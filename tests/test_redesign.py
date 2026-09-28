"""Offline regression checks for the redesigned user journeys."""
import json
import threading
import time
from unittest.mock import Mock
import httpx
import pytest
from slack_bolt.request import BoltRequest
from slack_sdk import WebClient
from slack_sdk.models.views import View
from coverage_desk import ui
from coverage_desk.config import Settings, DeskError
from coverage_desk.discovery import platform, finding_selection, DEFAULT_SOURCES
from coverage_desk.service import Desk
from coverage_desk.slack_app import create_app
from coverage_desk.sources import Brave, record
from coverage_desk.store import Store, Actor


@pytest.fixture
def app_env():
    settings=Settings(owner='UOWNER',workspace='TEST',channel='CDEMO',bot_token='xoxb-fixture',app_token='xapp-fixture')
    store=Store(settings);client=WebClient(token=settings.bot_token)
    for method in ('auth_test','views_open','views_update','views_push','views_publish'):
        setattr(client,method,Mock(return_value={'ok':True,'team_id':'TEST','user_id':'BOT','bot_id':'BOT'}))
    app,desk,home=create_app(settings,store,client)
    yield app,desk,store,client,Actor('TEST','UOWNER')
    desk.pool.shutdown()


def await_true(predicate):
    until=time.monotonic()+2
    while not predicate() and time.monotonic()<until:time.sleep(.01)
    assert predicate()


def action(app,action_id,value='-',view=None):
    body={'type':'block_actions','team':{'id':'TEST'},'user':{'id':'UOWNER'},'trigger_id':'TRIGGER',
          'api_app_id':'APP','container':{'type':'view'},'view':view or {'type':'home','id':'HOME'},
          'actions':[{'type':'button','action_id':action_id,'value':value,'action_ts':str(time.time())}]}
    return app.dispatch(BoltRequest(body=body,mode='socket_mode'))


def form_view(values,meta=None,ident='FORM'):
    state={}
    for key,value in values.items():
        field={'type':'multi_static_select','selected_options':[{'value':x} for x in value]} if isinstance(value,list) else {'type':'plain_text_input','value':value}
        state[key]={'value':field}
    return {'type':'modal','id':ident,'hash':'hash','private_metadata':json.dumps(meta or {}),
            'callback_id':'monitor_submit','state':{'values':state}}


def submit(app,view):
    return app.dispatch(BoltRequest(body={'type':'view_submission','team':{'id':'TEST'},'user':{'id':'UOWNER'},
        'api_app_id':'APP','view':view},mode='socket_mode'))


def test_create_collect_once_and_show_results(app_env):
    app,d,st,c,o=app_env
    view=form_view({'name':'Acme','campaign':'','messages':'Repair products','freshness':'pw','sources':DEFAULT_SOURCES})
    assert submit(app,view).status==200
    await_true(lambda:len(st.list(o,'run'))==1 and d.jobs.get(o.user,{}).get('state')=='Ready')
    assert st.list(o,'monitor')[0]['sources']==DEFAULT_SOURCES
    assert len(finding_selection(st,o,st.preferences(o))['visible'])==1
    submit(app,view)
    assert len(st.list(o,'monitor'))==1
    assert st.budgets()['ai']['used']==st.budgets()['source']['used']==0


def test_form_inline_errors_do_not_create_search(app_env):
    app,d,st,c,o=app_env
    view=form_view({'name':'','sources':[],'messages':'\n'.join(['x']*9),'custom_range':'2026-03-01to2026-02-01'})
    response=submit(app,view)
    payload=json.loads(response.body)
    assert payload['response_action']=='errors'
    assert set(payload['errors'])=={'name','sources','messages','custom_range'}
    assert not st.list(o,'monitor')


def test_expand_collapse_preserves_advanced_fields_and_existing_sources(app_env):
    app,d,st,c,o=app_env
    m=d.monitor(o,{'name':'Acme','aliases':['AC'],'notes':'Not a region','domains':'acme.test','sources':['news'],'language':'fr','country':'CA'})
    original=ui.monitor_modal(m)
    meta=json.loads(original['private_metadata'])
    view=form_view({'name':'Acme changed','sources':['news'],'campaign':'Product','messages':'One\nTwo','freshness':'pm'},meta)
    action(app,'monitor_options','show',view)
    await_true(lambda:c.views_update.called)
    expanded=c.views_update.call_args.kwargs['view']
    fields={b['block_id']:b['element'] for b in expanded['blocks'] if b['type']=='input'}
    assert fields['notes']['initial_value']=='Not a region'
    assert fields['messages']['initial_value']=='One\nTwo'
    assert fields['language']['initial_option']['value']=='fr'
    meta=json.loads(expanded['private_metadata'])
    view=form_view({'name':'Acme changed','sources':['news'],'messages':'One\nTwo','freshness':'pm','notes':'Updated note','aliases':'AC\nACME'},meta)
    c.views_update.reset_mock();action(app,'monitor_options','hide',view)
    await_true(lambda:c.views_update.called)
    collapsed=c.views_update.call_args.kwargs['view'];meta=json.loads(collapsed['private_metadata'])
    assert meta['values']['notes']=='Updated note'
    submit(app,form_view({'name':'Acme changed','sources':['news'],'messages':'One\nTwo','freshness':'pm'},meta))
    await_true(lambda:st.get(o,m['id'])['name']=='Acme changed')
    assert st.get(o,m['id'])['notes']=='Updated note'
    assert st.get(o,m['id'])['sources']==['news']
    assert not st.list(o,'run')


def test_saved_search_survives_busy_worker(app_env):
    app,d,st,c,o=app_env
    d.jobs[o.user]={'state':'Working','label':'Existing work','cancel':threading.Event()}
    submit(app,form_view({'name':'Acme','sources':['news']}))
    await_true(lambda:'collection has not started' in st.preferences(o).get('notice',''))
    assert len(st.list(o,'monitor'))==1 and not st.list(o,'run')


@pytest.mark.parametrize('url,expected',[
    ('https://www.instagram.com/p/abc','instagram'),('https://mobile.twitter.com/name/status/1','x'),
    ('https://x.com/name','x'),('https://uk.linkedin.com/posts/a','linkedin'),
    ('https://instagram.com.evil.test/p/1',None),('https://notinstagram.com',None),
    ('https://youtu.be/123','youtube'),('https://example.org/x.com',None)])
def test_platform_classification(url,expected):
    assert platform(url)==expected


def test_analyze_matches_filtered_visible_page_without_fetch(app_env):
    app,d,st,c,o=app_env;m=d.monitor(o,{'name':'Acme'});d.analyze=Mock()
    for i in range(13):
        r=record(str(i),'https://www.linkedin.com/posts/'+str(i),'Acme','Brave web',{})
        r['monitor_id']=m['id'];r['analysis']={'relevance':'relevant' if i%2 else 'uncertain'}
        st.create(o,'finding',r)
    st.preferences(o,{'monitor':m['id'],'source_filter':'linkedin','filter':'relevant','page':1,'snapshot':time.time()})
    expected=[r['id'] for r in finding_selection(st,o,st.preferences(o))['visible']]
    action(app,'analyze_page',m['id']);await_true(lambda:d.analyze.called)
    assert d.analyze.call_args.args[2]==expected and len(expected)==1
    assert st.budgets()['source']['used']==0


def test_modal_switches_in_place_and_provenance_is_readable(app_env):
    app,d,st,c,o=app_env
    r=record('Title','https://example.org','Excerpt','Brave news',{'endpoint':'news','query':'"Acme"','page':0,'filters':{'freshness':'pm','country':'US','search_lang':'en','safesearch':'moderate'}})
    r=st.create(o,'finding',r)
    view=ui.detail(r);view.update(id='DETAIL',hash='HASH')
    action(app,'detail_source','source',view);await_true(lambda:c.views_update.called)
    updated=c.views_update.call_args.kwargs['view']
    text=' '.join(b.get('text',{}).get('text','') for b in updated['blocks'])
    assert 'Search terms: "Acme"' in text and 'Past month' in text
    assert 'Provenance:' not in text and '"endpoint"' not in text
    c.views_push.assert_not_called()
    assert c.views_update.call_args.kwargs['hash']=='HASH'


def test_names_are_mentions_but_note_content_never_is(app_env):
    app,d,st,c,o=app_env
    f=d.manual(o,{'title':'Title','url':'https://example.org','text':'Text'})
    b=d.save(o,f['id'],'shared',True)
    d.perspective(o,b['id'],'<!channel> <@UOTHER>')
    b=st.get(o,b['id']);v=ui.detail(b,True,'discussion')
    assert '<@UOWNER>' in json.dumps(v)
    dr=d.draft(o,[b['id']]);msg=ui.briefing_message(dr)
    assert '<@UOWNER>' in msg['text'] and '<@UOTHER>' not in msg['text'] and '<!channel>' not in msg['text']
    assert '&lt;@UOTHER&gt;' in msg['text']


def test_generated_attribution_migration_preserves_edited_prose(app_env):
    app,d,st,c,o=app_env
    f=d.manual(o,{'title':'Title','url':'https://example.org','text':'Text'});b=d.save(o,f['id'],'shared',True)
    d.perspective(o,b['id'],'Original note')
    dr=d.draft(o,[b['id']]);dr.pop('perspectives');dr.pop('perspective_count')
    dr['text']='Summary\n\nTeam perspective (not sent to AI)\nUOWNER: Original note';st.update(o,dr['id'],dr)
    old_preview=d.preview(o,dr['id'])
    edited=st.create(o,'briefing',{**dr,'text':'Human UOWNER: note','edits':[{'author':o.user}]},'shared')
    d.migrate_perspectives(o)
    assert st.get(o,dr['id'])['text']=='Summary'
    assert st.get(o,dr['id'])['perspectives'][0]['author']==o.user
    assert st.get(o,edited['id'])['text']=='Human UOWNER: note'
    with pytest.raises(DeskError):d.publish(o,old_preview['id'],Mock())


def live_mock_settings():
    return Settings(mode='live',allow_live=True,storage_allowed=True,brave_key='fixture',results=60,calls=5)


def test_social_first_pages_before_campaign_and_paging():
    s=live_mock_settings();st=Store(s);calls=[];events=[]
    def response(req):
        calls.append(str(req.url))
        rows=[{'title':'A','url':f'https://example.org/{i}','description':'Text'} for i in range(20)]
        return httpx.Response(200,json={'results':rows,'web':{'results':rows},'query':{'more_results_available':True}})
    rows,status=Brave(s,st,httpx.Client(transport=httpx.MockTransport(response))).retrieve(
        {'name':'Acme','campaign':'repair','sources':DEFAULT_SOURCES},threading.Event(),progress=events.append)
    assert len(calls)==5 and len(rows)==100
    decoded=[httpx.URL(c).params['q'] for c in calls]
    assert all('repair' not in q for q in decoded)
    assert 'site:instagram.com' in decoded[2] and 'site:x.com' in decoded[3] and 'site:linkedin.com' in decoded[4]
    assert any(x['status']=='Collection cap reached' for x in status)
    assert events[-1]['requests']==5 and events[-1]['retained']==100


@pytest.mark.parametrize('cancel_after_page',[False,True])
def test_partial_and_cancel_keep_each_page_once(cancel_after_page):
    s=live_mock_settings();st=Store(s);o=Actor('TEST','OWNER');cancel=threading.Event();counter=[]
    def response(req):
        counter.append(1)
        if len(counter)>1:return httpx.Response(429)
        if cancel_after_page:cancel.set()
        return httpx.Response(200,json={'results':[{'title':'A','url':'https://example.org','description':'Text'}]})
    d=Desk(s,st,provider=Brave(s,st,httpx.Client(transport=httpx.MockTransport(response))))
    m=d.monitor(o,{'name':'Acme','sources':['news','web']})
    d.refresh(o,m['id'],cancel)
    assert len(st.list(o,'finding'))==1
    run=st.list(o,'run')[0]
    assert run['outcome']==('Cancelled' if cancel_after_page else 'Partial results') and run['count']==1
    assert st.budgets()['source']['used']==(1 if cancel_after_page else 2)
    d.pool.shutdown()


def test_progress_does_not_move_existing_page_and_is_persisted(app_env):
    app,d,st,c,o=app_env
    m=d.monitor(o,{'name':'Acme'});st.preferences(o,{'monitor':m['id'],'snapshot':1,'page':2,'tab':'board'})
    d.submit(o,'Collecting coverage',lambda cancel:d.refresh(o,m['id'],cancel),True)
    await_true(lambda:d.jobs.get(o.user,{}).get('state')=='Ready')
    p=st.preferences(o)
    assert p['snapshot']==1 and p['page']==2 and p['tab']=='board'
    job=st.list(o,'job')[0]
    assert job['retained']==1 and job['run_id'] and job['state']=='Ready'
    assert finding_selection(st,o,p)['new']==1


def test_all_new_views_obey_slack_limits(app_env):
    app,d,st,c,o=app_env
    views=[ui.monitor_modal(),ui.monitor_modal(expanded=True),ui.filters_modal({})]
    views.extend(ui.help_modal(tab) for tab in ('explore','board','briefings'))
    f=d.manual(o,{'title':'Title','url':'https://example.org','text':'x'*8000})
    b=d.save(o,f['id'],'shared',True)
    for i in range(30):d.perspective(o,b['id'],'x'*2000)
    dr=d.draft(o,[b['id']]);assert dr['perspective_count']==30 and len(dr['perspectives'])==8
    views.append(ui.modal('Briefing',ui.briefing_blocks(dr)))
    b=st.get(o,b['id'])
    for tab in ('overview','evidence','source','discussion'):
        for page in range(12):views.append(ui.detail(b,True,tab,page))
    for v in views:
        View(**v).validate_json()
        assert len(v['blocks'])<=100 and len(v.get('private_metadata',''))<=3000
        for block in v['blocks']:
            if block['type']=='section':assert len(block['text']['text'])<=3000
            if block['type']=='actions':assert len({e['action_id'] for e in block['elements']})==len(block['elements'])
    assert len(ui.briefing_blocks(dr))<50


def test_restart_restores_count_without_retry(app_env):
    app,d,st,c,o=app_env
    m=d.monitor(o,{'name':'Acme'})
    run=st.create(o,'run',{'monitor_id':m['id'],'count':3,'statuses':[],'outcome':'Searching'})
    st.create(o,'job',{'label':'Collecting coverage','state':'Working','run_id':run['id'],'retained':3})
    restarted=Desk(d.s,st)
    restarted.restore_jobs(o)
    assert restarted.jobs[o.user]['state']=='Interrupted' and restarted.jobs[o.user]['retained']==3
    assert st.get(o,run['id'])['outcome']=='Interrupted'
    assert st.budgets()['source']['used']==0
    restarted.pool.shutdown()


def test_collection_progress_updates_are_throttled(app_env):
    app,d,st,c,o=app_env
    d.jobs[o.user]={'label':'Collecting coverage','state':'Working'}
    for n in range(20):d.progress(o,{'retained':n})
    assert c.views_publish.call_count==1
    d.jobs[o.user]['state']='Ready';d.changed(o)
    assert c.views_publish.call_count==2


def test_collection_empty_unsearched_and_unavailable_are_distinct():
    run={'outcome':'Partial results','count':0,'checked':time.time(),'calls_cap':2,'pages_cap':1,
         'enabled_sources':['instagram','linkedin','x'], 'statuses':[
            {'target':'instagram','status':'No matches','results':0,'requested':True},
            {'target':'linkedin','status':'Source rate limit','results':0,'requested':True}]}
    v=ui.collection_modal(run)
    text=' '.join(b.get('text',{}).get('text','') for b in v['blocks'])
    assert 'No indexed matches returned' in text and 'Source rate limit' in text and 'Not searched' in text


def test_budget_exhaustion_sends_no_request_and_persists_status():
    s=live_mock_settings();st=Store(s)
    for _ in range(30):st.consume('source')
    client=Mock()
    rows,status=Brave(s,st,client).retrieve({'name':'Acme','sources':['instagram']},threading.Event())
    client.get.assert_not_called()
    assert rows==[] and not status[0]['requested'] and 'cap is reached' in status[0]['status']


def test_page_persistence_failure_keeps_prior_pages(app_env):
    app,d,st,c,o=app_env
    m=d.monitor(o,{'name':'Acme'})
    class Provider:
        def retrieve(self,monitor,cancel,on_page,progress):
            on_page([record('Kept','https://example.org','Text','Brave news',{})],[{'source':'news','status':'Results','results':1}])
            raise RuntimeError('Synthetic interruption')
    d.s.mode='live';d.provider=Provider()
    with pytest.raises(RuntimeError):d.refresh(o,m['id'],threading.Event())
    assert len(st.list(o,'finding'))==1 and st.list(o,'run')[0]['outcome']=='Partial results'


def test_social_operator_tokens_and_off_target_results_are_honest():
    s=live_mock_settings();st=Store(s);requests=[]
    def response(req):
        requests.append(req)
        return httpx.Response(200,json={'query':{'search_operators':{'applied':True}},'web':{'results':[
            {'title':'Off target','url':'https://example.org','description':'Text'},
            {'title':'On target','url':'https://instagram.com/p/1','description':'Text'}]}})
    rows,status=Brave(s,st,httpx.Client(transport=httpx.MockTransport(response))).retrieve(
        {'name':'Acme','sources':['instagram']},threading.Event())
    params=requests[0].url.params
    assert params['q']=='site:instagram.com "Acme"'
    assert params['operators']=='true' and params['spellcheck']=='false'
    assert len(rows)==2 and status[0]['platform_matches']==1
    assert any('outside the requested platform' in x['status'] for x in status)
    assert rows[0]['provenance']['operators_applied'] is True


def test_x_alternate_domain_is_queried_after_other_primary_targets():
    s=live_mock_settings();st=Store(s);queries=[]
    def response(req):
        queries.append(req.url.params['q'])
        return httpx.Response(200,json={'web':{'results':[]}})
    Brave(s,st,httpx.Client(transport=httpx.MockTransport(response))).retrieve(
        {'name':'Acme','sources':['x','linkedin']},threading.Event())
    assert queries==['site:x.com "Acme"','site:linkedin.com "Acme"','site:twitter.com "Acme"']


def test_readable_copy_has_no_encoding_replacement_separators(app_env):
    app,d,st,c,o=app_env
    m=d.monitor(o,{'name':'Acme'});d.refresh(o,m['id'],threading.Event())
    st.preferences(o,{'monitor':m['id'],'snapshot':time.time()})
    views=[ui.home(d,o),ui.monitor_modal(),ui.detail(st.list(o,'finding')[0])]
    for view in views:
        text=json.dumps(view,ensure_ascii=False)
        assert ' ? ' not in text and 'team?s' not in text and 'Brave?s' not in text
