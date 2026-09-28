"""Offline synthetic evidence for the outlet workflow; never live coverage."""
import copy,json,time,threading
from datetime import datetime,timedelta,timezone
from unittest.mock import Mock
import pytest
from coverage_desk.config import Settings,DeskError
from coverage_desk.store import Store,Actor
from coverage_desk.service import Desk
from coverage_desk.sources import record
from coverage_desk.scope import snapshot
from coverage_desk.overview import coverage_overview,chart_block
from coverage_desk.discovery import finding_selection
from coverage_desk import ui

@pytest.fixture
def env():
    s=Settings(channel='PUBLIC');st=Store(s);d=Desk(s,st);o=Actor('TEST','OWNER')
    m=d.monitor(o,{'name':'Synthetic client','campaign':'Launch','freshness':'pm','messages':['Missing slogan'],'notes':'PRIVATE IDENTITY NOTE'})
    yield d,st,o,m
    d.pool.shutdown();st.db.close()

def article(st,o,m,url='https://a.example/story',kind='reporting',date='recent',assessed=True):
    published=(datetime.now(timezone.utc)-timedelta(days=2)).replace(hour=12,minute=0,second=0,microsecond=0).isoformat() if date=='recent' else date
    r=record('Synthetic launch reporting',url,'A reporter documented criticism of the launch.','Codex web',{},published)
    r.update(monitor_id=m['id'],monitor_revision=m['revision'],scope_key=m['scope_key'],date_kind='publication' if published else 'unknown')
    if assessed:r.update(analysis_scope_key=m['scope_key'],analysis={'source_id':'placeholder','relevance':'relevant','campaign_relevance':'relevant',
        'explanation':'Critical launch coverage','messages':[], 'coverage':{'content_type':kind,'evidence':'A reporter documented criticism of the launch.','outlet_name':'','redistribution':''}})
    return st.create(o,'finding',r)

def overview(env,**prefs):
    d,st,o,m=env
    return coverage_overview(st,o,m,{'snapshot':time.time()+0.001,**prefs})

def test_unique_counts_span_pages_runs_and_survive_empty_refresh(env):
    d,st,o,m=env
    for i in range(13):article(st,o,m,f'https://a.example/{i}')
    duplicate=article(st,o,m,'https://a.example/0?utm_source=repeat',assessed=False)
    st.create(o,'run',{'monitor_id':m['id'],'scope':snapshot(m),'count':0,'outcome':'Unavailable','checked':time.time(),'error':'Provider failed'})
    data=overview(env)
    assert data['article_count']==13 and data['outlet_count']==1 and data['partial']
    assert sum(x['count'] for x in data['outlets'])==len(data['articles'])
    assert len(next(r for r in data['articles'] if r['canonical'].endswith('/0'))['observations'])==2
    p={'monitor':m['id'],'filter':'all','content_type':'reporting','coverage_state':'confirmed','page':2,'snapshot':time.time()+.001}
    selected=finding_selection(st,o,p)
    assert len(selected['rows'])==13 and len(selected['visible'])==3

def test_no_blind_merging_subdomains_or_common_publisher_names(env):
    d,st,o,m=env
    for domain in ('a.example','sports.a.example','b.example'):article(st,o,m,f'https://{domain}/story')
    assert overview(env)['outlet_count']==3
    source=st.list(o,'finding')[0]
    d.correct_coverage(o,source['id'],{'outlet_name':'Publication A','outlet_group':'a.example','reason':'Synthetic evidence of an exact-host alias'})
    data=overview(env)
    assert data['outlet_count']==2 and sorted(x['count'] for x in data['outlets'])==[1,2]
    assert all(r['outlet_key']!='example' for r in data['rows'])

def test_news_hit_is_not_reporting_and_categories_stay_inspectable(env):
    d,st,o,m=env
    for kind in ('reporting','client_owned','press_release','sponsored','social','unknown'):
        article(st,o,m,'https://'+kind.replace('_','-')+'.example/story',kind)
    data=overview(env)
    assert data['article_count']==1 and len(data['rows'])==6
    assert overview(env,content_type='all')['article_count']==6
    source=article(st,o,m,'https://news.example/no-type');source['analysis'].pop('coverage');source['provider']='Brave news';st.update(o,source['id'],source)
    assert overview(env)['article_count']==1

def test_relevance_dates_and_assessment_are_independent(env):
    d,st,o,m=env
    article(st,o,m,date=None)
    article(st,o,m,'https://a.example/unassessed',assessed=False)
    article(st,o,m,'https://a.example/old',date='2020-01-01T12:00:00+00:00')
    article(st,o,m,'https://a.example/critical')
    data=overview(env)
    assert data['article_count']==1
    assert data['states']['date_unconfirmed']==data['states']['unassessed']==data['states']['outside']==1
    assert next(r for r in data['rows'] if r['coverage_state']=='unassessed')['date_status']=='confirmed'

def test_new_negative_assessment_overrides_old_positive(env):
    d,st,o,m=env;article(st,o,m)
    newer=article(st,o,m);newer['analysis']['relevance']='not_relevant';st.update(o,newer['id'],newer)
    assert overview(env)['article_count']==0

def test_date_window_is_rechecked_and_retrieval_date_never_used(env):
    d,st,o,m=env;r=article(st,o,m,date=None)
    assert overview(env)['article_count']==0
    d.correct_coverage(o,r['id'],{'date_action':'set','published':'2026-09-10T12:00:00Z','reason':'Owner reviewed explicit publisher metadata'})
    data=coverage_overview(st,o,m,at=datetime(2026,9,28,tzinfo=timezone.utc).timestamp()+86400)
    assert data['article_count']==1
    later=coverage_overview(st,o,m,at=datetime(2026,11,1,tzinfo=timezone.utc).timestamp())
    assert later['article_count']==0 and later['states']['outside']==1

def test_scope_edits_do_not_reuse_incompatible_coverage(env):
    d,st,o,m=env;article(st,o,m)
    changed=d.monitor(o,{**m,'campaign':'Different'},m['id'])
    assert coverage_overview(st,o,changed)['article_count']==0

def test_chart_eight_plus_remainder_and_stable_ties(env):
    d,st,o,m=env
    for i in range(11):article(st,o,m,f'https://outlet{i:02}.example/story')
    data=overview(env);chart=chart_block(data);points=chart['chart']['series'][0]['data']
    assert len(points)==9 and points[-1]=={'label':'Other outlets','value':3}
    assert sum(p['value'] for p in points)==data['article_count']
    assert all(p['value']>=0 and len(p['label'])<=20 for p in points)
    assert [o['key'] for o in data['outlets']]==sorted(o['key'] for o in data['outlets'])
    assert chart_block({'outlets':[]}) is None

def test_syndicated_copies_are_distinct_outlet_appearances(env):
    d,st,o,m=env
    a=article(st,o,m);b=article(st,o,m,'https://b.example/story')
    assert overview(env)['article_count']==2
    assert not any(r['redistribution'] for r in overview(env)['rows'])
    a['analysis']['coverage']['redistribution']='A reporter documented criticism of the launch.';st.update(o,a['id'],a)
    assert len([r for r in overview(env)['rows'] if r['redistribution']])==1

def test_snapshot_is_frozen_authorized_and_omits_private_criteria(env):
    d,st,o,m=env;r=article(st,o,m)
    with pytest.raises(DeskError):d.overview_snapshot(o,m['id'])
    with pytest.raises(DeskError):d.overview_snapshot(Actor('TEST','TEAM'),m['id'],confirmed=True)
    with pytest.raises(DeskError):coverage_overview(st,Actor('TEST','TEAM'),m)
    snap=d.overview_snapshot(o,m['id'],confirmed=True);before=ui.briefing_message(snap)
    assert 'PRIVATE IDENTITY NOTE' not in json.dumps(snap) and 'Missing slogan' not in json.dumps(snap)
    article(st,o,m,'https://b.example/new')
    assert d.preview(o,snap['id']) and ui.briefing_message(st.get(o,snap['id']))==before
    assert snap['overview']['article_count']==1 and overview(env)['article_count']==2
    with pytest.raises(DeskError):st.get(Actor('TEST','TEAM'),snap['id'])
    with pytest.raises(DeskError):d.edit_draft(o,snap['id'],'Tampered count',1)

def test_snapshot_publish_rechecks_retention_and_corrections(env):
    d,st,o,m=env;r=article(st,o,m)
    snap=d.overview_snapshot(o,m['id'],confirmed=True);p=d.preview(o,snap['id'])
    d.correct_coverage(o,r['id'],{'content_type':'sponsored','reason':'Reviewed sponsorship disclosure'})
    client=Mock()
    with pytest.raises(DeskError):d.publish(o,p['id'],client)
    client.chat_postMessage.assert_not_called()

def test_confirmed_snapshot_publish_shares_only_frozen_copy(env):
    d,st,o,m=env;r=article(st,o,m)
    snap=d.overview_snapshot(o,m['id'],confirmed=True);p=d.preview(o,snap['id'])
    client=Mock();client.conversations_info.return_value={'channel':{'is_member':True}}
    client.chat_postMessage.return_value={'ts':'1.2'}
    sent=d.publish(o,p['id'],client)
    assert st.get(Actor('TEST','TEAM'),sent['id'])['overview']['article_count']==1
    with pytest.raises(DeskError):st.get(Actor('TEST','TEAM'),r['id'])
    with pytest.raises(DeskError):d.publish(o,p['id'],client)
    assert client.chat_postMessage.call_count==1

def test_migration_backup_keeps_saved_records_expiry_and_usage(tmp_path):
    st=Store(Settings(database=str(tmp_path/'desk.sqlite3')));o=Actor('TEST','OWNER')
    st.migrate_research();saved=st.create(o,'briefing',{'title':'Keep draft','text':'Private prose'})
    st.consume('ai');st.consume('source');before=st.budgets()
    backup=st.migrate_overview()
    assert backup.exists() and st.migrate_overview() is None
    assert st.get(o,saved['id'])==saved and st.budgets()==before
    st.db.close()


def test_equivalent_timestamp_observations_do_not_conflict(env):
    d,st,o,m=env
    a=article(st,o,m);b=article(st,o,m)
    b['published']=datetime.fromisoformat(a['published']).astimezone(timezone(timedelta(hours=-4))).isoformat()
    st.update(o,b['id'],b)
    assert overview(env)['article_count']==1


def test_snapshot_rejects_revoked_storage_and_expired_evidence(env):
    d,st,o,m=env;r=article(st,o,m)
    r['provider']='Brave news';st.update(o,r['id'],r);d.s.storage_allowed=True
    snap=d.overview_snapshot(o,m['id'],confirmed=True);p=d.preview(o,snap['id'])
    d.s.storage_allowed=False
    client=Mock()
    with pytest.raises(DeskError):d.publish(o,p['id'],client)
    client.chat_postMessage.assert_not_called()
    d.s.storage_allowed=True
    st.db.execute('UPDATE objects SET expires=? WHERE id=?',(time.time()-1,r['id']))
    assert overview(env)['article_count']==0
    with pytest.raises(DeskError):d.preview(o,snap['id'])


def test_alias_asof_and_snapshot_change_detection(env):
    d,st,o,m=env;r=article(st,o,m)
    at=time.time();snap=d.overview_snapshot(o,m['id'],{'snapshot':at},confirmed=True)
    d.correct_coverage(o,r['id'],{'outlet_name':'Reviewed Publication','reason':'Publisher masthead'})
    assert coverage_overview(st,o,m,at=at)['outlets'][0]['name']=='a.example'
    assert overview(env)['outlets'][0]['name']=='Reviewed Publication'
    with pytest.raises(DeskError):d.preview(o,snap['id'])


def test_outlet_and_source_snapshot_pages_cover_every_item(env):
    from coverage_desk.overview_ui import snapshot_modal
    d,st,o,m=env
    for i in range(17):article(st,o,m,f'https://outlet{i:02}.example/story')
    snap=d.overview_snapshot(o,m['id'],confirmed=True)
    sources=' '.join(json.dumps(snapshot_modal(snap,page)) for page in range(4))
    outlets=' '.join(json.dumps(snapshot_modal(snap,page,'outlets')) for page in range(2))
    for source in snap['sources']:assert source['url'] in sources and source['outlet_name'] in outlets
    for page in range(4):
        for block in snapshot_modal(snap,page)['blocks']:
            ids=[e['action_id'] for e in block.get('elements',[]) if 'action_id' in e]
            assert len(ids)==len(set(ids))


def test_home_default_order_chart_fallback_and_all_outlets(env):
    d,st,o,m=env
    for i in range(11):article(st,o,m,f'https://outlet{i:02}.example/story')
    st.preferences(o,{'monitor':m['id'],'snapshot':time.time()})
    fallback=ui.home(d,o)
    assert not any(b['type']=='data_visualization' for b in fallback['blocks'])
    st.create(o,'slack_capabilities',{'home':{'data_visualization':{'supported':True}}})
    home=ui.home(d,o);blocks=home['blocks'];chart=next(i for i,b in enumerate(blocks) if b['type']=='data_visualization')
    assert sum(b['type']=='data_visualization' for b in blocks)==1
    assert next(i for i,b in enumerate(blocks) if 'Coverage found' in json.dumps(b))<chart
    assert next(i for i,b in enumerate(blocks) if 'Collection details' in json.dumps(b))>chart if any('Collection details' in json.dumps(b) for b in blocks) else True
    first=json.dumps(home);st.preferences(o,{'outlet_page':1});second=json.dumps(ui.home(d,o))
    for i in range(11):assert f'outlet{i:02}.example' in first+second


def test_empty_partial_and_message_absence_never_exclude_critical_reporting(env):
    d,st,o,m=env
    assert overview(env)['article_count']==0 and chart_block(overview(env)) is None
    r=article(st,o,m)
    r['analysis']['messages']=[{'message':'Missing slogan','label':'not_observed','evidence':[],'explanation':'Not present'}]
    st.update(o,r['id'],r)
    st.create(o,'run',{'monitor_id':m['id'],'scope':snapshot(m),'outcome':'Assessed','limited':True})
    data=overview(env)
    assert data['article_count']==1 and data['partial']


def test_live_assessment_schema_requires_all_fields_but_legacy_storage_is_readable():
    from coverage_desk.models import LiveAnalysis,Classification
    schema=LiveAnalysis.model_json_schema()
    for node in [schema,*schema['$defs'].values()]:
        if node.get('type')=='object':assert set(node['properties'])==set(node['required']) and node['additionalProperties'] is False
    assert Classification.model_validate({'source_id':'x','relevance':'uncertain','campaign_relevance':'not_applicable','explanation':'Legacy','messages':[]}).coverage is None


def test_field_correction_evidence_and_saved_date_survive_later_outlet_edit(env):
    d,st,o,m=env;r=article(st,o,m,date=None)
    stamp=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
    d.correct_coverage(o,r['id'],{'content_type':'reporting','date_action':'set','published':stamp,'reason':'Reporting byline and publication timestamp'})
    d.correct_coverage(o,r['id'],{'outlet_name':'Publication A','reason':'Publisher masthead'})
    row=d.finding_detail(o,r['id'])
    assert row['classification_evidence']['quote']=='Reporting byline and publication timestamp'
    assert row['published']==stamp
    saved=d.save(o,r['id'],'private')
    assert saved['published']==stamp and saved['date_kind']=='owner_confirmed'
    assert 'Publisher masthead' not in json.dumps(saved)


def test_publisher_metadata_supports_type_not_message_claims():
    from coverage_desk.models import validate_analysis
    source={'id':'x','title':'A client announcement','text':'Short observed excerpt','provenance':{'publication_check':{'source_profile':{'publisher':'Outlet A','authors':['Jane Journalist'],'article_types':['NewsArticle']}}}}
    result={'findings':[{'source_id':'x','relevance':'relevant','campaign_relevance':'not_applicable','explanation':'Reporting','messages':[],
        'coverage':{'content_type':'reporting','evidence':'Jane Journalist','outlet_name':'Outlet A','redistribution':''}}]}
    assert validate_analysis(result,[source],[])['findings'][0]['coverage']['content_type']=='reporting'
    result['findings'][0]['messages']=[{'message':'Jane Journalist','label':'supported','explanation':'Invalid message proof','evidence':[{'source_id':'x','quote':'Jane Journalist'}]}]
    with pytest.raises(DeskError):validate_analysis(result,[source],['Jane Journalist'])


def test_www_is_not_implicitly_merged(env):
    d,st,o,m=env
    article(st,o,m,'https://a.example/one');article(st,o,m,'https://www.a.example/two')
    assert overview(env)['outlet_count']==2


def test_pending_classification_prioritizes_current_confirmed_evidence(env):
    d,st,o,m=env
    current=article(st,o,m);older=article(st,o,m,'https://other.example/old',date='2020-01-01T00:00:00Z')
    for source in (current,older):source['analysis'].pop('coverage');st.update(o,source['id'],source)
    d.s.mode='live';d.s.ai_items=1;d.analyze=Mock();d.verify_dates=Mock()
    d.continue_research(o,m['id'],threading.Event())
    assert d.analyze.call_args.args[2]==[current['id']]


def test_type_only_assessment_preserves_message_evidence_and_counts(env):
    d,st,o,m=env;r=article(st,o,m,kind='unknown');before=copy.deepcopy(r['analysis'])
    d.s.mode='live';d.s.allow_live=True;d.verify_dates=Mock();d.analyzer=Mock()
    d.analyzer.classify_coverage.return_value={'findings':[{'source_id':r['id'],'coverage':{'content_type':'reporting','evidence':r['text'],'outlet_name':'','redistribution':''}}]}
    d.continue_research(o,m['id'],threading.Event())
    assert st.get(o,r['id'])['analysis']==before and overview(env)['article_count']==1
    d.analyzer.analyze.assert_not_called()
    d.continue_research(o,m['id'],threading.Event())
    assert d.analyzer.classify_coverage.call_count==1
    with pytest.raises(DeskError):d.classify_coverage(Actor('TEST','TEAM'),m,[r],threading.Event())


def test_type_only_runtime_allowlist_excludes_private_data():
    from coverage_desk.runtime import CodexAnalyzer
    s=Settings(mode='live',allow_live=True);st=Store(s);ai=CodexAnalyzer(s,st)
    ai.status=Mock(return_value={'state':'Ready'});ai.call=Mock(return_value={'findings':[]})
    r={'id':'x','title':'Title','url':'https://a.example','text':'Observed text','access':'excerpt','notes':'PRIVATE CANARY','provenance':{'query':'PRIVATE QUERY','publication_check':{'source_profile':{'publisher':'Outlet','secret':'PRIVATE PROFILE'}}}}
    ai.classify_coverage([r],threading.Event())
    payload=ai.call.call_args.args[1]
    assert 'PRIVATE' not in json.dumps(payload)
    assert payload['sources'][0]['publisher_metadata']=={'publisher':'Outlet'}
    assert st.budgets()['ai']['used']==1


def test_refresh_automatically_builds_overview_after_two_bounded_assessments(monkeypatch):
    from test_native_research import envelope,configure_analyzer
    s=Settings(mode='live',allow_live=True);st=Store(s);o=Actor('TEST','OWNER');ai=Mock();configure_analyzer(ai)
    ai.discover.return_value=envelope()
    ai.classify_coverage.side_effect=lambda rows,cancel:{'findings':[{'source_id':r['id'],'coverage':{'content_type':'reporting','evidence':r['text'],'outlet_name':'','redistribution':''}} for r in rows]}
    date=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
    metadata=Mock(return_value={'published':date,'source_profile':{'authors':['Synthetic journalist']}})
    monkeypatch.setattr('coverage_desk.public_evidence.fetch_metadata',metadata)
    d=Desk(s,st,ai);m=d.monitor(o,{'name':'Acme','freshness':'pm'})
    try:
        d.research(o,m['id'],threading.Event())
        data=coverage_overview(st,o,m)
        assert data['article_count']==data['outlet_count']==1 and len(data['articles'][0]['observations'])==2
        assert ai.analyze.call_count==ai.classify_coverage.call_count==1 and metadata.call_count==1
        assert st.preferences(o)['explore_view']=='overview'
        assert not data['run'].get('error')
    finally:d.pool.shutdown();st.db.close()


def test_publisher_canonical_merge_preserves_saved_work_and_snapshot_corrections(env):
    d,st,o,m=env
    original=article(st,o,m,'https://a.example/story')
    amp=article(st,o,m,'https://a.example/amp/story')
    board=d.save(o,amp['id'],'private')
    d.perspective(o,board['id'],'Retain this perspective')
    amp=st.get(o,amp['id']);amp['canonical']=original['canonical'];st.update(o,amp['id'],amp)
    data=overview(env)
    assert data['article_count']==1 and len(data['articles'][0]['observations'])==2
    assert st.get(o,board['id'])['perspectives'][0]['text']=='Retain this perspective'
    draft=d.overview_snapshot(o,m['id'],confirmed=True)
    d.correct_coverage(o,original['id'],{'relevance':'not_relevant','reason':'Reviewed original evidence'})
    with pytest.raises(DeskError,match='corrected'):d.validate_overview_snapshot(o,draft)
    assert overview(env)['article_count']==0
