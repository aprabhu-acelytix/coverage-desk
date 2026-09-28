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
        if kind=='finding':
            from .scope import identity,version
            data={**data,'article_id':identity(actor.workspace,actor.user,data['url']),'version_id':version(data)}
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
            if not row:
                raise DeskError('Unknown usage category.')
            self.db.execute('UPDATE budgets SET used=used+1 WHERE kind=?',(kind,))

    def budgets(self):
        with self.lock:
            # Legacy caps remain in SQLite as historical data, not enforcement.
            return {r['kind']: {'used':r['used'],'cap':None,'historical_cap':r['cap']} for r in self.db.execute('SELECT * FROM budgets')}

    def claim(self, key):
        with self.lock:
            return self.db.execute('INSERT OR IGNORE INTO claims VALUES(?,?)',(key,time.time())).rowcount == 1

    def preferences(self, actor, changes=None):
        self.authorize(actor)
        with self.lock:
            row = self.db.execute('SELECT data FROM preferences WHERE workspace=? AND user=?',(actor.workspace,actor.user)).fetchone()
            value = json.loads(row[0]) if row else {'tab':'explore','page':0,'filter':'relevant','history':'current','monitor':''}
            if changes:
                value.update(changes)
                self.db.execute('INSERT OR REPLACE INTO preferences VALUES(?,?,?)',(actor.workspace,actor.user,json.dumps(value)))
            return value

    def purge(self):
        with self.lock:
            n = self.db.execute('DELETE FROM objects WHERE expires<=?',(time.time(),)).rowcount
            if self.db.execute("SELECT 1 FROM sqlite_master WHERE name='article_aliases'").fetchone():
                self.db.execute('DELETE FROM article_aliases WHERE expires<=?',(time.time(),))
            self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            if self.s.database!=':memory:':
                # Migration backups retain original expiries, never renewed rights.
                folder=Path(self.s.database).resolve().parent/'backups'
                for path in [*folder.glob('research-v1-*.sqlite3'),*folder.glob('overview-v1-*.sqlite3')]:
                    backup=sqlite3.connect(path)
                    try:
                        backup.execute('PRAGMA secure_delete=ON')
                        backup.execute('DELETE FROM objects WHERE expires<=?',(time.time(),))
                        backup.commit()
                        backup.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                    finally:backup.close()
                # Only task-owned public validation exports; no arbitrary user files.
                root=Path(self.s.database).resolve().parent
                for pattern in ('research-comparison-*.json','native-research-probe.json','research-workflow-validation.json'):
                    for path in root.glob(pattern):
                        if path.is_file() and path.stat().st_mtime+self.s.retention_days*86400<=time.time():path.unlink()
            return n

    def migrate_research(self):
        """Idempotent metadata migration; observation and board IDs never change."""
        from .scope import identity,version,scope_key
        with self.lock:
            exists=self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='migrations'").fetchone()
            if exists and self.db.execute("SELECT 1 FROM migrations WHERE name='research-v1'").fetchone():return None
            backup_path=None
            if self.s.database!=':memory:':
                folder=Path(self.s.database).resolve().parent/'backups'
                folder.mkdir(exist_ok=True)
                backup_path=folder/f'research-v1-{int(time.time())}.sqlite3'
                backup=sqlite3.connect(backup_path)
                try:self.db.backup(backup)
                finally:backup.close()
            with self.transaction():
                self.db.execute('CREATE TABLE IF NOT EXISTS migrations(name TEXT PRIMARY KEY, applied REAL, backup TEXT)')
                self.db.execute('CREATE TABLE IF NOT EXISTS article_aliases(observation_id TEXT PRIMARY KEY, article_id TEXT, expires REAL)')
                records=self.db.execute('SELECT * FROM objects').fetchall()
                monitors={r['id']:json.loads(r['data']) for r in records if r['kind']=='monitor'}
                for raw in records:
                    data=json.loads(raw['data'])
                    if raw['kind']=='monitor':data['scope_key']=scope_key(data)
                    elif raw['kind']=='finding':
                        data.update(article_id=identity(raw['workspace'],raw['owner'],data['url']),version_id=version(data))
                        monitor=monitors.get(data.get('monitor_id'))
                        if monitor and data.get('monitor_revision')==monitor.get('revision'):
                            data['scope_key']=scope_key(monitor)
                        data['legacy_observation']=True
                        self.db.execute('INSERT OR IGNORE INTO article_aliases VALUES(?,?,?)',(raw['id'],data['article_id'],raw['expires']))
                    elif raw['kind']=='preview':data['used']=True
                    else:continue
                    self.db.execute('UPDATE objects SET data=? WHERE id=?',(json.dumps(data),raw['id']))
                for row in self.db.execute('SELECT workspace,user,data FROM preferences').fetchall():
                    p=json.loads(row['data']);p.update(filter='relevant',history='current',page=0)
                    self.db.execute('UPDATE preferences SET data=? WHERE workspace=? AND user=?',(json.dumps(p),row['workspace'],row['user']))
                self.db.execute('INSERT INTO migrations VALUES(?,?,?)',('research-v1',time.time(),str(backup_path) if backup_path else None))
            return backup_path

    def migrate_overview(self):
        """Backup first; preserve all source/board IDs and ledger entries."""
        self.migrate_research()
        with self.lock:
            if self.db.execute("SELECT 1 FROM migrations WHERE name='overview-v1'").fetchone():return None
            path=None
            if self.s.database!=':memory:':
                folder=Path(self.s.database).resolve().parent/'backups';folder.mkdir(exist_ok=True)
                path=folder/f'overview-v1-{int(time.time())}.sqlite3'
                backup=sqlite3.connect(path)
                try:self.db.backup(backup)
                finally:backup.close()
            with self.transaction():
                for row in self.db.execute('SELECT workspace,user,data FROM preferences').fetchall():
                    p=json.loads(row['data']);p.update(explore_view='overview',content_type='reporting',coverage_state='confirmed',outlet='',outlet_page=0,page=0)
                    self.db.execute('UPDATE preferences SET data=? WHERE workspace=? AND user=?',(json.dumps(p),row['workspace'],row['user']))
                self.db.execute('INSERT INTO migrations VALUES(?,?,?)',('overview-v1',time.time(),str(path) if path else None))
            return path
