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
        path=values.get('research_path','AI-planned Brave')
        if path not in ('AI-planned Brave','Codex native web'):raise DeskError('Unknown research path.')
        data['research_path']=path
        data['scope_key']=scope_key(data)
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
            run.update(count=len(saved),outcome='Partial results' if saved else 'Unavailable',checked=time.time())
            self.store.update(actor,run['id'],run)
            self.progress(actor,{'outcome':run['outcome'],'retained':len(saved)})
            raise

    def research(self,actor,monitor_id,cancel):
        """One explicit owner action; independent of the current results page."""
        self.store.authorize(actor,owner=True)
        self.progress(actor,{'monitor_id':monitor_id,'stage':'Checking research capacity'})
        if self.s.mode=='demo':
            self.refresh(actor,monitor_id,cancel)
            return self.continue_research(actor,monitor_id,cancel)
        if self.store.get(actor,monitor_id,'monitor').get('research_path','AI-planned Brave')=='AI-planned Brave':
            return self.planned_research(actor,monitor_id,cancel)
        require_live(self.s)
        if not self.analyzer:raise DeskError('AI unavailable. Run the runtime status helper.')
        from .research import registry,assessments,remap
        monitor=self.store.get(actor,monitor_id,'monitor');scope=snapshot(monitor)
        run=self.store.create(actor,'run',{'monitor_id':monitor_id,'scope':scope,'path':'Codex native web',
            'mode':self.s.mode,'statuses':[],'count':0,'checked':time.time(),'outcome':'Researching',
            'enabled_sources':monitor['sources'],'reserved_source_slots':3})
        self.progress(actor,{'stage':'Understanding scope and searching','monitor_id':monitor_id,'run_id':run['id'],'retained':0})
        saved=[]
        try:
            envelope=self.analyzer.research(scope,cancel)
            rows=registry(envelope)
            checked,error=assessments(envelope,rows,monitor['messages'])
            if envelope.get('interrupted'):error=envelope['interrupted']
            # Verify one promising article's date through bounded public metadata
            # retrieval. Model-authored dates never enter the eligibility gate.
            target=next((r for r in rows if checked.get(r.get('source_ref'),{}).get('relevance')=='relevant' and not r.get('published')),None)
            if target and not cancel.is_set():
                from .public_evidence import fetch_metadata
                try:
                    metadata=fetch_metadata(target['url'],self.s,self.store,cancel)
                    for row in rows:
                        if row['canonical']==target['canonical']:
                            row['provenance']['publication_check']=metadata
                            if metadata['published']:row.update(published=metadata['published'],date_kind='publication')
                except Exception as exc:
                    target['provenance']['publication_check']={'status':str(exc) if isinstance(exc,DeskError) else 'Public metadata unavailable; no access bypass attempted.'}
            for row in rows:
                row.update(monitor_id=monitor_id,monitor_revision=monitor['revision'],scope_key=scope['key'],
                    scope_id=scope['id'],run_id=run['id'])
                saved.append(self.store.create(actor,'finding',row))
            # A changed scope remains inspectable as history, never current results.
            current=self.store.get(actor,monitor_id,'monitor')['revision']==monitor['revision']
            cached={r.get('analysis_key'):r['analysis'] for r in self.store.list(actor,'finding')
                if r.get('analysis_key') and r.get('analysis') and r['owner']==actor.user}
            for row in saved:
                a=checked.get(row.get('source_ref')) or cached.get(self.analysis_key(actor,row,monitor))
                if a and not cancel.is_set():
                    row.update(analysis=remap(a,row['id']),analysis_scope_key=scope['key'],
                        analysis_scope_id=scope['id'],analysis_status='AI assessed',analysis_key=self.analysis_key(actor,row,monitor))
                    self.store.update(actor,row['id'],row)
            unique={r['canonical'] for r in saved}
            assessed={r['canonical'] for r in saved if r.get('analysis')}
            outcome='Cancelled' if cancel.is_set() else 'Previous scope' if not current else 'Needs review' if error or unique-assessed else 'Assessed'
            run.update(count=len(saved),unique_count=len(unique),assessed_count=len(assessed),pending_count=len(unique-assessed),
                outcome=outcome,interpretation=envelope.get('result',{}).get('interpretation',''),
                observed_actions=[{'id':e.get('id'),'query':e.get('query'),'action':e.get('action'),
                    'returned_results':len(e.get('results') or [])} for e in envelope.get('observed',[])],
                error=error,limited=envelope.get('limited',False),checked=time.time())
            self.store.update(actor,run['id'],run)
            self.progress(actor,{'stage':'Evidence assessed','outcome':outcome,'retained':len(unique)})
            if current:self.store.preferences(actor,{'snapshot':time.time(),'page':0,'history':'current','notice':''})
            return saved
        except Exception:
            run.update(count=len(saved),outcome='Partial results' if saved else 'Unavailable',checked=time.time())
            self.store.update(actor,run['id'],run)
            self.progress(actor,{'outcome':run['outcome'],'retained':len(saved)})
            raise

    def planned_research(self,actor,monitor_id,cancel):
        from dataclasses import replace
        from .public_evidence import fetch_metadata
        self.store.authorize(actor,owner=True);require_live(self.s)
        if not self.analyzer:raise DeskError('AI unavailable. Run the runtime status helper.')
        if not self.s.brave_key or not self.s.storage_allowed:raise DeskError('AI-planned Brave requires a configured Brave key and owner-supplied storage permission.')
        usage=self.store.budgets()
        if usage['ai']['cap']-usage['ai']['used']<2 or usage['source']['cap']-usage['source']['used']<2:
            raise DeskError('Usage limit: this research path needs two AI jobs and at least two source requests. Nothing started.')
        monitor=self.store.get(actor,monitor_id,'monitor');scope=snapshot(monitor)
        run=self.store.create(actor,'run',{'monitor_id':monitor_id,'scope':scope,'path':'AI-planned Brave','mode':self.s.mode,
            'statuses':[],'count':0,'checked':time.time(),'outcome':'Researching','calls_cap':2,'pages_cap':1,'enabled_sources':monitor['sources']})
        self.progress(actor,{'stage':'Understanding the search','monitor_id':monitor_id,'run_id':run['id'],'retained':0})
        saved=[];statuses=[]
        try:
            plan=self.analyzer.plan(monitor,cancel,max_queries=2)
            run.update(interpretation=plan['interpretation'],plan=plan['queries']);self.store.update(actor,run['id'],run)
            provider=Brave(replace(self.s,calls=1,pages=1,results=min(10,self.s.results)),self.store)
            def save_page(rows,updates):
                for row in rows:
                    # Brave page_age can mean last modified; it is not verified publication.
                    row.update(date_kind='page_age',monitor_id=monitor_id,monitor_revision=monitor['revision'],
                        scope_key=scope['key'],scope_id=scope['id'],run_id=run['id'])
                    saved.append(self.store.create(actor,'finding',row))
                run.update(count=len(saved),statuses=statuses+updates);self.store.update(actor,run['id'],run)
            for query in sorted(plan['queries'],key=lambda q:0 if (q['purpose']=='focus' and monitor.get('campaign')) or (q['purpose']=='broad' and not monitor.get('campaign')) else 1):
                if cancel.is_set():break
                self.progress(actor,{'stage':'Searching: '+query['purpose'],'retained':len(saved)})
                _,updates=provider.retrieve({**monitor,'sources':[query['target']],
                    '_planned_query':query['query'],'_planned_purpose':query['purpose']},cancel,on_page=save_page)
                statuses.extend(updates)
            unique=list({r['canonical']:r for r in saved}.values())
            # Verify at most two publication dates, with independent request charging.
            for row in unique[:2]:
                if cancel.is_set():break
                try:
                    metadata=fetch_metadata(row['url'],self.s,self.store,cancel)
                    row['provenance']['publication_check']=metadata
                    if metadata['published']:row.update(published=metadata['published'],date_kind='publication',version_id=version({**row,'published':metadata['published'],'date_kind':'publication'}))
                except Exception as exc:
                    row['provenance']['publication_check']={'status':str(exc) if isinstance(exc,DeskError) else 'Public metadata unavailable; no access bypass attempted.'}
                self.store.update(actor,row['id'],row)
            if self.store.get(actor,monitor_id,'monitor')['revision']!=monitor['revision']:
                raise DeskError('Search changed during collection. Earlier sources remain in previous-scope history.')
            self.progress(actor,{'stage':'Assessing unique evidence','retained':len(unique)})
            if not cancel.is_set():self.continue_research(actor,monitor_id,cancel)
            from .discovery import finding_selection
            projection=finding_selection(self.store,actor,{'monitor':monitor_id,'filter':'all','snapshot':time.time()})
            assessed=sum(bool(r.get('analysis')) for r in projection['rows'])
            run.update(count=len(saved),unique_count=len(unique),assessed_count=assessed,pending_count=len(unique)-assessed,
                outcome='Cancelled' if cancel.is_set() else 'Needs review' if assessed<len(unique) else 'Assessed',
                statuses=statuses,checked=time.time())
            self.store.update(actor,run['id'],run)
            self.progress(actor,{'outcome':run['outcome'],'stage':'Evidence assessed','retained':len(unique)})
            self.store.preferences(actor,{'snapshot':time.time(),'page':0,'history':'current'})
            return saved
        except Exception:
            run.update(count=len(saved),outcome='Partial results' if saved else 'Unavailable',checked=time.time())
            self.store.update(actor,run['id'],run);self.progress(actor,{'outcome':run['outcome'],'retained':len(saved)})
            self.store.preferences(actor,{'snapshot':time.time()})
            raise

    def analysis_key(self,actor,row,monitor):
        return digest(json.dumps({'article':row['canonical'],'version':version(row),'scope':scope_key(monitor),
            'workspace':actor.workspace,'owner':actor.user,'model':self.s.model,'mode':self.s.mode,'analysis_version':3},sort_keys=True))

    def continue_research(self,actor,monitor_id,cancel):
        from .discovery import finding_selection
        self.store.authorize(actor,owner=True)
        monitor=self.store.get(actor,monitor_id,'monitor')
        rows=finding_selection(self.store,actor,{'monitor':monitor_id,'filter':'all','snapshot':time.time()})['rows']
        pending=[r for r in rows if not r.get('analysis') or r.get('analysis_scope_key')!=scope_key(monitor)]
        # Deterministic bounded batch across the entire run, never the visible page.
        batch=[];size=0
        for row in pending:
            item_size=len(json.dumps(row['text']))+len(row['title'])+300
            if len(batch)>=self.s.ai_items or size+item_size>self.s.input_job-6000:break
            self.allowed_source(row);batch.append(row['id']);size+=item_size
        if batch:self.analyze(actor,monitor_id,batch,cancel)
        runs=[r for r in self.store.list(actor,'run') if r['monitor_id']==monitor_id and r.get('scope',{}).get('key')==scope_key(monitor)]
        if runs:
            run=runs[0];run.update(pending_count=max(0,len(pending)-len(batch)),outcome='Needs review' if len(pending)>len(batch) else 'Assessed')
            self.store.update(actor,run['id'],run)
        self.store.preferences(actor,{'snapshot':time.time(),'page':0})
        self.progress(actor,{'outcome':'Needs review' if len(pending)>len(batch) else 'Assessed','stage':'Evidence assessed'})
        return batch

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
            findings.extend(validate_analysis(result,pending,monitor['messages'])['findings'])
        result=validate_analysis({'findings':findings},sources,monitor['messages'])
        if cancel.is_set():raise DeskError('Cancelled; no assessment saved.')
        self.store.authorize(actor,owner=True)
        if self.store.get(actor,monitor_id,'monitor')['revision']!=monitor['revision']:
            raise DeskError('Monitor changed while AI was working. Results were not saved.')
        for assessment in result['findings']:
            row=self.store.get(actor,assessment['source_id'],'finding');self.allowed_source(row)
            row.update(analysis=assessment,analysis_scope_key=scope_key(monitor),analysis_scope_id=row.get('scope_id'),
                analysis_status='Fixture assessment' if self.s.mode=='demo' else 'AI assessed',analysis_key=keys[row['id']])
            self.store.update(actor,row['id'],row)
        return result

    def finding_detail(self,actor,ident):
        row=self.store.get(actor,ident,'finding')
        row['observations']=[r for r in self.store.list(actor,'finding') if r['canonical']==row['canonical'] and r['owner']==row['owner']]
        return row

    def save(self,actor,source_id,visibility,confirmed=False,include_analysis=False):
        source = self.store.get(actor,source_id,'finding')
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

    def edit_draft(self,actor,ident,text,revision,title=None):
        with self.store.lock:
            d = self.store.get(actor,ident,'briefing')
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
