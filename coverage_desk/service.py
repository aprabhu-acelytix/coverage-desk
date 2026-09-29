import json
import threading
import time
import re
from concurrent.futures import ThreadPoolExecutor
from .config import DeskError, require_live
from .models import validate_analysis, digest
from .sources import Brave, demo_records, record
from .discovery import SOURCE_CHOICES
from .scope import scope_key,snapshot,version

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
            'interpretation':values.get('interpretation','')[:500],'revision':time.time()}
        data['scope_key']=scope_key(data)
        path=values.get('research_path','Codex native web')
        if path not in ('AI-planned Brave','Codex native web'):raise DeskError('Unknown research path.')
        data['research_path']=path
        data['scope_key']=scope_key(data)
        if ident:
            self.store.get(actor,ident,'monitor')
            return self.store.update(actor,ident,data,owner_only=True)
        return self.store.create(actor,'monitor',data,expires=time.time()+10*365*86400)

    def set_outlet_priority(self,actor,source_id,priority,reason):
        from .outlets import PRIORITIES
        from .overview import host
        self.store.authorize(actor,owner=True)
        source=self.store.get(actor,source_id,'finding');self.allowed_source(source)
        reason=(reason or '').strip()
        if priority not in (*PRIORITIES,'default'):raise DeskError('Choose an outlet priority.')
        if not reason or len(reason)>500:raise DeskError('Add a short reason (up to 500 characters).')
        return self.store.create(actor,'outlet_priority',{'host':host(source['url']),'priority':priority,'reason':reason},
            expires=source['expires'])

    def mark_relevant(self,actor,source_id):
        self.store.authorize(actor,owner=True)
        current=self.finding_detail(actor,source_id);self.allowed_source(current)
        if not current.get('can_review'):raise DeskError('Mark findings in the current search scope.')
        if current.get('correction_audit',{}).get('changes',{}).get('relevance')!='relevant':
            self.correct_coverage(actor,source_id,{'relevance':'relevant','reason':'Owner marked this finding relevant in Slack.'})
        row=self.finding_detail(actor,source_id)
        notice='Marked relevant. Available in the Relevant view.'
        if row.get('date_status')=='unconfirmed':notice+=' Publication date is still unverified; it remains outside dated totals.'
        elif row.get('date_status')=='outside':notice+=' Its verified date is outside this period, so it remains outside current results.'
        self.store.preferences(actor,{'snapshot':time.time(),'page':0,'notice':notice})
        return row

    def correct_coverage(self,actor,source_id,values):
        from .overview import CONTENT_TYPES,host
        from datetime import datetime
        self.store.authorize(actor,owner=True)
        source=self.store.get(actor,source_id,'finding');self.allowed_source(source)
        monitor=self.store.get(actor,source['monitor_id'],'monitor')
        if source.get('scope_key')!=scope_key(monitor) or source.get('monitor_revision')!=monitor['revision']:raise DeskError('Edit findings in the current search scope.')
        reason=(values.get('reason') or '').strip()
        if not reason or len(reason)>1000:raise DeskError('Explain the correction and its supporting evidence (up to 1,000 characters).')
        changes={}
        content=values.get('content_type','keep');relevance=values.get('relevance','keep')
        if content!='keep':
            if content not in CONTENT_TYPES:raise DeskError('Choose a supported content type.')
            changes['content_type']=content
        if relevance!='keep':
            if relevance not in ('relevant','uncertain','not_relevant'):raise DeskError('Choose a relevance status.')
            changes['relevance']=relevance
        date_action=values.get('date_action','keep')
        if date_action=='unknown':changes['published']=None
        elif date_action=='set_day':
            from datetime import date
            try:changes.update(published=date.fromisoformat(values.get('published','')).isoformat(),date_precision='day')
            except ValueError:raise DeskError('Choose the publication date shown on the source.') from None
        elif date_action=='set':
            try:
                date=datetime.fromisoformat((values.get('published') or '').strip().replace('Z','+00:00'))
                if not date.tzinfo:raise ValueError()
                changes['published']=date.isoformat();changes['date_precision']='timestamp'
            except ValueError:raise DeskError('Use a publication timestamp with timezone, for example 2026-09-18T14:44:00-07:00.') from None
        elif date_action!='keep':raise DeskError('Choose a publication-date action.')
        if values.get('redistribution_action')=='clear':changes['redistribution']=''
        elif values.get('redistribution_action')=='set':
            from .models import observed_quote
            quote=(values.get('redistribution') or '').strip()
            if not observed_quote(quote,source):raise DeskError('Redistribution needs an exact quotation from the retained headline or excerpt.')
            changes['redistribution']=quote
        with self.store.transaction():
            from .models import canonical_url
            related={r['article_id'] for r in self.store.list(actor,'finding') if r.get('monitor_id')==monitor['id'] and
                r.get('scope_key')==scope_key(monitor) and canonical_url(r['canonical'])==canonical_url(source['canonical'])}
            prior=[r for r in self.store.list(actor,'coverage_review') if r['article_id'] in related and r['scope_key']==scope_key(monitor)]
            merged={};evidence={}
            for review in reversed(prior):merged.update(review['changes']);evidence.update(review.get('field_evidence',{}))
            merged.update(changes)
            evidence.update({field:{'reason':reason,'source_id':source_id,'author':actor.user,'at':time.time()} for field in changes})
            review=self.store.create(actor,'coverage_review',{'source_id':source_id,'article_id':source['article_id'],
                'monitor_id':monitor['id'],'scope_key':scope_key(monitor),'changes':merged,'field_evidence':evidence,'reason':reason},expires=source['expires'])
            name=(values.get('outlet_name') or '').strip();group=(values.get('outlet_group') or '').strip()
            if name or group:
                domain=host(source['url']);outlet_key=host('https://'+group) if group else domain
                if not name or len(name)>180 or not outlet_key or '/' in group:raise DeskError('Give the full outlet name and an optional exact grouping hostname.')
                self.store.create(actor,'outlet_alias',{'domain':domain,'outlet_key':outlet_key,'name':name,'reason':reason,
                    'source_id':source_id},expires=source['expires'])
            self.store.preferences(actor,{'snapshot':time.time(),'page':0,'notice':'Coverage correction saved with its evidence and author.'})
            return review

    def overview_snapshot(self,actor,monitor_id,preferences=None,confirmed=False):
        from .overview import coverage_overview
        self.store.authorize(actor,owner=True)
        if not confirmed:raise DeskError('Confirm disclosure of the client, campaign, aggregate counts and included sources first.')
        with self.store.transaction():
            monitor=self.store.get(actor,monitor_id,'monitor')
            overview=coverage_overview(self.store,actor,monitor,preferences)
            if not overview['articles']:raise DeskError('No confirmed articles in this category to share. Review the evidence or choose another category.')
            entries=[]
            for row in overview['articles']:
                self.allowed_source(row)
                entries.append({k:row.get(k) for k in ('id','article_id','title','url','text','provider','access','published','date_kind','date_precision',
                    'outlet_id','outlet_name','content_type','redistribution','expires','projection_expires')})
                entries[-1]['observation_ids']=[r['id'] for r in row['observations']]
                evidence=row['classification_evidence']
                entries[-1]['classification_evidence']={'method':evidence['method'],
                    'quote':evidence.get('quote','') if evidence['method']=='AI assessment' else ''}
            frozen={k:overview[k] for k in ('at','category','article_count','outlet_count','partial','caveats','freshness')}
            frozen['scope']={'window':overview['scope']['window'],'id':overview['scope']['id']}
            frozen['outlets']=[{k:o[k] for k in ('id','key','name','count')} for o in overview['outlets']]
            frozen['sources']=entries;frozen['client']=monitor['name'];frozen['campaign']=monitor.get('campaign','')
            return self.store.create(actor,'briefing',{'title':monitor['name']+' | Coverage found','text':'Frozen coverage overview',
                'overview':frozen,'sources':entries,'board_ids':[],'status':'Draft','revision':1,'edits':[],
                'disclosure_confirmed':True},expires=min(r['projection_expires'] for r in entries))

    def validate_overview_snapshot(self,actor,draft):
        if not draft.get('overview'):return
        if not draft.get('disclosure_confirmed'):raise DeskError('Overview disclosure has not been confirmed.')
        for source in draft['overview']['sources']:
            current=self.store.get(actor,source['id'],'finding');self.allowed_source(current)
            if current['expires']<time.time() or source['projection_expires']<=time.time():raise DeskError('Overview source evidence expired. Create a fresh overview.')
        ids={s['article_id'] for s in draft['overview']['sources']}
        observations={ident for source in draft['overview']['sources'] for ident in source.get('observation_ids',[source['id']])}
        if any((r['article_id'] in ids or r.get('source_id') in observations) and r['created']>draft['overview']['at'] for r in self.store.list(actor,'coverage_review')):
            raise DeskError('Included evidence was corrected after this snapshot. Create a fresh overview before publishing.')
        from .overview import host
        domains={host(s['url']) for s in draft['overview']['sources']}
        if any(a['domain'] in domains and a['created']>draft['overview']['at'] for a in self.store.list(actor,'outlet_alias')):
            raise DeskError('An included outlet identity changed. Create a fresh overview before publishing.')

    def adopt_native_research(self,actor):
        """Apply the owner's requested provider change once, without revising evidence scopes."""
        self.store.authorize(actor,owner=True)
        with self.store.transaction():
            if not self.store.claim('owner-request:native-research-default:v2'):return
            for monitor in self.store.list(actor,'monitor'):
                if monitor['owner']!=actor.user:continue
                monitor['research_path']='Codex native web'
                self.store.update(actor,monitor['id'],monitor,owner_only=True)
            self.store.preferences(actor,{'notice':'Searches now use Codex web research. Search options lets you choose Brave explicitly; existing findings and shared work are preserved.'})

    def delete_monitor(self,actor,ident,confirmed=False):
        self.store.authorize(actor,owner=True)
        if not confirmed:raise DeskError('Confirm deletion of this search first.')
        with self.guard, self.store.transaction():
            if self.jobs.get(actor.user,{}).get('state') in ('Queued','Working'):
                raise DeskError('Wait for the current work to finish, or cancel it, before deleting a search.')
            monitor=self.store.get(actor,ident,'monitor')
            if monitor['owner']!=actor.user:raise DeskError('Only the search creator can delete it.')
            # Board/briefing snapshots are independent; keep their IDs and evidence.
            records=self.store.db.execute('SELECT id,kind,data FROM objects WHERE workspace=? AND owner=?',
                (actor.workspace,actor.user)).fetchall()
            ids=[r['id'] for r in records if r['id']==ident or
                (r['kind'] in ('finding','run','schedule','job') and json.loads(r['data']).get('monitor_id')==ident)]
            source_ids=set(ids)
            ids.extend(r['id'] for r in records if r['kind']=='analysis_cache' and any(
                f.get('source_id') in source_ids for f in json.loads(r['data']).get('result',{}).get('findings',[])))
            self.store.db.executemany('DELETE FROM objects WHERE id=?',[(i,) for i in ids])
            if self.store.db.execute("SELECT 1 FROM sqlite_master WHERE name='article_aliases'").fetchone():
                self.store.db.executemany('DELETE FROM article_aliases WHERE observation_id=?',[(i,) for i in ids])
            preferences=self.store.preferences(actor)
            if preferences.get('monitor')==ident:
                remaining=self.store.list(actor,'monitor')
                self.store.preferences(actor,{'monitor':remaining[0]['id'] if remaining else '',
                    'page':0,'snapshot':time.time(),'history':'current'})
            if self.jobs.get(actor.user,{}).get('monitor_id')==ident:self.jobs.pop(actor.user,None)

    def deletable_item(self,actor,ident,kind):
        if kind not in ('board','briefing'):raise DeskError('This item cannot be deleted here.')
        row=self.store.get(actor,ident,kind)
        if row['owner']!=actor.user and not (actor.user==self.s.owner and row['visibility']=='shared'):
            raise DeskError('Only the creator or workspace app owner can delete this shared item.')
        return row

    def delete_item(self,actor,ident,kind,confirmed=False):
        if not confirmed:raise DeskError('Confirm deletion first.')
        with self.guard,self.store.transaction():
            row=self.deletable_item(actor,ident,kind)
            if any(j.get('state') in ('Queued','Working') for j in self.jobs.values()):
                raise DeskError('Wait for current work to finish before deleting saved items.')
            affected={ident} if kind=='briefing' else set()
            if kind=='board':
                # Referential maintenance includes other users' private drafts,
                # without returning their contents or existence to the deleter.
                drafts=self.store.db.execute("SELECT id,data FROM objects WHERE workspace=? AND kind='briefing'",(actor.workspace,)).fetchall()
                for saved in drafts:
                    draft=json.loads(saved['data'])
                    if ident not in draft['board_ids']:continue
                    # Preserve only the evidence needed by an already-created briefing.
                    fields=('title','full_title','url','text','provider','access','expires','hash','canonical','published','date_kind')
                    draft.setdefault('source_snapshots',{})[ident]={k:row[k] for k in fields if k in row}
                    if draft['status']=='Draft':draft['revision']+=1
                    self.store.db.execute('UPDATE objects SET data=? WHERE id=?',(json.dumps(draft),saved['id']))
                    affected.add(saved['id'])
            previews=self.store.db.execute("SELECT id,data FROM objects WHERE workspace=? AND kind='preview'",(actor.workspace,)).fetchall()
            for preview in previews:
                if json.loads(preview['data']).get('draft_id') in affected:
                    self.store.db.execute('DELETE FROM objects WHERE id=?',(preview['id'],))
            self.store.db.execute('DELETE FROM objects WHERE id=?',(ident,))
            self.store.preferences(actor,{'page':0})

    def briefing_source(self,actor,draft,ident):
        snapshot=draft.get('source_snapshots',{}).get(ident)
        source=snapshot if snapshot is not None else self.store.get(actor,ident,'board')
        self.allowed_source(source)
        return source

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
                self.jobs[actor.user]['error']=str(exc) if isinstance(exc,DeskError) else 'The operation could not finish. Saved evidence remains available.'
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
            'enabled_sources':monitor.get('sources',['news','web']),'scope':snapshot(monitor),'path':'collection-only legacy','outcome':'Searching'})
        self.progress(actor, {'monitor_id':monitor_id,'run_id':run['id'], 'retained':0})
        saved = []
        def save_page(rows, statuses):
            for row in rows:
                saved.append(self.store.create(actor,'finding',{**row,'monitor_id':monitor_id,'monitor_revision':monitor['revision'],'scope_key':scope_key(monitor),'run_id':run['id'],'scope_id':run['scope']['id']}))
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
            run=self.store.get(actor,run['id'],'run')
            run.update(count=len(saved),outcome='Partial results' if saved else 'Unavailable',checked=time.time())
            self.store.update(actor,run['id'],run)
            self.progress(actor,{'outcome':run['outcome'],'retained':len(saved)})
            raise

    def research(self,actor,monitor_id,cancel):
        """Owner-led planning, observed discovery, then isolated evidence assessment."""
        self.store.authorize(actor,owner=True)
        if self.s.mode=='demo':
            self.refresh(actor,monitor_id,cancel)
            return self.continue_research(actor,monitor_id,cancel)
        monitor=self.store.get(actor,monitor_id,'monitor')
        return self.planned_research(actor,monitor_id,cancel,monitor.get('research_path','Codex native web'))

    def planned_research(self,actor,monitor_id,cancel,path='AI-planned Brave'):
        from dataclasses import replace
        from .research import registry,search_tasks,search_statuses,event_queries
        from .discovery import finding_selection
        self.store.authorize(actor,owner=True);require_live(self.s)
        if not self.analyzer:raise DeskError('AI unavailable. Run the runtime status helper.')
        if path=='AI-planned Brave' and (not self.s.brave_key or not self.s.storage_allowed):
            raise DeskError('AI-planned Brave requires a configured Brave key and owner-supplied storage permission.')
        monitor=self.store.get(actor,monitor_id,'monitor');scope=snapshot(monitor)
        run=self.store.create(actor,'run',{'monitor_id':monitor_id,'scope':scope,'path':path,'mode':self.s.mode,
            'statuses':[],'count':0,'checked':time.time(),'outcome':'Researching','pages_cap':1,'calls_cap':self.s.calls,
            'enabled_sources':monitor['sources']})
        self.progress(actor,{'stage':'Understanding the search','monitor_id':monitor_id,'run_id':run['id'],'retained':0})
        saved=[];statuses=[]
        def persist(rows):
            for row in rows:
                row.update(monitor_id=monitor_id,monitor_revision=monitor['revision'],
                    scope_key=scope['key'],scope_id=scope['id'],run_id=run['id'])
                saved.append(self.store.create(actor,'finding',row))
            run.update(count=len(saved),statuses=statuses);self.store.update(actor,run['id'],run)
        try:
            plan=self.analyzer.plan(monitor,cancel,max_queries=3)
            tasks=search_tasks(monitor,plan,scope)
            run.update(interpretation=plan['interpretation'],plan=plan['queries'],tasks=tasks)
            self.store.update(actor,run['id'],run)
            if path=='Codex native web':
                self.progress(actor,{'stage':'Searching selected sources','retained':0})
                envelope=self.analyzer.discover(scope,tasks[:self.s.calls],cancel)
                statuses=search_statuses(tasks,envelope.get('observed',[]))
                rows=registry(envelope)
                for row in rows:
                    event=next((e for e in envelope.get('observed',[]) if e.get('id')==row['provenance'].get('event_id')), {})
                    queries=event_queries(event)
                    row['provenance']['query']='; '.join(queries)
                    row['provenance']['targets']=[t['target'] for t in tasks if any(t['query'].lower().split()==q.lower().split() for q in queries)]
                    row['provenance']['task_order']=next((i for i,t in enumerate(tasks) if t['query'] in queries),len(tasks))
                persist(rows)
                run.update(observed_actions=[{'id':e.get('id'),'query':e.get('query'),'action':e.get('action'),
                    'returned_results':len(e.get('results') or [])} for e in envelope.get('observed',[])],
                    error=envelope.get('interrupted',''),limited=envelope.get('limited',False),reserved_source_slots=min(len(tasks),self.s.calls)+1)
            else:
                provider=Brave(replace(self.s,calls=1,pages=1,results=min(10,self.s.results)),self.store)
                def save_page(rows,updates):
                    for rank,row in enumerate(rows):
                        row['date_kind']='page_age'
                        row['provenance'].update(task_order=index,result_rank=rank,targets=[query['target']])
                    persist(rows)
                for index,query in enumerate(tasks):
                    if cancel.is_set() or index>=self.s.calls:
                        statuses.append({**query,'requested':False,'results':0,'status':'Not searched'})
                        continue
                    self.progress(actor,{'stage':'Searching '+query['target'],'retained':len(saved)})
                    _,updates=provider.retrieve({**monitor,'sources':[query['target']],
                        '_planned_query':query['query'],'_planned_purpose':query['purpose']},cancel,on_page=save_page)
                    statuses.extend(updates)
            run.update(statuses=statuses);self.store.update(actor,run['id'],run)
            current=self.store.get(actor,monitor_id,'monitor')['revision']==monitor['revision']
            if current and not cancel.is_set():
                self.complete_research(actor,monitor_id,cancel)
                # Reload progress persisted by the complete workflow.
                run=self.store.get(actor,run['id'],'run')
            current=self.store.get(actor,monitor_id,'monitor')['revision']==monitor['revision']
            projection=finding_selection(self.store,actor,{'monitor':monitor_id,'filter':'all','snapshot':time.time()})
            rows=projection['rows'] if current else saved
            assessed=sum(bool(r.get('analysis')) and not r.get('analysis_error') for r in rows)
            run.update(count=len(saved),unique_count=len({r['canonical'] for r in saved}),assessed_count=assessed,
                pending_count=len(rows)-assessed,counts=projection['counts'],checked=time.time(),
                outcome='Cancelled' if cancel.is_set() else 'Previous scope' if not current else
                    'Needs review' if projection['counts']['review'] or run.get('error') else 'Assessed')
            self.store.update(actor,run['id'],run)
            self.progress(actor,{'outcome':run['outcome'],'stage':'Search complete','retained':run['unique_count']})
            self.store.preferences(actor,{'snapshot':time.time(),'page':0,'history':'current','notice':'','explore_view':'overview','outlet':'','outlet_page':0})
            return saved
        except Exception:
            run=self.store.get(actor,run['id'],'run')
            run.update(count=len(saved),outcome='Partial results' if saved else 'Unavailable',checked=time.time())
            self.store.update(actor,run['id'],run)
            self.progress(actor,{'outcome':run['outcome'],'retained':len(saved)})
            self.store.preferences(actor,{'snapshot':time.time()})
            raise

    def complete_research(self,actor,monitor_id,cancel):
        from .workflow import complete
        return complete(self,actor,monitor_id,cancel)

    def verify_dates(self,actor,monitor_id,cancel):
        from .public_evidence import fetch_metadata
        from .discovery import finding_selection
        from .research import needs_publication_check,evidence_priority
        from .discovery import platform
        monitor=self.store.get(actor,monitor_id,'monitor')
        rows=finding_selection(self.store,actor,{'monitor':monitor_id,'filter':'all','snapshot':time.time()})['rows']
        candidates=[r for r in rows if needs_publication_check(r,monitor) or (r.get('relevance')=='relevant' and r.get('content_type')=='unknown'
            and r.get('coverage_state')=='confirmed' and r['provider'] in ('Codex web','Brave news','Brave web')
            and 'source_profile' not in r.get('provenance',{}).get('publication_check',{}))]
        candidates.sort(key=lambda r:(r.get('coverage_state')!='confirmed',bool(platform(r['url'])),evidence_priority(r)))
        started=time.monotonic()
        for index,row in enumerate(candidates[:5]):
            if cancel.is_set() or time.monotonic()-started>50:break
            self.progress(actor,{'stage':f'Checking publication dates ({index+1}/{min(5,len(candidates))})'})
            try:metadata=fetch_metadata(row['url'],self.s,self.store,cancel)
            except Exception as exc:
                metadata={'published':None,'status':str(exc) if isinstance(exc,DeskError) else 'Public metadata unavailable; no access bypass attempted.'}
            # Apply metadata to all current observations of this article; preserve evidence and assessments.
            for item in self.store.list(actor,'finding'):
                if item.get('run_id')!=row.get('run_id') or item['canonical']!=row['canonical']:continue
                item.setdefault('provenance',{})['publication_check']=metadata
                if metadata.get('published'):
                    item.update(published=metadata['published'],date_kind='publication')
                    item['version_id']=version(item)
                self.store.update(actor,item['id'],item)

    def analysis_key(self,actor,row,monitor):
        return digest(json.dumps({'article':row['canonical'],'version':version(row),'scope':scope_key(monitor),
            'publisher_metadata':row.get('provenance',{}).get('publication_check',{}).get('source_profile',{}),
            'workspace':actor.workspace,'owner':actor.user,'model':self.s.model,'mode':self.s.mode,'analysis_version':6},sort_keys=True))

    def continue_research(self,actor,monitor_id,cancel,verify_dates=True,exclude_ids=None):
        from .discovery import finding_selection
        self.store.authorize(actor,owner=True)
        monitor=self.store.get(actor,monitor_id,'monitor')
        if verify_dates and self.s.mode=='live' and not cancel.is_set():self.verify_dates(actor,monitor_id,cancel)
        rows=finding_selection(self.store,actor,{'monitor':monitor_id,'filter':'all','snapshot':time.time()})['rows']
        pending=[r for r in rows if (not r.get('analysis') or r.get('analysis_scope_key')!=scope_key(monitor) or (self.s.mode=='live' and r.get('content_type')=='unknown'
            and r.get('coverage_key')!=self.analysis_key(actor,r,monitor))) and r['id'] not in (exclude_ids or set())]
        from .research import evidence_priority
        pending.sort(key=lambda r:(0 if r.get('coverage_state')=='confirmed' else 1,
            0 if r.get('relevance')=='relevant' else 1,evidence_priority(r)))
        # Deterministic bounded batch across the entire run, never the visible page.
        batch=[];size=0
        batch_limit=min(self.s.ai_items,max(1,self.s.output_job//(700+250*len(monitor['messages']))))
        for row in pending:
            item_size=len(json.dumps(row['text']))+len(row['title'])+300
            if len(batch)>=batch_limit or size+item_size>self.s.input_job-6000:break
            self.allowed_source(row);batch.append(row['id']);size+=item_size
        if batch:
            typed=[r for r in pending if r['id'] in batch and r.get('analysis') and r.get('content_type')=='unknown']
            if typed and self.s.mode=='live' and self.analyzer and hasattr(self.analyzer,'classify_coverage'):
                batch=[r['id'] for r in typed]
                self.classify_coverage(actor,monitor,typed,cancel)
            else:self.analyze(actor,monitor_id,batch,cancel,partial=True)
        selection=finding_selection(self.store,actor,{'monitor':monitor_id,'filter':'all','snapshot':time.time()})
        remaining=sum(not r.get('analysis') for r in selection['rows'])
        outcome='Needs review' if selection['counts']['review'] else 'Assessed'
        runs=[r for r in self.store.list(actor,'run') if r['monitor_id']==monitor_id and r.get('scope',{}).get('key')==scope_key(monitor)]
        if runs:
            run=runs[0];run.update(pending_count=remaining,assessed_count=len(selection['rows'])-remaining,counts=selection['counts'],outcome=outcome)
            if batch and run.get('error','').startswith('AI '):
                run.setdefault('previous_assessment_errors',[]).append({'at':time.time(),'error':run.pop('error')})
            self.store.update(actor,run['id'],run)
        self.store.preferences(actor,{'snapshot':time.time(),'page':0})
        self.progress(actor,{'outcome':outcome,'stage':'Evidence assessed'})
        return batch

    def classify_coverage(self,actor,monitor,sources,cancel):
        from .models import CoverageAnalysis
        self.store.authorize(actor,owner=True)
        for source in sources:self.allowed_source(source)
        result=self.analyzer.classify_coverage(sources,cancel)
        try:result=CoverageAnalysis.model_validate(result).model_dump()
        except ValueError:raise DeskError('Content-type assessment did not match its schema.') from None
        if {r['source_id'] for r in result['findings']}!={s['id'] for s in sources} or len(result['findings'])!=len(sources):raise DeskError('Content-type assessment must cover each selected source once.')
        validated=validate_analysis({'findings':[{'source_id':r['source_id'],'coverage':r['coverage'],'relevance':'uncertain',
            'campaign_relevance':'not_applicable','explanation':'Separate content-type assessment','messages':[]} for r in result['findings']]},sources,[])
        if cancel.is_set():raise DeskError('Cancelled; no content-type assessment saved.')
        if self.store.get(actor,monitor['id'],'monitor')['revision']!=monitor['revision']:raise DeskError('Search scope changed; content types were not saved.')
        for item in validated['findings']:
            row=self.store.get(actor,item['source_id'],'finding');self.allowed_source(row)
            row.update(coverage=item['coverage'],coverage_key=self.analysis_key(actor,row,monitor),coverage_assessed_at=time.time())
            self.store.update(actor,row['id'],row)

    def manual(self,actor,values):
        self.store.authorize(actor)
        if not values.get('title','').strip():
            raise DeskError('Give the source a title.')
        row = record(values['title'],values['url'],values.get('text',''), 'Manual contribution',
            {'submitted_by':actor.user,'verification':'User-supplied text; publisher text not verified'},access='user-supplied excerpt')
        row['monitor_id'] = values.get('monitor_id','')
        if row['monitor_id']:
            monitor=self.store.get(actor,row['monitor_id'],'monitor')
            row.update(monitor_revision=monitor['revision'],scope_key=scope_key(monitor))
        row['comment'] = values.get('comment','')[:2000]
        return self.store.create(actor,'finding',row)

    def allowed_source(self,row):
        if row['expires']<=time.time():
            raise DeskError('A source expired. Select current findings.')
        if row['provider'].startswith('Brave') and not self.s.storage_allowed:
            raise DeskError('Brave storage permission is no longer enabled.')
        if row['provider'].startswith('YouTube'):
            raise DeskError('YouTube metadata is not enabled for AI or briefing export.')

    def analyze(self,actor,monitor_id,ids,cancel,partial=False):
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
            if row.get('scope_key')!=scope_key(monitor) or row.get('monitor_revision')!=monitor['revision']:
                raise DeskError('This evidence belongs to a previous search scope. Refresh the current search.')
        from .research import remap
        # One target per article, regardless of how many observation IDs arrive.
        sources=list({r['canonical']:r for r in sources}.values())
        keys={r['id']:self.analysis_key(actor,r,monitor) for r in sources}
        reusable={}
        for old in self.store.list(actor,'finding'):
            if old.get('analysis') and old.get('analysis_key') in keys.values():
                self.allowed_source(old)
                reusable[old['analysis_key']]=old['analysis']
        pending=[r for r in sources if keys[r['id']] not in reusable]
        findings=[remap(reusable[keys[r['id']]],r['id']) for r in sources if keys[r['id']] in reusable]
        for item in findings:item.pop('supporting_quote',None)
        if pending:
            if self.s.mode=='demo':
                result={'findings':[{'source_id':r['id'],'relevance':'uncertain','campaign_relevance':'uncertain' if monitor['campaign'] else 'not_applicable',
                    'explanation':'Fixture assessment; no live inference.','messages':[{'message':m,'label':'insufficient_evidence',
                    'explanation':'Demo fixture only.','evidence':[]} for m in monitor['messages']]} for r in pending]}
            else:
                if not self.analyzer:raise DeskError('AI unavailable. Run the local runtime status helper.')
                result=self.analyzer.analyze(pending,monitor,cancel)
                self.runtime_state='Ready'
            if partial:
                returned=result.get('findings',[]) if isinstance(result,dict) else []
                for source in pending:
                    matches=[f for f in returned if isinstance(f,dict) and f.get('source_id')==source['id']]
                    try:findings.extend(validate_analysis({'findings':matches},[source],monitor['messages'])['findings'])
                    except DeskError:
                        source['analysis_error']='Assessment did not pass evidence checks; source retained for review.'
                        self.store.update(actor,source['id'],source)
            else:findings.extend(validate_analysis(result,pending,monitor['messages'])['findings'])
        validated_sources=[r for r in sources if any(f['source_id']==r['id'] for f in findings)] if partial else sources
        result=validate_analysis({'findings':findings},validated_sources,monitor['messages']) if findings else {'findings':[]}
        if cancel.is_set():raise DeskError('Cancelled; no assessment saved.')
        self.store.authorize(actor,owner=True)
        if self.store.get(actor,monitor_id,'monitor')['revision']!=monitor['revision']:
            raise DeskError('Monitor changed while AI was working. Results were not saved.')
        for assessment in result['findings']:
            row=self.store.get(actor,assessment['source_id'],'finding');self.allowed_source(row)
            row.pop('analysis_error',None)
            if row.get('analysis_key')!=keys[row['id']]:
                row.pop('coverage',None);row.pop('coverage_key',None)
            row.update(analysis=assessment,analysis_scope_key=scope_key(monitor),analysis_scope_id=row.get('scope_id'),
                analysis_status='Fixture assessment' if self.s.mode=='demo' else 'AI assessed',analysis_key=keys[row['id']])
            self.store.update(actor,row['id'],row)
        return result

    def finding_detail(self,actor,ident):
        row=self.store.get(actor,ident,'finding')
        row['observations']=[r for r in self.store.list(actor,'finding') if r['canonical']==row['canonical'] and r['owner']==row['owner']]
        if row.get('monitor_id'):
            from .overview import project_articles
            monitor=self.store.get(actor,row['monitor_id'],'monitor')
            row['can_review']=actor.user==self.s.owner and row.get('scope_key')==scope_key(monitor) and row.get('monitor_revision')==monitor['revision']
            match=next((r for r in project_articles(self.store,actor,monitor)['rows'] if any(o['id']==ident for o in r['observations'])),None)
            if match:
                for key in ('published','date_kind','date_precision','relevance','projection_expires','content_type','outlet_name','outlet_context','outlet_evidence','classification_evidence','correction_audit','coverage_state','assessment_status','date_status','redistribution'):
                    if key in match:row[key]=match[key]
        return row

    def save(self,actor,source_id,visibility,confirmed=False,include_analysis=False):
        source = self.finding_detail(actor,source_id)
        source['expires']=min(source['expires'],source.get('projection_expires',source['expires']))
        self.allowed_source(source)
        if visibility == 'shared' and not confirmed:
            raise DeskError('Confirm disclosure to everyone in this workspace.')
        # Copy evidence without private criteria, query provenance, analysis or comments.
        # Private assessments stay in Explore; sharing never exposes monitor messages.
        with self.store.lock:
            existing = next((b for b in self.store.list(actor,'board') if b['canonical']==source['canonical'] and b['visibility']==visibility and (visibility=='shared' or b['owner']==actor.user)),None)
            if existing:
                if include_analysis and source.get('analysis'):
                    if existing['hash']!=source['hash'] or existing['title']!=source['title']:
                        raise DeskError('This article is already saved with an earlier evidence snapshot. Its discussion is preserved; a newer assessment cannot replace different source text.')
                    existing.update(analysis=source['analysis'],analysis_status=source['analysis_status'],
                        assessment_disclosure='Creator explicitly included this assessment and its message wording.')
                    return self.store.update(actor,existing['id'],existing)
                return existing
            selected = {k:source[k] for k in ('title','url','canonical','text','provider','published','retrieved','access','hash')}
            selected.update(source_kind=source.get('source_kind','Web page'),date_kind=source.get('date_kind','unknown'))
            selected['full_title']=source.get('full_title',source['title'])
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
        return self.store.create(actor,'briefing',{'title':boards[0]['title'][:95]+' | '+time.strftime('%d %b %Y, %H:%M'),
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
        if jobs:
            restored={**jobs[0],'cancel':threading.Event()}
            former_cap=('validation cap is reached','Usage limit: this research path needs','Usage limit: research needs')
            if any(marker in restored.get('error','') for marker in former_cap):
                # Retain the original job record as history, not an active error.
                restored.pop('error',None)
                restored['state']='Stopped at former app cap'
            self.jobs[actor.user]=restored
            notice=self.store.preferences(actor).get('notice','')
            if any(marker in notice for marker in former_cap):self.store.preferences(actor,{'notice':''})

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

    def edit_draft(self,actor,ident,text,revision,title=None):
        with self.store.lock:
            d = self.store.get(actor,ident,'briefing')
            if d.get('overview'):raise DeskError('Coverage snapshots are frozen. Correct the source evidence and create a new snapshot.')
            if d['revision'] != revision or d['status'] != 'Draft':
                raise DeskError('This draft changed. Reopen it before editing.')
            if not text.strip() or len(text)>2800:
                raise DeskError('Use 1–2,800 characters.')
            d.update(text=text,revision=revision+1)
            if title is not None:
                if not title.strip() or len(title)>150:raise DeskError('Use a title of 1 to 150 characters.')
                d['title']=title.strip()
            d['edits'].append({'author':actor.user,'at':time.time()})
            return self.store.update(actor,ident,d)

    def preview(self,actor,ident):
        from .ui import briefing_message
        self.store.authorize(actor,owner=True)
        d = self.store.get(actor,ident,'briefing')
        if d['status']!='Draft':
            raise DeskError('This briefing was already sent or its delivery is uncertain.')
        self.validate_overview_snapshot(actor,d)
        for ident in d['board_ids']:
            self.briefing_source(actor,d,ident)
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
            self.validate_overview_snapshot(actor,d)
            message=briefing_message(d)
            if p['used'] or d['status']!='Draft' or d['revision']!=p['revision'] or digest(json.dumps(message,sort_keys=True))!=p['digest'] or p['channel']!=self.s.channel:
                raise DeskError('Preview expired or changed. Open a fresh preview.')
            for ident in d['board_ids']:
                self.briefing_source(actor,d,ident)
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
        if d.get('overview'):
            # The exact confirmation explicitly includes workspace disclosure.
            self.store.db.execute("UPDATE objects SET visibility='shared' WHERE id=?",(d['id'],))
        return self.store.update(actor,d['id'],d)
