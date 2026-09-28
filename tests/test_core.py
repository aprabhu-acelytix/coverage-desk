import json
import threading
import time
from unittest.mock import Mock
import pytest
import httpx
from coverage_desk.config import Settings,DeskError
from coverage_desk.store import Store,Actor
from coverage_desk.service import Desk
from coverage_desk.sources import Brave,queries
from coverage_desk.models import canonical_url,validate_analysis
from coverage_desk.runtime import child_env
from coverage_desk import ui

@pytest.fixture
def setup():
    s=Settings(channel='CDEMO');st=Store(s);d=Desk(s,st)
    owner=Actor('TEST','OWNER');team=Actor('TEST','TEAM')
    m=d.monitor(owner,{'name':'Acme','aliases':['AC'],'messages':['Repairable products'],'campaign':'repair'})
    f=d.manual(owner,{'monitor_id':m['id'],'title':'Acme report','url':'https://example.org/news?utm_source=test','text':'Acme says its products are repairable.'})
    yield s,st,d,owner,team,m,f
    d.pool.shutdown(wait=True)
    st.db.close()

def test_offline_flow(setup):
    s,st,d,o,t,m,f=setup
    assert d.analyze(o,m['id'],[f['id']],threading.Event())['findings']
    private=d.save(o,f['id'],'private')
    with pytest.raises(DeskError):st.get(t,private['id'])
    shared=d.save(o,f['id'],'shared',True)
    d.perspective(t,shared['id'],'Needs an independent source.','Use in briefing')
    draft=d.draft(o,[shared['id']])
    d.edit_draft(t,draft['id'],'Edited by collaborator.',1)
    assert st.get(o,draft['id'])['revision']==2
    preview=d.preview(o,draft['id'])
    client=Mock()
    client.conversations_info.return_value={'channel':{'is_member':True,'is_private':False}}
    client.chat_postMessage.return_value={'ts':'1.2'}
    assert d.publish(o,preview['id'],client)['status']=='Published'
    with pytest.raises(DeskError):d.publish(o,preview['id'],client)
    assert client.chat_postMessage.call_count==1
    assert st.budgets()['ai']['used']==0

def test_delete_board_preserves_existing_briefing_and_requires_new_preview(setup):
    s,st,d,o,t,m,f=setup
    board=d.save(o,f['id'],'shared',True)
    d.perspective(t,board['id'],'Keep this included note')
    draft=d.draft(o,[board['id']]);old=d.preview(o,draft['id']);usage=st.budgets()
    with pytest.raises(DeskError):d.delete_item(o,board['id'],'board')
    with pytest.raises(DeskError):d.delete_item(t,board['id'],'board',True)
    d.delete_item(o,board['id'],'board',True)
    assert not st.list(o,'board') and st.get(o,f['id'])
    kept=st.get(o,draft['id'])
    assert kept['text']==draft['text'] and kept['perspectives']==draft['perspectives']
    with pytest.raises(DeskError):st.get(o,old['id'])
    preview=d.preview(o,draft['id'])
    client=Mock();client.conversations_info.return_value={'channel':{'is_member':True}}
    client.chat_postMessage.return_value={'ts':'1.2'}
    assert d.publish(o,preview['id'],client)['status']=='Published'
    assert st.budgets()==usage

def test_delete_briefing_removes_previews_only_and_blocks_tampering(setup):
    s,st,d,o,t,m,f=setup
    board=d.save(o,f['id'],'shared',True);draft=d.draft(o,[board['id']]);preview=d.preview(o,draft['id'])
    with pytest.raises(DeskError):d.delete_item(t,draft['id'],'briefing',True)
    with pytest.raises(DeskError):d.delete_item(Actor('OTHER','OWNER'),draft['id'],'briefing',True)
    with pytest.raises(DeskError):d.delete_item(o,board['id'],'briefing',True)
    d.jobs[o.user]={'state':'Working'}
    with pytest.raises(DeskError):d.delete_item(o,draft['id'],'briefing',True)
    d.jobs.clear();d.delete_item(o,draft['id'],'briefing',True)
    assert not st.list(o,'briefing') and not st.list(o,'preview')
    assert st.get(o,board['id'])

def test_teammate_deletion_keeps_owner_private_draft_private(setup):
    s,st,d,o,t,m,f=setup
    source=d.manual(t,{'title':'Team source','url':'https://example.org/team','text':'Public excerpt'})
    board=d.save(t,source['id'],'shared',True)
    private=d.save(o,f['id'],'private');draft=d.draft(o,[board['id'],private['id']])
    with pytest.raises(DeskError):st.get(t,draft['id'])
    d.delete_item(t,board['id'],'board',True)
    assert d.preview(o,draft['id'])
    with pytest.raises(DeskError):st.get(t,draft['id'])
    with pytest.raises(DeskError):d.delete_item(t,private['id'],'board',True)

@pytest.mark.parametrize('status',['Published','Delivery uncertain'])
def test_remove_sent_briefing_does_not_remove_board_or_call_slack(setup,status):
    s,st,d,o,t,m,f=setup
    board=d.save(o,f['id'],'shared',True);draft=d.draft(o,[board['id']])
    draft.update(status=status,posted_ts='1.2');st.update(o,draft['id'],draft)
    d.delete_item(o,draft['id'],'briefing',True)
    assert not st.list(o,'briefing') and st.get(o,board['id'])

@pytest.mark.parametrize('operation',['monitor','analysis','draft','publish'])
def test_owner_only(setup,operation):
    s,st,d,o,t,m,f=setup
    with pytest.raises(DeskError):
        if operation=='monitor':d.monitor(t,{'name':'No'})
        elif operation=='analysis':d.analyze(t,m['id'],[f['id']],threading.Event())
        elif operation=='draft':d.draft(t,[])
        else:d.publish(t,'fake',Mock())

def test_workspace_and_tampered_ids(setup):
    s,st,d,o,t,m,f=setup
    wrong=Actor('OTHER','OWNER')
    for actor in (wrong,t):
        with pytest.raises(DeskError):st.get(actor,m['id'])
        with pytest.raises(DeskError):d.save(actor,f['id'],'private')
    with pytest.raises(DeskError):st.get(o,m['id'],'finding')

def test_sharing_does_not_leak_private_context(setup):
    s,st,d,o,t,m,f=setup
    d.analyze(o,m['id'],[f['id']],threading.Event())
    with pytest.raises(DeskError):d.save(o,f['id'],'shared')
    b=d.save(o,f['id'],'shared',True)
    assert not any(k in b for k in ('monitor_id','provenance','comment','analysis_key'))
    assert b['analysis'] is None
    assert 'Repairable products' not in json.dumps(st.get(t,b['id']))
    assert not st.list(t,'analysis_cache')

def test_duplicate_saves_and_action_claims(setup):
    s,st,d,o,t,m,f=setup
    assert d.save(o,f['id'],'shared',True)['id']==d.save(o,f['id'],'shared',True)['id']
    assert st.claim('event') and not st.claim('event')
    assert len(st.list(o,'board'))==1

def test_retention_blocks_saved_drafts(setup):
    s,st,d,o,t,m,f=setup
    b=d.save(o,f['id'],'shared',True);draft=d.draft(o,[b['id']])
    st.db.execute('UPDATE objects SET expires=? WHERE id=?',(time.time()-1,b['id']))
    with pytest.raises(DeskError):d.preview(o,draft['id'])
    assert not st.list(t,'board')
    assert st.purge()==1

def test_revoked_permission(setup):
    s,st,d,o,t,m,f=setup
    f['provider']='Brave news';st.update(o,f['id'],f)
    with pytest.raises(DeskError):d.save(o,f['id'],'private')

def test_stale_preview_and_edit(setup):
    s,st,d,o,t,m,f=setup
    b=d.save(o,f['id'],'shared',True);draft=d.draft(o,[b['id']]);p=d.preview(o,draft['id'])
    d.edit_draft(t,draft['id'],'Changed.',1)
    with pytest.raises(DeskError):d.edit_draft(o,draft['id'],'Overwrite',1)
    with pytest.raises(DeskError):d.publish(o,p['id'],Mock())

def test_uncertain_delivery_not_retried(setup):
    s,st,d,o,t,m,f=setup
    b=d.save(o,f['id'],'shared',True);dr=d.draft(o,[b['id']]);p=d.preview(o,dr['id'])
    client=Mock();client.conversations_info.return_value={'channel':{'is_member':True}}
    client.chat_postMessage.side_effect=TimeoutError()
    with pytest.raises(DeskError):d.publish(o,p['id'],client)
    with pytest.raises(DeskError):d.publish(o,p['id'],client)
    assert client.chat_postMessage.call_count==1

def test_query_and_tracking_url(setup):
    m=setup[-2]
    q=queries(m)
    assert len(q)==2 and 'Repairable products' not in q[0][1] and 'repair' in q[1][1]
    assert canonical_url('https://EXAMPLE.org/a?id=2&utm_source=a&fbclid=x')=='https://example.org/a?id=2'

def test_brave_pagination_preserves_every_record(setup):
    s,st,d,o,t,m,f=setup
    s.mode='live';s.allow_live=True;s.brave_key='MOCK';s.storage_allowed=True;s.results=60
    calls=[]
    def response(request):
        calls.append(request)
        rows=[{'title':f'Result {i}','url':f'https://example.org/{i}','description':'Acme'} for i in range(20)]
        return httpx.Response(200,json={'results':rows,'web':{'results':rows},'query':{'more_results_available':True}})
    provider=Brave(s,st,httpx.Client(transport=httpx.MockTransport(response)))
    rows,status=provider.retrieve(m,threading.Event())
    assert len(rows)==120 and len(calls)==6
    assert len({r['canonical'] for r in rows})==20
    assert st.budgets()['source']['used']==6
    assert any(x['status']=='Collection cap reached' for x in status)

@pytest.mark.parametrize('code',[401,403,429,500])
def test_provider_failure_never_fixture(setup,code):
    s,st,d,o,t,m,f=setup
    s.mode='live';s.allow_live=True;s.brave_key='MOCK';s.storage_allowed=True
    provider=Brave(s,st,httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(code))))
    rows,status=provider.retrieve(m,threading.Event())
    assert rows==[] and status and st.budgets()['source']['used']==4

def test_persistent_usage_continues_beyond_historical_caps(tmp_path):
    s=Settings(database=str(tmp_path/'budget.sqlite3'))
    st=Store(s)
    for _ in range(10):st.consume('ai')
    st.db.close();st=Store(s)
    st.consume('ai')
    for _ in range(31):st.consume('source')
    assert st.budgets()['ai']=={'used':11,'cap':None,'historical_cap':10}
    assert st.budgets()['source']=={'used':31,'cap':None,'historical_cap':30}
    with pytest.raises(DeskError):st.consume('unknown')

def test_exact_evidence_and_completeness(setup):
    s,st,d,o,t,m,f=setup
    raw={'findings':[{'source_id':f['id'],'relevance':'relevant','campaign_relevance':'relevant','explanation':'Company claim only.',
        'messages':[{'message':m['messages'][0],'label':'supported','explanation':'Attributed claim.','evidence':[{'source_id':f['id'],'quote':'products are repairable'}]}]}]}
    assert validate_analysis(raw,[f],m['messages'])
    raw['findings'][0]['messages'][0]['evidence'][0]['quote']='products last forever'
    with pytest.raises(DeskError):validate_analysis(raw,[f],m['messages'])
    with pytest.raises(DeskError):validate_analysis({'findings':[]},[f],m['messages'])

def test_environment_allowlist(monkeypatch):
    monkeypatch.setenv('SLACK_BOT_TOKEN','SECRET_CANARY')
    monkeypatch.setenv('BRAVE_API_KEY','SECRET_CANARY')
    monkeypatch.setenv('OPENAI_API_KEY','SECRET_CANARY')
    monkeypatch.setenv('CODEX_HOME','DEVELOPER_CANARY')
    monkeypatch.setenv('PATH','UNTRUSTED_CANARY')
    env=child_env('/dedicated')
    assert 'SECRET_CANARY' not in json.dumps(env)
    assert 'DEVELOPER_CANARY' not in json.dumps(env)
    assert 'UNTRUSTED_CANARY' not in json.dumps(env)

def test_cancel_before_network(setup):
    s,st,d,o,t,m,f=setup
    s.mode='live';s.allow_live=True;s.brave_key='MOCK';s.storage_allowed=True
    cancel=threading.Event();cancel.set()
    assert Brave(s,st).retrieve(m,cancel)[0]==[]
    assert st.budgets()['source']['used']==0

def test_safe_slack_and_payloads(setup):
    s,st,d,o,t,m,f=setup
    assert ui.esc('<!channel> & <@U>')=='&lt;!channel&gt; &amp; &lt;@U&gt;'
    for tab in ('explore','board','briefings'):
        st.preferences(o,{'tab':tab})
        view=ui.home(d,o)
        assert len(view['blocks'])<=100
        for block in view['blocks']:
            if block['type']=='section':assert len(block['text']['text'])<=3000
            if block['type']=='actions':
                ids=[x['action_id'] for x in block['elements']]
                assert len(ids)==len(set(ids))
    assert all(o['value'] for b in ui.monitor_modal()['blocks'] if b['type']=='input' and b['element']['type']=='static_select' for o in b['element']['options'])

def test_explicit_assessment_disclosure(setup):
    s,st,d,o,t,m,f=setup
    d.analyze(o,m['id'],[f['id']],threading.Event())
    b=d.save(o,f['id'],'shared',True,include_analysis=True)
    assert st.get(t,b['id'])['analysis']['messages'][0]['message']=='Repairable products'
    assert 'provenance' not in b and 'monitor_id' not in b

def test_busy_user_rejected_and_cancelled(setup):
    s,st,d,o,t,m,f=setup
    started=threading.Event();release=threading.Event()
    def work(cancel):
        started.set();release.wait(2)
    d.submit(o,'Work',work,True,key='one');assert started.wait(1)
    with pytest.raises(DeskError):d.submit(o,'Work',work,True,key='two')
    d.cancel(o);assert d.jobs[o.user]['cancel'].is_set()
    release.set()

def test_demo_cache_cannot_be_relabelled_as_live(setup):
    s,st,d,o,t,m,f=setup
    d.analyze(o,m['id'],[f['id']],threading.Event())
    s.mode='live';s.allow_live=True
    analyzer=Mock();analyzer.analyze.side_effect=DeskError('Sign-in needed');d.analyzer=analyzer
    with pytest.raises(DeskError,match='Sign-in'):d.analyze(o,m['id'],[f['id']],threading.Event())
    analyzer.analyze.assert_called_once()
    assert st.get(o,f['id'])['analysis_status']=='Fixture assessment'

def test_exact_preview_covers_source_links_not_only_text(setup):
    s,st,d,o,t,m,f=setup
    b=d.save(o,f['id'],'shared',True);draft=d.draft(o,[b['id']]);p=d.preview(o,draft['id'])
    draft['sources'][0]['url']='https://example.org/changed'
    st.update(o,draft['id'],draft)
    client=Mock()
    with pytest.raises(DeskError,match='changed'):d.publish(o,p['id'],client)
    client.chat_postMessage.assert_not_called()

def test_accessible_fallback_includes_sources_and_escaped_mentions(setup):
    s,st,d,o,t,m,f=setup
    b=d.save(o,f['id'],'shared',True);draft=d.draft(o,[b['id']])
    draft=d.edit_draft(o,draft['id'],'Worth discussing: <!channel> <@U123>',1)
    message=ui.briefing_message(draft)
    assert 'Worth discussing' in message['text'] and 'https://example.org/news' in message['text']
    assert '<!channel>' not in message['text'] and '<@U123>' not in message['text']
