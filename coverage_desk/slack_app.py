import json
import logging
import re
import socket
import threading
import time
from pathlib import Path
from slack_bolt import App
from slack_bolt.authorization import AuthorizeResult
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from .config import DeskError, ROOT
from .store import Actor
from .service import Desk
from .runtime import CodexAnalyzer
from . import ui
from .scheduling import Scheduler
from .discovery import finding_selection, DEFAULT_SOURCES, SOURCE_CHOICES

def bind(s):
    if not (s.bot_token and s.app_token and s.owner):
        raise DeskError('Configure Slack bot token, app token and owner ID locally.')
    client=WebClient(token=s.bot_token,retry_handlers=[],timeout=15)
    try:
        result=client.auth_test()
        if s.workspace and result['team_id']!=s.workspace:
            raise DeskError('Configured workspace does not match the Slack installation.')
        s.workspace=result['team_id']
        client.coverage_identity={'bot_id':result.get('bot_id'),'user_id':result.get('user_id')}
        return client,result.get('app_id','')
    except DeskError:
        raise
    except Exception:
        raise DeskError('Slack authentication failed. Check the bot installation and local token.') from None

def create_app(s,store,client):
    desk=Desk(s,store,CodexAnalyzer(s,store))
    scheduler=Scheduler(desk,Actor(s.workspace,s.owner))
    desk.scheduler=scheduler
    # Socket Mode authenticates envelopes; Bolt handles ack/event dispatch.
    def authorize(enterprise_id,team_id,user_id):
        if team_id!=s.workspace:return None
        identity=getattr(client,'coverage_identity',{})
        return AuthorizeResult(enterprise_id=enterprise_id,team_id=team_id,bot_token=s.bot_token,
            bot_id=identity.get('bot_id'),bot_user_id=identity.get('user_id'))
    app=App(client=client,authorize=authorize,token_verification_enabled=False)
    publish_locks={}
    def actor_of(body):
        team=body.get('team_id') or body.get('team',{}).get('id')
        user=body.get('user_id') or body.get('user',{}).get('id') or body.get('event',{}).get('user')
        a=Actor(team,user)
        store.authorize(a)
        return a
    def home(actor,notice=None):
        lock=publish_locks.setdefault(actor.user,threading.RLock())
        with lock:
            if notice is not None:store.preferences(actor,{'notice':notice})
            try:
                view=ui.home(desk,actor)
                try:client.views_publish(user_id=actor.user,view=view)
                except Exception as exc:
                    if getattr(exc,'response',{}).get('error') not in ('invalid_blocks','invalid_arguments') or not any(b['type']=='data_visualization' for b in view['blocks']):raise
                    store.create(actor,'slack_capabilities',{'home':{'data_visualization':{'supported':False}},'checked':time.time()})
                    client.views_publish(user_id=actor.user,view=ui.home(desk,actor))
            except Exception:
                logging.getLogger('coverage').warning('App Home update unavailable; reopen Home to refresh.')
    last_progress={}
    def changed(actor):
        job=desk.jobs.get(actor.user,{})
        now=time.monotonic()
        terminal=job.get('state') not in ('Working',)
        if terminal or now-last_progress.get(actor.user,0)>=2:
            last_progress[actor.user]=now
            if job.get('state') not in ('Queued','Working'):
                p=store.preferences(actor)
                changes={}
                if p.get('notice','').startswith('Search saved. Collection is starting'):
                    changes['notice']=''
                if p.get('awaiting_first_collection')==job.get('monitor_id') and p.get('monitor')==job.get('monitor_id'):
                    changes.update(snapshot=time.time(),awaiting_first_collection='')
                if changes:store.preferences(actor,changes)
            home(actor)
    desk.changed=changed
    def open_modal(body,view):
        method=client.views_push if body.get('view',{}).get('type')=='modal' else client.views_open
        method(trigger_id=body['trigger_id'],view=view)
    def form_values(body):
        data={}
        for k,fields in body['view']['state']['values'].items():
            e=next(iter(fields.values()))
            if e.get('type')=='multi_static_select' or 'selected_options' in e:
                data[k]=[o['value'] for o in e.get('selected_options',[])]
            elif 'selected_option' in e:data[k]=(e.get('selected_option') or {}).get('value','')
            else:data[k]=e.get('selected_date') or e.get('value') or ''
        return data
    def metadata(body):return json.loads(body['view'].get('private_metadata') or '{}')
    def monitor_values(actor, body):
        meta=metadata(body)
        base=store.get(actor,meta['id'],'monitor') if meta.get('id') else {'sources':DEFAULT_SOURCES,'freshness':'pw','language':'en','country':'US'}
        if 'to' in base.get('freshness',''):base['custom_range']=base['freshness']
        base.update(meta.get('values',{}))
        base.update(form_values(body))
        for key in ('aliases','messages'):
            if isinstance(base.get(key,''),str):base[key]=[x.strip() for x in base.get(key,'').splitlines() if x.strip()]
        for key in ('domains','notes','campaign','custom_range'):base[key]=base.get(key) or ''
        if isinstance(base['sources'],str):base['sources']=['news','web'] if base['sources']=='both' else [base['sources']]
        if base['freshness']=='any':base['freshness']=''
        return base
    def monitor_errors(v):
        errors={}
        if not v.get('name','').strip():errors['name']='Enter a company, brand, or person.'
        if len(v.get('messages',[]))>8 or any(len(x)>500 for x in v.get('messages',[])):
            errors['messages']='Use up to eight messages, each under 500 characters.'
        if not v.get('sources') or any(x not in {value:label for label,value in SOURCE_CHOICES} for x in v['sources']):errors['sources']='Choose at least one source.'
        if v.get('custom_range'):
            from datetime import date
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}to\d{4}-\d{2}-\d{2}',v['custom_range']):raise ValueError()
                start,end=v['custom_range'].split('to')
                if date.fromisoformat(start)>date.fromisoformat(end):raise ValueError()
            except ValueError:errors['custom_range']='Use YYYY-MM-DDtoYYYY-MM-DD, earliest date first.'
        return errors

    @app.event('app_home_opened')
    def opened(body,ack):
        ack()
        try:
            actor=actor_of(body);store.preferences(actor,{'snapshot':time.time(),'page':0,'outlet_page':0});home(actor)
        except DeskError:pass
    @app.command('/coverage')
    def coverage(body,ack):
        ack('Open Coverage Desk → Home to explore, collaborate and preview briefings.')
        try:home(actor_of(body))
        except DeskError:pass
    @app.action(re.compile('.*'))
    def action(ack,body):
        ack()
        actor=None
        try:
            actor=actor_of(body)
            a=body['actions'][0]
            kind=a['action_id'];value=a.get('value') or (a.get('selected_option') or {}).get('value','')
            p=store.preferences(actor)
            if kind.startswith('nav_'):
                if value not in ('explore','board','briefings'):raise DeskError('Unknown view.')
                store.preferences(actor,{'tab':value,'page':0,'notice':''})
            elif kind.startswith('page_'):store.preferences(actor,{'page':max(0,int(value))})
            elif kind=='monitor_select':store.get(actor,value,'monitor');store.preferences(actor,{'monitor':value,'page':0,'snapshot':time.time(),'notice':'','outlet':'','outlet_page':0,'explore_view':'overview','content_type':'reporting','coverage_state':'confirmed'})
            elif kind.startswith('coverage_view_'):
                if value not in ('overview','articles'):raise DeskError('Unknown coverage view.')
                store.preferences(actor,{'explore_view':value,'page':0,'notice':''})
            elif kind=='coverage_category':
                from .overview import CONTENT_TYPES
                if value not in (*CONTENT_TYPES,'all'):raise DeskError('Unknown content type.')
                store.preferences(actor,{'content_type':value,'page':0,'outlet_page':0,'outlet':''})
            elif kind=='coverage_state':
                from .overview import STATES
                if value not in (*STATES,'all','attention'):raise DeskError('Unknown evidence state.')
                store.preferences(actor,{'coverage_state':value,'page':0})
            elif kind=='coverage_outlet':
                from .overview import coverage_overview
                monitor=store.get(actor,p['monitor'],'monitor')
                if value not in {o['id'] for o in coverage_overview(store,actor,monitor,p)['outlets']}:raise DeskError('This outlet is no longer in the selected overview.')
                store.preferences(actor,{'explore_view':'articles','outlet':value,'coverage_state':'confirmed','history':'current','source_filter':'all','page':0})
            elif kind in ('coverage_back','coverage_clear'):
                store.preferences(actor,{'explore_view':'overview' if kind=='coverage_back' else 'articles','outlet':'','page':0})
            elif kind.startswith('outlet_page_'):store.preferences(actor,{'outlet_page':max(0,int(value))})
            elif kind.startswith('coverage_review_state_'):
                from .overview import STATES
                if value not in (*STATES,'all','attention'):raise DeskError('Unknown evidence state.')
                store.preferences(actor,{'explore_view':'articles','content_type':'all','coverage_state':value,'history':'current','source_filter':'all','outlet':'','page':0})
            elif kind=='coverage_correct_field':
                from .overview_ui import correction_modal
                store.authorize(actor,owner=True)
                client.views_update(view_id=body['view']['id'],hash=body['view'].get('hash'),view=correction_modal(desk.finding_detail(actor,metadata(body)['id']),value,form_values(body).get('reason','')));return
            elif kind=='coverage_correct':
                from .overview_ui import correction_modal
                store.authorize(actor,owner=True)
                open_modal(body,correction_modal(desk.finding_detail(actor,value)));return
            elif kind=='overview_share':
                from .overview import coverage_overview,CONTENT_TYPES
                from .overview_ui import period
                store.authorize(actor,owner=True)
                monitor=store.get(actor,value,'monitor');overview=coverage_overview(store,actor,monitor,p)
                open_modal(body,ui.modal('Share coverage overview',[
                    ui.para(monitor['name']+' · '+(monitor.get('campaign') or 'General coverage')),
                    ui.para(period(overview['scope']['window'])+'\n'+str(overview['article_count'])+' articles / '+str(overview['outlet_count'])+' outlets · '+CONTENT_TYPES.get(overview['category'],'All content types')),
                    ui.para('This snapshot includes private client/campaign information, aggregate counts, outlet names, source links and excerpts. Publishing shares it in the configured public channel and makes the snapshot visible to everyone in this workspace. Monitor notes, queries and tracked messages are excluded. Nothing is posted until you confirm the exact preview next.'),
                    ui.input_select('disclosure','Include this information?',[('Keep private','no'),('Yes, prepare sharing preview','yes')],'no')],
                    'overview_share_submit',{'id':value,'category':overview['category'],'at':overview['at'],'scope_key':monitor['scope_key']},submit='Prepare preview'));return
            elif kind=='overview_review_snapshot':
                from .overview_ui import snapshot_modal
                open_modal(body,snapshot_modal(store.get(actor,value,'briefing')));return
            elif kind.startswith(('overview_sources_','overview_outlets_','overview_snapshot_')):
                from .overview_ui import snapshot_modal
                d=store.get(actor,metadata(body)['id'],'briefing')
                client.views_update(view_id=body['view']['id'],hash=body['view'].get('hash'),view=snapshot_modal(d,int(value),'outlets' if 'outlets' in kind else 'sources'));return
            elif kind=='board_filter':store.preferences(actor,{'board_filter':value,'page':0})
            elif kind=='result_filter':
                if value not in ('relevant','review','all'):raise DeskError('Unknown result view.')
                store.preferences(actor,{'filter':value,'page':0})
            elif kind=='search_options':
                row=store.get(actor,value,'monitor')
                controls=[ui.button('Add a source','manual')]
                if actor.user==s.owner:controls.extend([ui.button('Edit search','edit_monitor',value),ui.button('New search','new_monitor'),ui.button('Delete search','delete_monitor',value)])
                open_modal(body,ui.modal('Search options',[ui.para(row['name']),ui.para(row.get('interpretation') or row.get('campaign') or 'General coverage of this subject.'),ui.actions(*controls)]));return
            elif kind=='delete_monitor':
                store.authorize(actor,owner=True)
                row=store.get(actor,value,'monitor')
                open_modal(body,ui.modal('Delete search?',[
                    ui.para(row['name']),
                    ui.para('Delete this search, its collected results, search history and any schedule? This cannot be undone.'),
                    ui.para('Saved board findings, perspectives and briefings stay available. Usage history is preserved.')],
                    'delete_monitor_submit',{'id':value},submit='Delete search'));return
            elif kind=='clear_filters':store.preferences(actor,{'filter':'all','source_filter':'all','page':0,'snapshot':time.time(),'notice':''})
            elif kind=='show_new':store.preferences(actor,{'snapshot':time.time(),'page':0,'notice':''})
            elif kind=='tab_help':open_modal(body,ui.help_modal(value));return
            elif kind=='cancel':desk.cancel(actor)
            elif kind=='monitor_options':
                store.authorize(actor,owner=True)
                values=monitor_values(actor,body)
                client.views_update(view_id=body['view']['id'],hash=body['view']['hash'],view=ui.monitor_modal(values,expanded=value=='show'));return
            elif kind.startswith('detail_'):
                m=metadata(body);row=store.get(actor,m['id'],'board' if m['board'] else 'finding')
                if not m['board']:row=desk.finding_detail(actor,row['id'])
                tab=m['tab'] if kind.startswith('detail_page_') else value
                page=int(value) if kind.startswith('detail_page_') else 0
                client.views_update(view_id=body['view']['id'],hash=body['view']['hash'],view=ui.detail(row,m['board'],tab,page));return
            elif kind in ('new_monitor','edit_monitor'):
                store.authorize(actor,owner=True)
                open_modal(body,ui.monitor_modal(store.get(actor,value,'monitor') if kind=='edit_monitor' else None));return
            elif kind=='settings':open_modal(body,ui.settings_modal(desk,actor));return
            elif kind=='runtime_check':
                store.authorize(actor,owner=True)
                def check_runtime(cancel):
                    desk.runtime_state=desk.analyzer.status()['state']
                desk.submit(actor,'Checking AI connection',check_runtime,True,key=actor.user+':'+a.get('action_ts',body['trigger_id']))
            elif kind=='schedule':
                store.authorize(actor,owner=True)
                monitors=store.list(actor,'monitor')
                if not monitors:raise DeskError('Create a monitor before configuring a schedule.')
                selected=p['monitor'] or monitors[0]['id']
                current=next((x for x in store.list(actor,'schedule') if x['monitor_id']==selected),{})
                blocks=[ui.para('Optional scheduled source refresh. It creates a private, source-linked briefing preview only. It NEVER invokes AI or posts automatically. Destination on later owner confirmation: '+(s.channel or 'not configured')),
                    ui.input_select('monitor_id','Monitor',[(m['name'],m['id']) for m in monitors],selected),
                    ui.input_select('cadence','Cadence',[('Daily','daily'),('Weekly','weekly')],current.get('cadence','daily')),
                    ui.input_select('zone','Timezone',[(z,z) for z in ('UTC','America/New_York','Europe/London','America/Los_Angeles')],current.get('timezone','UTC')),
                    ui.input_select('hour','Local hour',[(f'{h:02d}:00',str(h)) for h in range(24)],str(current.get('hour',9))),
                    ui.input_select('enabled','Schedule state',[('Disabled','no'),('Enable preview preparation','yes')],'yes' if current.get('enabled') else 'no'),
                    ui.para('Local scheduling switch: '+('enabled' if s.schedules else 'disabled. Set ENABLE_SCHEDULED_DIGESTS=true locally and restart before enabling.'))]
                if current:blocks.append(ui.para(current['last_status']))
                open_modal(body,ui.modal('Schedule previews',blocks,'schedule_submit',submit='Confirm schedule'));return
            elif kind=='filters':open_modal(body,ui.filters_modal(p));return
            elif kind in ('inspect','inspect_board'):
                open_modal(body,ui.detail(store.get(actor,value,'board') if kind=='inspect_board' else desk.finding_detail(actor,value),kind=='inspect_board'));return
            elif kind in ('delete_board','delete_briefing'):
                item_kind='board' if kind=='delete_board' else 'briefing'
                row=desk.deletable_item(actor,value,item_kind)
                explanation=('Remove this saved finding and its board discussion. Existing briefings keep their source snapshots and included perspectives. The original Explore finding remains.' if item_kind=='board' else
                    'Remove this briefing and its saved previews from the app. Board findings stay. Any message already published in Slack remains in its channel.')
                if row['visibility']=='shared':explanation+=' This removes the shared item for everyone in this workspace.'
                open_modal(body,ui.modal('Delete saved finding?' if item_kind=='board' else 'Delete briefing?',
                    [ui.para(row['title']),ui.para(explanation)],'delete_item_submit',{'id':value,'kind':item_kind},submit='Delete'));return
            elif kind=='run_status':open_modal(body,ui.collection_modal(store.get(actor,value,'run')));return
            elif kind=='refresh':
                store.get(actor,value,'monitor')
                store.preferences(actor,{'notice':''})
                desk.submit(actor,'Researching coverage',lambda cancel:desk.research(actor,value,cancel),True,key=actor.user+':'+a.get('action_ts',body['trigger_id']))
            elif kind=='continue_research':
                desk.submit(actor,'Assessing pending evidence',lambda cancel:desk.complete_research(actor,value,cancel) if s.mode=='live' else desk.continue_research(actor,value,cancel),True,key=actor.user+':'+a.get('action_ts',body['trigger_id']))
            elif kind=='manual':
                open_modal(body,ui.modal('Add a source',[ui.context('User-submitted evidence. The app does not fetch this URL.'),ui.input_text('url','Source URL',max_length=1500),ui.input_text('title','Title'),ui.input_text('text','Available excerpt','',True,True,3000),ui.input_text('comment','Your private comment','',True,True,2000)],'manual_submit',{'monitor_id':p['monitor']}));return
            elif kind=='save':
                row=store.get(actor,value,'finding')
                open_modal(body,ui.modal('Save finding',[ui.para(row['title']),ui.input_select('visibility','Audience',[('Private to me','private'),('Shared with this workspace','shared')],'private'),ui.input_select('assessment','Include AI assessment?',[('Source evidence only','no'),('Include assessment and message wording','yes')],'no'),ui.para('Choosing Shared discloses this source to everyone in this workspace. Including AI also discloses the selected assessment and its message wording. Private monitor configuration, queries and notes remain private.')],'save_submit',{'id':value},submit='Save finding'));return
            elif kind in ('perspective','review'):
                row=store.get(actor,value,'board')
                blocks=[ui.para(row['title'])]
                if kind=='perspective':blocks.append(ui.input_text('text','Your perspective','',False,True,2000))
                blocks.append(ui.input_select('status','Review status',[(x,x) for x in ('New','Reviewed','Use in briefing')],row['status']))
                open_modal(body,ui.modal('Add perspective' if kind=='perspective' else 'Review status',blocks,'perspective_submit',{'id':value,'parent':{'id':body['view']['id'],'hash':body['view'].get('hash'),'meta':metadata(body)} if body.get('view',{}).get('type')=='modal' else None}));return
            elif kind=='new_briefing':
                store.authorize(actor,owner=True)
                rows=store.list(actor,'board')
                if not rows:raise DeskError('Save at least one finding to the Team board first.')
                selector={'type':'multi_static_select','action_id':'value','placeholder':ui.plain('Select up to five findings'),'max_selected_items':5,'options':[ui.option(r['title'],r['id']) for r in rows[:100]]}
                open_modal(body,ui.modal('Create briefing',[ui.context('Only selected public evidence goes to Codex. Team perspectives never enter AI inputs. Shared drafts require shared sources.'),{'type':'input','block_id':'ids','label':ui.plain('Board findings'),'element':selector},ui.input_select('ai','Draft method',[('AI-assisted, evidence-validated','yes'),('Source-linked draft without AI','no')],'yes')],'briefing_submit',submit='Create draft'));return
            elif kind=='draft_detail':
                d=store.get(actor,value,'briefing')
                from .overview_ui import snapshot_modal
                open_modal(body,snapshot_modal(d) if d.get('overview') else ui.modal('Briefing snapshot',ui.briefing_blocks(d)));return
            elif kind=='edit_draft':
                d=store.get(actor,value,'briefing')
                open_modal(body,ui.modal('Edit briefing',[ui.input_text('title','Title',d['title'],max_length=150),ui.input_text('text','Draft text',d['text'],False,True,2800),ui.context('Source links remain attached. Editing never invokes AI.')],'edit_draft_submit',{'id':value,'revision':d['revision']}));return
            elif kind=='preview':
                p=desk.preview(actor,value);d=store.get(actor,value,'briefing')
                blocks=[ui.para('Destination: '+s.channel+' · Public demo channel. Confirming sends the exact blocks below.'),*ui.briefing_blocks(d)]
                if d.get('overview'):
                    blocks.insert(1,ui.para('Publishing also makes the frozen snapshot workspace-visible, including private client/campaign information, aggregate counts and all included source excerpts. Review the full list before confirming.'))
                    blocks.append(ui.actions(ui.button('Review all included sources','overview_review_snapshot',d['id'])))
                open_modal(body,ui.modal('Confirm exact preview',blocks,'publish_submit',{'id':p['id']},submit='Publish'));return
            else:raise DeskError('Reopen Home to use the current controls.')
            home(actor)
        except Exception as exc:
            if actor:home(actor,str(exc) if isinstance(exc,DeskError) else 'That action could not finish. Reopen Home and try again.')
    @app.view(re.compile('.*'))
    def submission(ack,body):
        actor=None
        try:
            actor=actor_of(body);v=form_values(body);m=metadata(body);kind=body['view']['callback_id']
            if kind=='monitor_submit':
                store.authorize(actor,owner=True)
                v=monitor_values(actor,body)
                errors=monitor_errors(v)
                if errors:
                    ack(response_action='errors',errors=errors);return
        except DeskError as exc:
            ack()
            if actor:home(actor,str(exc))
            return
        if kind=='overview_share_submit':
            try:
                if v.get('disclosure')!='yes':raise DeskError('Choose Yes to include private aggregates and sources, or cancel to keep them private.')
                monitor=store.get(actor,m['id'],'monitor')
                if monitor['scope_key']!=m['scope_key']:raise DeskError('The search scope changed. Open a new overview preview.')
                if not store.claim('form:'+actor.user+':'+body['view']['id']+':'+body['view'].get('hash','')):
                    ack(response_action='clear');return
                d=desk.overview_snapshot(actor,m['id'],{'content_type':m['category'],'snapshot':m['at']},confirmed=True)
                preview=desk.preview(actor,d['id'])
                ack(response_action='update',view=ui.modal('Confirm exact preview',[
                    ui.para('Destination: '+s.channel+' · Public internal channel and workspace-visible snapshot. Confirming publishes the exact content below.'),
                    *ui.briefing_blocks(d),ui.actions(ui.button('Review all included sources','overview_review_snapshot',d['id']))],'publish_submit',{'id':preview['id']},submit='Publish'))
            except Exception as exc:ack(response_action='errors',errors={'disclosure':str(exc) if isinstance(exc,DeskError) else 'Could not prepare the preview. Try again from Home.'})
            return
        if kind in ('delete_monitor_submit','delete_item_submit'):ack(response_action='clear')
        else:ack()
        try:
            if not store.claim('form:'+actor.user+':'+body['view']['id']+':'+body['view'].get('hash','')):
                return
            if kind=='monitor_submit':
                row=desk.monitor(actor,v,m.get('id'))
                store.preferences(actor,{'monitor':row['id'],'outlet':'','outlet_page':0,'explore_view':'overview','content_type':'reporting','coverage_state':'confirmed','tab':'explore','filter':'relevant','history':'current','source_filter':'all','page':0,'snapshot':time.time(),'notice':''})
                try:desk.submit(actor,'Researching coverage',lambda cancel:desk.research(actor,row['id'],cancel),True,key='search:'+body['view']['id']+':'+body['view'].get('hash',''))
                except DeskError as exc:store.preferences(actor,{'notice':'Search saved. '+str(exc)+' Use Refresh when ready.'})
            elif kind=='delete_monitor_submit':
                desk.delete_monitor(actor,m['id'],confirmed=True)
                store.preferences(actor,{'notice':'Search deleted. Saved board findings and briefings were kept.'})
            elif kind=='delete_item_submit':
                desk.delete_item(actor,m['id'],m['kind'],confirmed=True)
                store.preferences(actor,{'tab':'board' if m['kind']=='board' else 'briefings','page':0,
                    'notice':'Saved finding deleted. Existing briefings were kept.' if m['kind']=='board' else 'Briefing deleted from the app. Published Slack messages were kept.'})
            elif kind=='coverage_correct_submit':
                if m.get('field')=='published':v['date_action']='set_day' if v.get('published') else 'unknown'
                desk.correct_coverage(actor,m['id'],v)
            elif kind=='filters_submit':store.preferences(actor,{'source_filter':v.get('source_filter','all'),'history':v.get('history','current'),
                'content_type':'all','coverage_state':'all','outlet':'','explore_view':'articles','page':0,'notice':''})
            elif kind=='manual_submit':
                v={k:(x or '') for k,x in v.items()};v['monitor_id']=m.get('monitor_id','')
                desk.manual(actor,v);store.preferences(actor,{'snapshot':time.time(),'notice':'Source added. Its excerpt is labeled user-supplied.'})
            elif kind=='save_submit':desk.save(actor,m['id'],v['visibility'],confirmed=True,include_analysis=v.get('assessment')=='yes');store.preferences(actor,{'notice':'Finding saved to the Team board.'})
            elif kind=='perspective_submit':
                row=desk.perspective(actor,m['id'],v.get('text') or '',v['status'])
                parent=m.get('parent')
                if parent:
                    try:client.views_update(view_id=parent['id'],hash=parent.get('hash'),view=ui.detail(row,True,'discussion'))
                    except Exception:pass
            elif kind=='briefing_submit':
                desk.submit(actor,'Creating briefing',lambda cancel:desk.draft(actor,v['ids'],cancel,use_ai=v.get('ai')=='yes'),True,key='draft:'+body['view']['id']+':'+body['view']['hash'])
                store.preferences(actor,{'tab':'briefings','page':0,'notice':'Draft requested. Review, edit, and preview before publishing.'})
            elif kind=='edit_draft_submit':desk.edit_draft(actor,m['id'],v['text'],m['revision'],v.get('title'))
            elif kind=='publish_submit':
                desk.submit(actor,'Publishing confirmed preview',lambda cancel:desk.publish(actor,m['id'],client),True,key='publish:'+m['id'])
            elif kind=='schedule_submit':
                scheduler.configure(actor,v['monitor_id'],v['cadence'],v['zone'],int(v['hour']),v['enabled']=='yes')
                store.preferences(actor,{'notice':'Schedule configuration saved. No automatic posts or AI.'})
            home(actor)
        except Exception as exc:
            if actor:home(actor,str(exc) if isinstance(exc,DeskError) else 'The form could not be saved. Reopen it from Home.')
    return app,desk,home

def run(s,store):
    from .runtime_worker import job_guard
    lifetime_guard=job_guard()
    # One local listener holds a single-instance lock. It accepts no requests.
    guard=socket.socket()
    try:guard.bind(('127.0.0.1',47831))
    except OSError:raise DeskError('Coverage Desk is already running (local single-instance port 47831).') from None
    client,_=bind(s)
    store.s.workspace=s.workspace
    store.migrate_research()
    store.migrate_overview()
    store.purge()
    app,desk,publish=create_app(s,store,client)
    owner_actor=Actor(s.workspace,s.owner)
    desk.adopt_native_research(owner_actor)
    desk.restore_jobs(owner_actor)
    desk.migrate_perspectives(owner_actor)
    if s.mode=='live':
        try:desk.runtime_state=desk.analyzer.status()['state']
        except DeskError:desk.runtime_state='Unavailable — run runtime-status locally'
    logging.getLogger('slack_bolt').setLevel(logging.CRITICAL)
    logging.getLogger('slack_sdk').setLevel(logging.CRITICAL)
    handler=SocketModeHandler(app,s.app_token)
    handler.connect()
    deadline=time.monotonic()+15
    while not handler.client.is_connected() and time.monotonic()<deadline:
        time.sleep(0.1)
    if not handler.client.is_connected():
        raise DeskError('Slack Socket Mode did not become ready. Check the app-level token and connection.')
    publish(Actor(s.workspace,s.owner))
    state=ROOT/'data/backend.json'
    import os
    state.write_text(json.dumps({'pid':os.getpid(),'started':time.time(),'ready':True,'workspace':s.workspace,'mode':s.mode}),encoding='utf-8')
    print('Coverage Desk ready: Socket Mode connected; owner App Home updated.',flush=True)
    try:
        while True:
            time.sleep(30)
            store.purge()
            try:desk.scheduler.tick()
            except Exception:logging.getLogger('coverage').warning('Schedule tick unavailable; no automatic retry or channel post.')
            state.write_text(json.dumps({'pid':os.getpid(),'started':time.time(),'ready':handler.client.is_connected(),'workspace':s.workspace,'mode':s.mode}),encoding='utf-8')
    finally:
        handler.close();guard.close();state.unlink(missing_ok=True)
