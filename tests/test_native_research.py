import threading,json,time,sqlite3
from unittest.mock import Mock
import pytest
from coverage_desk.config import DeskError,Settings
from coverage_desk.store import Store,Actor
from coverage_desk.service import Desk
from coverage_desk.research import registry,assessments,public_url
from coverage_desk.public_evidence import publication,fetch_metadata
from coverage_desk.discovery import finding_selection
from coverage_desk.sources import record


def envelope():
 return {'observed':[{'type':'webSearch','id':'search1','query':'Acme repair','action':{'type':'search'},'results':[
  {'type':'text_result','url':'https://example.org/story','title':'Repair report','snippet':'Acme repairs face criticism.','ref_id':'turn0search0'},
  {'type':'text_result','url':'https://example.org/story?utm_source=again','title':'Repair report','snippet':'Acme repairs face criticism.','ref_id':'turn0search1'}]}],
  'result':{'interpretation':'General coverage including critical reporting.','findings':[{'source_id':'turn0search0','relevance':'relevant','campaign_relevance':'not_applicable','explanation':'Names the subject.','messages':[], 'supporting_quote':'Acme repairs face criticism.'}]}}


def configure_analyzer(a):
 a.classify_coverage.side_effect=lambda rows,cancel:{'findings':[{'source_id':r['id'],'coverage':{'content_type':'unknown','evidence':'','outlet_name':'','redistribution':''}} for r in rows]}
 a.plan.return_value={'interpretation':'Public coverage','queries':[{'query':'Acme repair','target':'news','purpose':'broad','rationale':'General'}]}
 a.analyze.side_effect=lambda rows,monitor,cancel: {'findings':[{'source_id':r['id'],'relevance':'relevant','campaign_relevance':'not_applicable','explanation':'Names the subject.','messages':[]} for r in rows]}


def test_registry_ignores_generated_urls_and_attempted_open():
 e=envelope();e['result']['invented_url']='https://example.org/fake';e['observed'].append({'type':'webSearch','id':'open1','action':{'type':'openPage','url':'https://example.org/unread'}})
 rows=registry(e)
 assert len(rows)==2 and all('fake' not in r['url'] and 'unread' not in r['url'] for r in rows)
 assert all(r['published'] is None for r in rows)


def test_native_quotes_and_refs_require_observed_text():
 e=envelope();rows=registry(e)
 assert len(assessments(e,rows,[])[0])==1
 e['result']['findings'][0]['supporting_quote']='Invented quote'
 assert not assessments(e,rows,[])[0]
 e['result']['findings'][0].update(supporting_quote='Acme repairs face criticism.',source_id='invented')
 assert not assessments(e,rows,[])[0]


def test_one_owner_action_deduplicates_and_assesses_off_page(monkeypatch):
 s=Settings(mode='live',allow_live=True);st=Store(s);a=Mock();a.discover.return_value=envelope();configure_analyzer(a);d=Desk(s,st,a);o=Actor('TEST','OWNER')
 monkeypatch.setattr('coverage_desk.public_evidence.fetch_metadata',lambda *args:{'published':None,'status':'No date'})
 m=d.monitor(o,{'name':'Acme','research_path':'Codex native web'});st.preferences(o,{'monitor':m['id'],'page':9})
 try:
  d.research(o,m['id'],threading.Event())
  result=finding_selection(st,o,{**st.preferences(o),'filter':'all'})
  assert len(result['rows'])==1 and result['rows'][0]['analysis']
  assert len(result['rows'][0]['observations'])==2
  assert result['counts']=={'all':1,'relevant':0,'review':1}
  assert a.discover.call_count==1 and a.analyze.call_count==1 and not a.research.called
  d.research(o,m['id'],threading.Event())
  assert len(finding_selection(st,o,{**st.preferences(o),'filter':'all'})['rows'])==1
  assert len(st.list(o,'finding'))==4
  assert len(d.finding_detail(o,st.list(o,'finding')[0]['id'])['observations'])==4
  with pytest.raises(DeskError):d.research(Actor('TEST','OTHER'),m['id'],threading.Event())
 finally:d.pool.shutdown()


def test_migration_preserves_references_expiry_privacy_and_ledger(tmp_path):
 s=Settings(database=str(tmp_path/'desk.sqlite3'),storage_allowed=True);st=Store(s);o=Actor('TEST','OWNER');d=Desk(s,st)
 try:
  m=d.monitor(o,{'name':'Acme'});r=record('Title','https://example.org/a','Public excerpt','Brave news',{});r['monitor_id']=m['id']
  r=st.create(o,'finding',r);b=d.save(o,r['id'],'shared',True);d.perspective(o,b['id'],'Keep this perspective')
  draft=d.draft(o,[b['id']]);d.edit_draft(o,draft['id'],'Edited prose',1,'Edited title')
  preview=st.create(o,'preview',{'used':False});st.consume('source');st.consume('ai')
  before=st.db.execute('SELECT id,expires,visibility FROM objects').fetchall();budget=st.budgets()
  backup=st.migrate_research();assert backup.exists();assert st.migrate_research() is None
  assert st.budgets()==budget and [tuple(r) for r in before]==[tuple(r) for r in st.db.execute('SELECT id,expires,visibility FROM objects')]
  assert st.get(o,b['id'])['perspectives'][0]['text']=='Keep this perspective'
  assert st.get(o,draft['id'])['text']=='Edited prose' and st.get(o,draft['id'])['title']=='Edited title'
  assert st.get(o,preview['id'])['used']
  with pytest.raises(DeskError):st.get(Actor('TEST','OTHER'),r['id'])
  con=sqlite3.connect(backup);assert con.execute('SELECT used FROM budgets WHERE kind=?',('source',)).fetchone()[0]==1;con.close()
 finally:d.pool.shutdown();st.db.close()


def test_publication_requires_explicit_consistent_timezone_metadata():
 assert publication('<meta property="article:published_time" content="2026-09-26T12:00:00Z">')=='2026-09-26T12:00:00+00:00'
 assert publication('<time>Today</time><p>2026-09-26</p>') is None
 assert publication('<script type="application/ld+json">{"datePublished":"2026-09-26"}</script>') is None
 assert publication('<script type="application/ld+json">{"datePublished":"2026-09-26T12:00:00Z"}</script>')


@pytest.mark.parametrize('url',['http://127.0.0.1/x','http://169.254.169.254/x','http://[::1]/','http://localhost','file:///secret','http://thing.internal'])
def test_private_addresses_rejected(url):
 with pytest.raises(DeskError):public_url(url)


def test_public_fetch_rejects_private_dns_before_request(monkeypatch):
 monkeypatch.setattr('socket.getaddrinfo',lambda *a,**k:[(2,1,6,'',('127.0.0.1',443))])
 s=Settings(mode='live',allow_live=True);st=Store(s)
 with pytest.raises(DeskError):fetch_metadata('https://example.org/a',s,st,threading.Event())
 assert st.budgets()['source']['used']==0


def test_planned_workflow_runs_plan_then_unique_evidence_analysis(monkeypatch):
 s=Settings(mode='live',allow_live=True,brave_key='offline-placeholder',storage_allowed=True)
 st=Store(s);o=Actor('TEST','OWNER');a=Mock();d=Desk(s,st,a)
 m=d.monitor(o,{'name':'Acme','sources':['news','web'],'research_path':'AI-planned Brave'})
 st.db.execute('UPDATE budgets SET used=cap')
 a.plan.return_value={'interpretation':'Public subject coverage','queries':[
  {'query':'Acme news','target':'news','purpose':'broad','rationale':'General coverage'},
  {'query':'Acme repair','target':'web','purpose':'focus','rationale':'Campaign coverage'}]}
 class FakeProvider:
  def __init__(self,*args):pass
  def retrieve(self,monitor,cancel,on_page):
   rows=[record('Acme report','https://example.org/same?utm_source='+monitor['sources'][0],'Acme criticism.','Brave news',{})]
   status=[{'source':monitor['sources'][0],'status':'Results','requested':True,'results':1}]
   on_page(rows,status);return rows,status
 monkeypatch.setattr('coverage_desk.service.Brave',FakeProvider)
 monkeypatch.setattr('coverage_desk.public_evidence.fetch_metadata',lambda *a:{'published':None})
 def analyze(rows,monitor,cancel):
  assert len(rows)==1
  return {'findings':[{'source_id':rows[0]['id'],'relevance':'relevant','campaign_relevance':'not_applicable','explanation':'Subject identified','messages':[]}]}
 a.analyze.side_effect=analyze
 a.classify_coverage.side_effect=lambda rows,cancel:{'findings':[{'source_id':r['id'],'coverage':{'content_type':'unknown','evidence':'','outlet_name':'','redistribution':''}} for r in rows]}
 try:
  d.research(o,m['id'],threading.Event())
  assert a.plan.call_count==a.analyze.call_count==1 and not a.research.called
  result=finding_selection(st,o,{'monitor':m['id'],'filter':'all','snapshot':time.time()})
  assert len(result['rows'])==1 and result['rows'][0]['analysis']
  assert len(result['rows'][0]['observations'])==3
 finally:d.pool.shutdown()


def test_old_native_run_cannot_replace_edited_scope(monkeypatch):
 s=Settings(mode='live',allow_live=True);st=Store(s);o=Actor('TEST','OWNER');a=Mock();d=Desk(s,st,a)
 m=d.monitor(o,{'name':'Acme','research_path':'Codex native web'})
 def research(*args):
  d.monitor(o,{**m,'name':'Changed'},m['id']);return envelope()
 configure_analyzer(a)
 a.discover.side_effect=research
 monkeypatch.setattr('coverage_desk.public_evidence.fetch_metadata',lambda *a:{'published':None})
 try:
  d.research(o,m['id'],threading.Event())
  p={'monitor':m['id'],'filter':'all','snapshot':time.time()}
  assert not finding_selection(st,o,p)['rows']
  assert finding_selection(st,o,{**p,'history':'previous'})['rows']
  assert st.list(o,'run')[0]['outcome']=='Previous scope'
 finally:d.pool.shutdown()


def test_planner_never_receives_desired_message_as_search_restriction():
 from coverage_desk.runtime import CodexAnalyzer
 s=Settings(mode='live',allow_live=True);st=Store(s);a=CodexAnalyzer(s,st)
 a.status=Mock(return_value={'state':'Ready'})
 a.call=Mock(return_value={'interpretation':'General brand coverage','queries':[{'query':'Acme news','target':'news','purpose':'broad','rationale':'General'}]})
 a.plan({'name':'Acme','campaign':'','sources':['news'],'messages':['Confine coverage to repair']},threading.Event(),max_queries=2)
 assert 'messages' not in a.call.call_args.args[1]['criteria']
 assert st.budgets()['ai']['used']==1


def test_metadata_redirect_private_host_fails_before_second_request(monkeypatch):
 from coverage_desk import public_evidence as pe
 s=Settings(mode='live',allow_live=True);st=Store(s)
 monkeypatch.setattr(pe.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',80))])
 stream=Mock();monkeypatch.setattr(pe.socket,'create_connection',lambda *a,**k:stream)
 response=Mock(status=302);response.getheader.return_value='http://127.0.0.1/private'
 connection=Mock();connection.getresponse.return_value=response
 monkeypatch.setattr(pe.http.client,'HTTPConnection',lambda *a,**k:connection)
 with pytest.raises(DeskError):fetch_metadata('http://example.org/a',s,st,threading.Event())
 assert st.budgets()['source']['used']==1
 connection.close.assert_called_once()
