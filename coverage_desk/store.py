"""Scoped SQLite records. Every public operation requires an authenticated actor."""
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from contextlib import contextmanager
from dataclasses import dataclass
from .config import DeskError

@dataclass(frozen=True)
class Actor:
    workspace: str
    user: str

class Store:
    def __init__(self, settings):
        self.s = settings
        if settings.database != ':memory:':
            Path(settings.database).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(settings.database, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        PRAGMA secure_delete=ON;
        CREATE TABLE IF NOT EXISTS objects(id TEXT PRIMARY KEY, kind TEXT NOT NULL, workspace TEXT NOT NULL,
          owner TEXT NOT NULL, visibility TEXT NOT NULL, data TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS object_scope ON objects(workspace,kind,expires);
        CREATE TABLE IF NOT EXISTS claims(key TEXT PRIMARY KEY, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS budgets(kind TEXT PRIMARY KEY, used INTEGER NOT NULL, cap INTEGER NOT NULL);
        INSERT OR IGNORE INTO budgets VALUES('source',0,30);
        INSERT OR IGNORE INTO budgets VALUES('ai',0,10);
        CREATE TABLE IF NOT EXISTS preferences(workspace TEXT,user TEXT,data TEXT,PRIMARY KEY(workspace,user));
        ''')

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                yield
                self.db.execute('COMMIT')
            except BaseException:
                self.db.execute('ROLLBACK')
                raise

    def authorize(self, actor, owner=False):
        if not actor.user or not self.s.workspace or actor.workspace != self.s.workspace:
            raise DeskError('This action is unavailable in this workspace.')
        if owner and actor.user != self.s.owner:
            raise DeskError('AI and monitor controls are owner-operated in this prototype.')

    def _decode(self, row, actor):
        if not row or row['workspace'] != actor.workspace or (row['owner'] != actor.user and row['visibility'] != 'shared') or row['expires'] <= time.time():
            raise DeskError('This item is private, expired, or no longer available.')
        return dict(json.loads(row['data']), id=row['id'], kind=row['kind'], owner=row['owner'], visibility=row['visibility'], created=row['created'], expires=row['expires'])

    def get(self, actor, ident, kind=None):
        self.authorize(actor)
        with self.lock:
            result = self._decode(self.db.execute('SELECT * FROM objects WHERE id=?', (ident,)).fetchone(), actor)
        if kind and result['kind'] != kind:
            raise DeskError('This action does not apply to this item.')
        return result

    def list(self, actor, kind):
        self.authorize(actor)
        with self.lock:
            rows = self.db.execute('SELECT * FROM objects WHERE workspace=? AND kind=? AND expires>? AND (owner=? OR visibility=?) ORDER BY created DESC,id DESC', (actor.workspace,kind,time.time(),actor.user,'shared')).fetchall()
        return [self._decode(row,actor) for row in rows]

    def create(self, actor, kind, data, visibility='private', expires=None):
        self.authorize(actor)
        if visibility not in ('private','shared'):
            raise DeskError('Choose private or workspace shared.')
        ident = uuid.uuid4().hex
        now = time.time()
        with self.lock:
            self.db.execute('INSERT INTO objects VALUES(?,?,?,?,?,?,?,?)', (ident,kind,actor.workspace,actor.user,visibility,json.dumps(data),now,expires or now+self.s.retention_days*86400))
        return self.get(actor,ident)

    def update(self, actor, ident, data, owner_only=False):
        with self.lock:
            current = self.get(actor,ident)
            if owner_only and current['owner'] != actor.user:
                raise DeskError('Only the creator can change this item.')
            clean = {k:v for k,v in data.items() if k not in ('id','kind','owner','visibility','created','expires')}
            self.db.execute('UPDATE objects SET data=? WHERE id=?', (json.dumps(clean),ident))
            return self.get(actor,ident)

    def consume(self, kind):
        with self.transaction():
            row = self.db.execute('SELECT used,cap FROM budgets WHERE kind=?',(kind,)).fetchone()
            if not row or row['used'] >= row['cap']:
                raise DeskError(f'This build’s {kind} validation cap is reached. No request was sent.')
            self.db.execute('UPDATE budgets SET used=used+1 WHERE kind=?',(kind,))

    def budgets(self):
        with self.lock:
            return {r['kind']: {'used':r['used'],'cap':r['cap']} for r in self.db.execute('SELECT * FROM budgets')}

    def claim(self, key):
        with self.lock:
            return self.db.execute('INSERT OR IGNORE INTO claims VALUES(?,?)',(key,time.time())).rowcount == 1

    def preferences(self, actor, changes=None):
        self.authorize(actor)
        with self.lock:
            row = self.db.execute('SELECT data FROM preferences WHERE workspace=? AND user=?',(actor.workspace,actor.user)).fetchone()
            value = json.loads(row[0]) if row else {'tab':'explore','page':0,'filter':'all','monitor':''}
            if changes:
                value.update(changes)
                self.db.execute('INSERT OR REPLACE INTO preferences VALUES(?,?,?)',(actor.workspace,actor.user,json.dumps(value)))
            return value

    def purge(self):
        with self.lock:
            n = self.db.execute('DELETE FROM objects WHERE expires<=?',(time.time(),)).rowcount
            self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            return n
