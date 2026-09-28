import json
import threading
import time
import re
from concurrent.futures import ThreadPoolExecutor
from .config import DeskError, require_live
from .models import validate_analysis, digest
from .sources import Brave, demo_records, record
from .discovery import SOURCE_CHOICES

class Desk:
    def __init__(self,s,store,analyzer=None,provider=None):
        self.s,self.store = s,store
        self.analyzer = analyzer
        self.provider = provider or Brave(s,store)
        self.pool = ThreadPoolExecutor(max_workers=1,thread_name_prefix='coverage')
        self.slots = threading.BoundedSemaphore(1+s.queue_size)
        self.jobs = {}
        self.runtime_state = 'Demo fixtures' if s.mode=='demo' else 'Check local sign-in'
        self.guard = threading.RLock()
        self.changed = lambda actor: None

    def monitor(self,actor,values,ident=None):
        self.store.authorize(actor,owner=True)
        name = values.get('name','').strip()
        if not name or len(name)>100:
            raise DeskError('Client name must contain 1–100 characters.')
        messages = [m.strip() for m in values.get('messages',[]) if m.strip()]
        if len(messages)>8 or any(len(m)>500 for m in messages):
            raise DeskError('Use up to eight messages, each under 500 characters.')
        freshness=values.get('custom_range') or values.get('freshness','pw')
        if freshness not in ('','pd','pw','pm','py'):
            from datetime import date
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}to\d{4}-\d{2}-\d{2}',freshness):raise ValueError()
                start,end=freshness.split('to')
                if date.fromisoformat(start)>date.fromisoformat(end):raise ValueError()
            except ValueError:raise DeskError('Use a valid custom range: YYYY-MM-DDtoYYYY-MM-DD, earliest date first.') from None
        sources = values.get('sources', ['news', 'web'])
        if not sources or any(x not in {value:label for label,value in SOURCE_CHOICES} for x in sources):
            raise DeskError('Choose at least one supported source.')
        data = {'name':name,'aliases':values.get('aliases',[])[:4],'domains':values.get('domains','')[:500],
            'notes':values.get('notes','')[:1000],'campaign':values.get('campaign','')[:300],
            'messages':messages,'language':values.get('language','en'), 'country':values.get('country','US'),
            'freshness':freshness,'sources':list(dict.fromkeys(sources)),
            'revision':time.time()}
        if ident:
            self.store.get(actor,ident,'monitor')
            return self.store.update(actor,ident,data,owner_only=True)
        return self.store.create(actor,'monitor',data,expires=time.time()+10*365*86400)

    def submit(self,actor,label,callback,owner=False,key=None):
        self.store.authorize(actor,owner=owner)
        with self.guard:
            if self.jobs.get(actor.user,{}).get('state') in ('Queued','Working'):
                raise DeskError('You already have work in progress. Wait or cancel it before starting another action.')
            if not self.slots.acquire(blocking=False):
                raise DeskError('The work queue is full. Try again when the current work finishes.')
            if key and not self.store.claim('action:'+key):
                self.slots.release()
                return
            event = threading.Event()
            self.jobs[actor.user] = {'label':label,'state':'Queued','cancel':event}
            saved_job=self.store.create(actor,'job',{'label':label,'state':'Queued','started':time.time()})
            self.jobs[actor.user]['id']=saved_job['id']
        self.changed(actor)
        def work():
            try:
                self.store.authorize(actor,owner=owner)
                if event.is_set():
                    raise DeskError('Cancelled before starting.')
                self.jobs[actor.user]['state'] = 'Working'
                self.progress(actor, {'stage':'Searching' if label=='Collecting coverage' else 'Working'})
                self.changed(actor)
                callback(event)
                self.jobs[actor.user]['state'] = 'Cancelled' if event.is_set() else self.jobs[actor.user].get('outcome', 'Complete')
            except Exception as exc:
                self.jobs[actor.user]['state'] = str(exc) if isinstance(exc,DeskError) else 'Unavailable — retry the action after checking local status.'
                if self.jobs[actor.user].get('run_id'):
                    self.jobs[actor.user]['error']=str(exc) if isinstance(exc,DeskError) else 'Collection interrupted. Saved findings are preserved.'
                    self.jobs[actor.user]['state']=self.jobs[actor.user].get('outcome','Unavailable')
                if isinstance(exc,DeskError):
                    for state in ('Sign-in needed','Usage limit','AI timeout','Invalid evidence'):
                        if state.lower() in str(exc).lower():
                            self.runtime_state=state
                            break
            finally:
                job=self.jobs[actor.user]
                self.store.update(actor,saved_job['id'],{k:v for k,v in job.items() if k not in ('cancel','id')})
                self.slots.release()
                self.changed(actor)
        self.pool.submit(work)

    def cancel(self,actor):
        self.store.authorize(actor)
        if actor.user in self.jobs:
            self.jobs[actor.user]['cancel'].set()
            self.progress(actor,{'cancel_requested':True})

    def progress(self, actor, values):
        job = self.jobs.get(actor.user)
        if not job:
            return
        with self.guard:
            job.update(values)
            if job.get('id'):
                self.store.update(actor, job['id'], {k:v for k,v in job.items() if k not in ('cancel','id')})
        self.changed(actor)

    def refresh(self,actor,monitor_id,cancel):
        self.store.authorize(actor,owner=True)
        monitor = self.store.get(actor,monitor_id,'monitor')
        run = self.store.create(actor,'run',{'monitor_id':monitor_id,'statuses':[],'count':0,
            'mode':self.s.mode,'pages_cap':self.s.pages,'calls_cap':self.s.calls,'checked':time.time(),
            'enabled_sources':monitor.get('sources',['news','web']),'outcome':'Searching'})
        self.progress(actor, {'monitor_id':monitor_id,'run_id':run['id'], 'retained':0})
        saved = []
        def save_page(rows, statuses):
            for row in rows:
                saved.append(self.store.create(actor,'finding',{**row,'monitor_id':monitor_id,'monitor_revision':monitor['revision']}))
            run.update(statuses=statuses,count=len(saved),checked=time.time())
            self.store.update(actor,run['id'],run)
        try:
            if self.s.mode == 'demo':
                rows,statuses = demo_records(monitor),[{'source':'Synthetic fixtures','status':'Results','results':1}]
                save_page(rows,statuses)
            else:
                rows,statuses = self.provider.retrieve(monitor,cancel,on_page=save_page,
                    progress=lambda value:self.progress(actor,value))
            failures = any(x['status'] not in ('Results','No matches') for x in statuses)
            outcome = ('Cancelled' if cancel.is_set() else 'Partial results' if failures and saved else
                       'Unavailable' if failures else 'Ready' if saved else 'No matches')
            run.update(statuses=statuses,count=len(saved),outcome=outcome,checked=time.time())
            self.store.update(actor,run['id'],run)
            self.progress(actor,{'stage':'Saving','outcome':outcome,'retained':len(saved)})
            return rows
        except Exception:
            run.update(count=len(saved),outcome='Partial results' if saved else 'Unavailable',checked=time.time())
            self.store.update(actor,run['id'],run)
            self.progress(actor,{'outcome':run['outcome'],'retained':len(saved)})
            raise

    def manual(self,actor,values):
        self.store.authorize(actor)
        if not values.get('title','').strip():
            raise DeskError('Give the source a title.')
        row = record(values['title'],values['url'],values.get('text',''), 'Manual contribution',
            {'submitted_by':actor.user,'verification':'User-supplied text; publisher text not verified'},access='user-supplied excerpt')
        row['monitor_id'] = values.get('monitor_id','')
        if row['monitor_id']:
            self.store.get(actor,row['monitor_id'],'monitor')
        row['comment'] = values.get('comment','')[:2000]
        return self.store.create(actor,'finding',row)

    def allowed_source(self,row):
        if row['expires']<=time.time():
            raise DeskError('A source expired. Select current findings.')
        if row['provider'].startswith('Brave') and not self.s.storage_allowed:
            raise DeskError('Brave storage permission is no longer enabled.')
        if row['provider'].startswith('YouTube'):
            raise DeskError('YouTube metadata is not enabled for AI or briefing export.')

    def analyze(self,actor,monitor_id,ids,cancel):
        self.store.authorize(actor,owner=True)
        if self.s.mode=='live':require_live(self.s)
        monitor = self.store.get(actor,monitor_id,'monitor')
        sources = [self.store.get(actor,i,'finding') for i in ids]
        if not sources or len(sources)>self.s.ai_items:
            raise DeskError(f'Select between one and {self.s.ai_items} findings.')
        for row in sources:
            self.allowed_source(row)
            if row.get('monitor_id') != monitor_id:
                raise DeskError('Select findings from the same monitor.')
        key = digest(json.dumps({'sources':[{k:r[k] for k in ('id','hash','title','provider','access')} for r in sources],
            'criteria':monitor,'version':2,'actor':actor.user,'mode':self.s.mode,'model':self.s.model,
            'runtime':'0.157.1'},sort_keys=True))
        cached = next((x for x in self.store.list(actor,'analysis_cache') if x['key']==key),None)
        if cached:
            result = cached['result']
        elif self.s.mode == 'demo':
            result = {'findings':[{'source_id':r['id'],'relevance':'uncertain','campaign_relevance':'uncertain' if monitor['campaign'] else 'not_applicable',
                'explanation':'Fixture assessment; no live inference.', 'messages':[{'message':m,'label':'insufficient_evidence',
                'explanation':'Demo fixture only.','evidence':[]} for m in monitor['messages']]} for r in sources]}
        else:
            require_live(self.s)
            if not self.analyzer:
                raise DeskError('AI unavailable. Run the local runtime status helper.')
            result = self.analyzer.analyze(sources,monitor,cancel)
            self.runtime_state='Ready'
        result = validate_analysis(result,sources,monitor['messages'])
        if cancel.is_set():
            raise DeskError('Cancelled; no assessment saved.')
        self.store.authorize(actor,owner=True)
        if self.store.get(actor,monitor_id,'monitor')['revision'] != monitor['revision']:
            raise DeskError('Monitor changed while AI was working. Results were not saved.')
        for assessment in result['findings']:
            row = self.store.get(actor,assessment['source_id'],'finding')
            self.allowed_source(row)
            row.update(analysis=assessment,analysis_status='Fixture assessment' if self.s.mode=='demo' else 'AI assessed',analysis_key=key)
            self.store.update(actor,row['id'],row)
        if not cached:
            self.store.create(actor,'analysis_cache',{'key':key,'result':result},expires=min(r['expires'] for r in sources))
        return result

    def save(self,actor,source_id,visibility,confirmed=False,include_analysis=False):
        source = self.store.get(actor,source_id,'finding')
        self.allowed_source(source)
        if visibility == 'shared' and not confirmed:
            raise DeskError('Confirm disclosure to everyone in this workspace.')
        # Copy evidence without private criteria, query provenance, analysis or comments.
        # Private assessments stay in Explore; sharing never exposes monitor messages.
        with self.store.lock:
            existing = next((b for b in self.store.list(actor,'board') if b['source_id']==source_id and b['visibility']==visibility and (visibility=='shared' or b['owner']==actor.user)),None)
            if existing:
                if include_analysis and source.get('analysis'):
                    existing.update(analysis=source['analysis'],analysis_status=source['analysis_status'],
                        assessment_disclosure='Creator explicitly included this assessment and its message wording.')
                    return self.store.update(actor,existing['id'],existing)
                return existing
            selected = {k:source[k] for k in ('title','url','canonical','text','provider','published','retrieved','access','hash')}
            selected.update(source_id=source_id,status='New',perspectives=[],analysis=None,
                analysis_status='Private assessment not shared',verification='User-supplied; not publisher-verified' if source['provider']=='Manual contribution' else 'Provider-returned excerpt; full article not retrieved')
            if include_analysis and source.get('analysis'):
                selected.update(analysis=source['analysis'],analysis_status=source['analysis_status'],
                    assessment_disclosure='Creator explicitly included this assessment and its message wording.')
            return self.store.create(actor,'board',selected,visibility,source['expires'])

    def perspective(self,actor,board_id,text,status=None):
        with self.store.lock:
            board = self.store.get(actor,board_id,'board')
            self.allowed_source(board)
            if text.strip():
                if len(text)>2000:
                    raise DeskError('Keep perspectives under 2,000 characters.')
                board['perspectives'].append({'author':actor.user,'text':text.strip(),'at':time.time()})
                board['perspectives'] = board['perspectives'][-30:]
            if status:
                if status not in ('New','Reviewed','Use in briefing'):
                    raise DeskError('Unknown review status.')
                board['status'] = status
            return self.store.update(actor,board_id,board)

    def draft(self,actor,board_ids,cancel=None,use_ai=False):
        self.store.authorize(actor,owner=True)
        boards = [self.store.get(actor,i,'board') for i in dict.fromkeys(board_ids)]
        if not boards or len(boards)>5:
            raise DeskError('Select one to five board findings.')
        for b in boards:
            self.allowed_source(b)
        shared = all(b['visibility']=='shared' for b in boards)
        ai=None
        if use_ai and self.s.mode=='live':
            require_live(self.s)
            if not self.analyzer:raise DeskError('AI unavailable. Use a source-linked draft without AI.')
            ai=self.analyzer.briefing(boards,cancel or threading.Event())
            self.runtime_state='Ready'
            if cancel and cancel.is_set():raise DeskError('Cancelled; no draft saved.')
            for b in boards:self.allowed_source(self.store.get(actor,b['id'],'board'))
        text = 'What changed\n'+'\n'.join('• '+b['title'] for b in boards)
        text += '\n\nMessage evidence\nSource excerpts are linked below. Private monitor assessments are not included.'
        if ai:
            text='What changed · AI assessment\n'+'\n'.join('• '+p['text'] for p in ai['what_changed'])
            text+='\n\nMessage evidence · AI assessment\n'+('\n'.join('• '+p['text'] for p in ai['message_evidence']) or 'No message evidence identified in the available excerpts.')
            text+='\n\nWorth discussing\n'+ai['worth_discussing']
        else:text+='\n\nWorth discussing\nWhat additional reporting would help us interpret this coverage?'
        perspectives=[dict(n) for b in boards for n in b['perspectives']]
        return self.store.create(actor,'briefing',{'title':'Coverage briefing · '+time.strftime('%d %b %Y'),
            'text':text[:2800],'perspectives':sorted(perspectives,key=lambda n:n['at'])[-8:],'perspective_count':len(perspectives),'board_ids':[b['id'] for b in boards],'revision':1,'status':'Draft','edits':[],'ai_evidence':ai,
            'sources':[{'title':b['title'],'url':b['url'],'provider':b['provider'],'access':b['access']} for b in boards]},
            'shared' if shared else 'private',min(b['expires'] for b in boards))

    def restore_jobs(self, actor):
        jobs=self.store.list(actor,'job')
        for job in jobs:
            if job['state'] in ('Queued','Working'):
                job.update(state='Interrupted',outcome='Interrupted')
                self.store.update(actor,job['id'],job)
                if job.get('run_id'):
                    try:
                        run=self.store.get(actor,job['run_id'],'run')
                        run['outcome']='Interrupted'
                        job['retained']=run['count']
                        self.store.update(actor,run['id'],run)
                    except DeskError:pass
                self.store.update(actor,job['id'],job)
        if jobs:self.jobs[actor.user]={**jobs[0],'cancel':threading.Event()}

    def migrate_perspectives(self, actor):
        """Split only a provable generated suffix; never rewrite a collaborator's prose."""
        marker='\n\nTeam perspective (not sent to AI)\n'
        for draft in self.store.list(actor,'briefing'):
            if draft['status']!='Draft' or draft.get('edits') or 'perspectives' in draft or marker not in draft['text']:
                continue
            try:
                boards=[self.store.get(actor,i,'board') for i in draft['board_ids']]
            except DeskError:
                continue
            notes=[dict(n) for b in boards for n in b['perspectives'] if n['at']<=draft['created']]
            suffix='\n'.join(n['author']+': '+n['text'] for n in notes)
            before,actual=draft['text'].rsplit(marker,1)
            if actual not in (suffix, 'No team perspectives added.' if not notes else suffix):
                continue
            draft.update(text=before,perspectives=sorted(notes,key=lambda n:n['at'])[-8:],
                         perspective_count=len(notes),revision=draft['revision']+1)
            self.store.update(actor,draft['id'],draft)

    def edit_draft(self,actor,ident,text,revision):
        with self.store.lock:
            d = self.store.get(actor,ident,'briefing')
            if d['revision'] != revision or d['status'] != 'Draft':
                raise DeskError('This draft changed. Reopen it before editing.')
            if not text.strip() or len(text)>2800:
                raise DeskError('Use 1–2,800 characters.')
            d.update(text=text,revision=revision+1)
            d['edits'].append({'author':actor.user,'at':time.time()})
            return self.store.update(actor,ident,d)

    def preview(self,actor,ident):
        from .ui import briefing_message
        self.store.authorize(actor,owner=True)
        d = self.store.get(actor,ident,'briefing')
        if d['status']!='Draft':
            raise DeskError('This briefing was already sent or its delivery is uncertain.')
        for ident in d['board_ids']:
            self.allowed_source(self.store.get(actor,ident,'board'))
        if not self.s.channel:
            raise DeskError('Configure the public demo channel before publishing.')
        return self.store.create(actor,'preview',{'draft_id':d['id'],'revision':d['revision'],
            'channel':self.s.channel,'digest':digest(json.dumps(briefing_message(d),sort_keys=True)),'used':False},expires=min(time.time()+600,d['expires']))

    def publish(self,actor,preview_id,client):
        from .ui import briefing_message
        self.store.authorize(actor,owner=True)
        with self.store.lock:
            p = self.store.get(actor,preview_id,'preview')
            d = self.store.get(actor,p['draft_id'],'briefing')
            message=briefing_message(d)
            if p['used'] or d['status']!='Draft' or d['revision']!=p['revision'] or digest(json.dumps(message,sort_keys=True))!=p['digest'] or p['channel']!=self.s.channel:
                raise DeskError('Preview expired or changed. Open a fresh preview.')
            for ident in d['board_ids']:
                self.allowed_source(self.store.get(actor,ident,'board'))
            info = client.conversations_info(channel=self.s.channel)['channel']
            if info.get('is_private') or not info.get('is_member') or info.get('is_ext_shared') or info.get('is_shared') or info.get('is_archived'):
                raise DeskError('Publishing requires the configured public, internal channel with the bot invited.')
            p['used']=True
            self.store.update(actor,p['id'],p)
            d['status']='Delivery uncertain'
            self.store.update(actor,d['id'],d)
        try:
            result = client.chat_postMessage(channel=self.s.channel,**message,unfurl_links=False,unfurl_media=False,parse='none',link_names=False,client_msg_id=p['id'])
        except Exception:
            raise DeskError('Delivery is uncertain. Check the channel before taking any further action; automatic reposting is disabled.') from None
        d.update(status='Published',posted_ts=result['ts'])
        return self.store.update(actor,d['id'],d)
