"""General research regressions: no brand-specific retrieval rules."""
import threading,time
from datetime import datetime,timezone
from unittest.mock import Mock
import pytest
from coverage_desk.scope import eligibility,scope_key,snapshot
from coverage_desk.research import search_tasks,search_statuses

@pytest.mark.parametrize('name,focus',[
 ('Stephen Curry','Li-Ning "Everything is possible"'),
 ('Acme Robotics','Nova "Work without limits"'),
 ('Juniper','Network security "AI everywhere"'),
 ('River Foundation','Clean water program')])
def test_selected_sources_each_get_a_topic_query_and_phrase_is_not_required(name,focus):
 monitor={'name':name,'campaign':focus,'aliases':[],'sources':['news','web','instagram','x','linkedin'],'messages':['SECRET MESSAGE NOT A SEARCH TERM']}
 plan={'interpretation':'Topic coverage','queries':[{'query':name+' '+focus,'target':'web','purpose':'focus','rationale':'Focus'}]}
 tasks=search_tasks(monitor,plan,snapshot(monitor))
 assert set(t['target'] for t in tasks)==set(monitor['sources'])
 assert all('SECRET MESSAGE' not in t['query'] for t in tasks)
 assert any(t['purpose']=='broad' for t in tasks)
 assert all('"' not in t['query'] for t in tasks)
 assert any('site:instagram.com' in t['query'] for t in tasks)
 assert any('site:linkedin.com' in t['query'] for t in tasks)
 assert any('site:x.com' in t['query'] for t in tasks)


def test_irrelevant_undated_is_excluded_not_review():
 m={'name':'Acme','campaign':'Launch','freshness':'pm'}
 r={'published':None,'analysis_scope_key':scope_key(m),'analysis':{'relevance':'relevant','campaign_relevance':'not_relevant','explanation':'Unrelated contract news'}}
 assert eligibility(r,m,snapshot(m))[0]=='excluded'


def test_unattempted_social_targets_are_reported_honestly():
 tasks=[{'query':'Acme site:instagram.com','target':'instagram','purpose':'focus'}, {'query':'Acme site:x.com','target':'x','purpose':'focus'}]
 events=[{'type':'webSearch','query':'Acme site:instagram.com','action':{'type':'search','query':'Acme site:instagram.com'},'results':[]}]
 statuses=search_statuses(tasks,events)
 assert statuses[0]['status']=='No indexed matches' and statuses[0]['requested']
 assert statuses[1]['status']=='Not searched' and not statuses[1]['requested']


def test_large_public_page_keeps_bounded_publication_metadata(monkeypatch):
 from coverage_desk import public_evidence as pe
 from coverage_desk.config import Settings
 from coverage_desk.store import Store
 s=Settings(mode='live',allow_live=True);st=Store(s)
 monkeypatch.setattr(pe.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',80))])
 stream=Mock();monkeypatch.setattr(pe.socket,'create_connection',lambda *a,**k:stream)
 body=b'<meta property="article:published_time" content="2026-09-26T12:00:00Z">'+b' ' * 270000
 response=Mock(status=200)
 response.getheader.side_effect=lambda key:'text/html' if key=='Content-Type' else None
 import io
 response.read1.side_effect=io.BytesIO(body).read
 connection=Mock();connection.getresponse.return_value=response
 monkeypatch.setattr(pe.http.client,'HTTPConnection',lambda *a,**k:connection)
 result=pe.fetch_metadata('http://example.org/a',s,st,threading.Event())
 assert result['published']=='2026-09-26T12:00:00+00:00' and result['truncated']
 assert st.budgets()['source']['used']==1
 connection.close.assert_called_once()


def test_bad_quote_does_not_discard_other_valid_findings():
 from coverage_desk.config import Settings
 from coverage_desk.store import Store,Actor
 from coverage_desk.service import Desk
 from coverage_desk.sources import record
 s=Settings(mode='live',allow_live=True);st=Store(s);owner=Actor('TEST','OWNER');ai=Mock();desk=Desk(s,st,ai)
 try:
  monitor=desk.monitor(owner,{'name':'Acme','messages':['Repair']})
  rows=[]
  for index in range(2):
   row=record('Acme report',f'https://example.org/{index}','Acme offers Repair.','Codex web',{})
   row.update(monitor_id=monitor['id'],monitor_revision=monitor['revision'],scope_key=scope_key(monitor))
   rows.append(st.create(owner,'finding',row))
  ai.analyze.return_value={'findings':[{'source_id':r['id'],'relevance':'relevant','campaign_relevance':'not_applicable',
   'explanation':'Subject coverage','messages':[{'message':'Repair','label':'supported','explanation':'Quoted in excerpt',
    'evidence':[{'source_id':r['id'],'quote':'Acme offers Repair.' if i==0 else 'invented quote'}]}]} for i,r in enumerate(rows)]}
  result=desk.analyze(owner,monitor['id'],[r['id'] for r in rows],threading.Event(),partial=True)
  assert len(result['findings'])==1
  assert st.get(owner,rows[0]['id'])['analysis']
  assert not st.get(owner,rows[1]['id']).get('analysis') and st.get(owner,rows[1]['id'])['analysis_error']
 finally:desk.pool.shutdown()


def test_message_absence_and_critical_reporting_remain_relevant():
 m={'name':'Acme','campaign':'Launch','freshness':'pm'}
 r={'published':datetime.now(timezone.utc).isoformat(),'date_kind':'publication','analysis_scope_key':scope_key(m),
    'analysis':{'relevance':'relevant','campaign_relevance':'relevant','explanation':'Critical reporting on launch failures.',
       'messages':[{'message':'Best ever','label':'not_observed_in_available_text','evidence':[]}]}}
 assert eligibility(r,m,snapshot(m))[0]=='relevant'


def test_native_preference_migration_preserves_scope_and_usage_and_is_once():
 from coverage_desk.config import Settings,DeskError
 from coverage_desk.store import Store,Actor
 from coverage_desk.service import Desk
 st=Store(Settings());owner=Actor('TEST','OWNER');desk=Desk(st.s,st)
 try:
  m=desk.monitor(owner,{'name':'Acme','research_path':'AI-planned Brave'})
  st.consume('source');before=st.budgets()
  with pytest.raises(DeskError):desk.adopt_native_research(Actor('TEST','OTHER'))
  desk.adopt_native_research(owner)
  updated=st.get(owner,m['id'])
  assert updated['research_path']=='Codex native web'
  assert updated['revision']==m['revision'] and updated['scope_key']==m['scope_key']
  assert st.budgets()==before
  updated['research_path']='AI-planned Brave';st.update(owner,m['id'],updated)
  desk.adopt_native_research(owner)
  assert st.get(owner,m['id'])['research_path']=='AI-planned Brave'
 finally:desk.pool.shutdown()


def test_date_words_are_search_hints_and_queries_cover_every_target():
 m={'name':'Juniper','campaign':'Network security','freshness':'pm','sources':['news','web','instagram','x','linkedin','facebook','tiktok','reddit','youtube']}
 plan={'queries':[{'query':'Juniper Network security','purpose':'focus'}, {'query':'Juniper Network security slogan','purpose':'broad'}, {'query':'Juniper security criticism','purpose':'contrary'}]}
 tasks=search_tasks(m,plan,snapshot(m,datetime(2026,9,28,tzinfo=timezone.utc).timestamp()))
 assert len(tasks)<=12 and 'September 2026' in tasks[0]['query']
 broad=next(t for t in tasks if t['purpose']=='broad')
 assert 'security' not in broad['query'] and 'slogan' not in broad['query']
 assert set(t['target'] for t in tasks)==set(m['sources'])


def test_assessment_interleaves_queries_instead_of_spending_batch_on_one():
 from coverage_desk.research import evidence_priority
 rows=[{'provenance':{'task_order':task,'result_rank':rank}} for task in range(3) for rank in range(20)]
 selected=sorted(rows,key=evidence_priority)[:15]
 assert {r['provenance']['task_order'] for r in selected}=={0,1,2}
 assert all(r['provenance']['result_rank']<5 for r in selected)


def test_discovery_excludes_message_criteria_and_accounts_for_all_tasks():
 from coverage_desk.config import Settings,DeskError
 from coverage_desk.store import Store
 from coverage_desk.runtime import CodexAnalyzer
 st=Store(Settings(mode='live',allow_live=True));ai=CodexAnalyzer(st.s,st)
 ai.status=Mock(return_value={'state':'Ready'});ai.call=Mock(return_value={'observed':[]})
 scope=snapshot({'name':'Acme','messages':['Private desired message']})
 tasks=[{'query':'Acme','target':target} for target in ('news','web','instagram')]
 ai.discover(scope,tasks,threading.Event())
 payload=ai.call.call_args.args[1]
 assert 'messages' not in payload['scope']['criteria']
 assert st.budgets()['source']['used']==4 and st.budgets()['ai']['used']==1
 with pytest.raises(DeskError):ai.discover(scope,tasks*5,threading.Event())
 assert st.budgets()['ai']['used']==1


def test_retained_headline_is_valid_evidence_but_generated_explanation_is_not():
 from coverage_desk.models import validate_analysis
 from coverage_desk.config import DeskError
 source={'id':'one','title':'Acme launches Nova','text':'Available this autumn.'}
 result={'findings':[{'source_id':'one','relevance':'relevant','campaign_relevance':'relevant','explanation':'Generated interpretation',
  'messages':[{'message':'Nova','label':'supported','explanation':'Headline names it','evidence':[{'source_id':'one','quote':'Acme launches Nova'}]}]}]}
 assert validate_analysis(result,[source],['Nova'])['findings']
 result['findings'][0]['messages'][0]['evidence'][0]['quote']='Generated interpretation'
 with pytest.raises(DeskError):validate_analysis(result,[source],['Nova'])


def test_earlier_collection_survives_an_empty_refresh():
 from coverage_desk.config import Settings
 from coverage_desk.store import Store,Actor
 from coverage_desk.service import Desk
 from coverage_desk.sources import record
 from coverage_desk.discovery import finding_selection
 st=Store(Settings());owner=Actor('TEST','OWNER');desk=Desk(st.s,st)
 try:
  m=desk.monitor(owner,{'name':'Acme'});scope=snapshot(m)
  run=st.create(owner,'run',{'monitor_id':m['id'],'scope':scope})
  row=record('Article','https://example.org/retained','Acme report','Codex web',{})
  row.update(monitor_id=m['id'],scope_key=scope['key'],monitor_revision=m['revision'],run_id=run['id'])
  old=st.create(owner,'finding',row)
  st.create(owner,'run',{'monitor_id':m['id'],'scope':scope,'count':0,'outcome':'Unavailable'})
  prefs={'monitor':m['id'],'filter':'all','snapshot':time.time()+1}
  assert finding_selection(st,owner,prefs)['rows'][0]['id']==old['id']
  assert not finding_selection(st,owner,{**prefs,'history':'previous'})['rows']
 finally:desk.pool.shutdown()
