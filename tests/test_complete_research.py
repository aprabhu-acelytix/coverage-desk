"""Offline regressions for complete assessment and simpler owner controls."""
import json,time,threading
from datetime import datetime,timedelta,timezone
from unittest.mock import Mock
import pytest
from coverage_desk.config import Settings,DeskError
from coverage_desk.store import Store,Actor
from coverage_desk.service import Desk
from coverage_desk.overview import coverage_overview
from coverage_desk.discovery import platform
from coverage_desk import ui

def test_one_refresh_assesses_every_unique_finding(monkeypatch):
    s=Settings(mode='live',allow_live=True);st=Store(s);o=Actor('TEST','OWNER');ai=Mock();d=Desk(s,st,ai)
    m=d.monitor(o,{'name':'Example','sources':['news'],'freshness':'pw'})
    ai.plan.return_value={'interpretation':'Example coverage','queries':[{'query':'Example','purpose':'broad','target':'news','rationale':'Subject'}]}
    ai.discover.return_value={'observed':[{'type':'webSearch','id':'one','query':'Example','results':[
        {'type':'text_result','url':f'https://example.org/{i}','title':f'Example report {i}','snippet':'A reporter describes Example.'} for i in range(41)]}]}
    def assess(rows,monitor,cancel):
        return {'findings':[{'source_id':r['id'],'relevance':'relevant','campaign_relevance':'not_applicable','explanation':'Subject reporting','messages':[],
            'coverage':{'content_type':'reporting','evidence':'A reporter describes Example.','outlet_name':'','redistribution':''}} for r in rows]}
    ai.analyze.side_effect=assess
    date=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
    monkeypatch.setattr('coverage_desk.public_evidence.fetch_metadata',lambda *a:{'published':date,'source_profile':{},'excerpt':'A reporter describes Example.','fetch_version':2})
    try:
        d.research(o,m['id'],threading.Event())
        data=coverage_overview(st,o,m)
        assert data['article_count']==41
        assert not data['states'].get('unassessed')
        assert sum(len(call.args[0]) for call in ai.analyze.call_args_list)==41
    finally:d.pool.shutdown();st.db.close()

def test_company_newsroom_is_not_a_social_post():
    assert platform('https://about.fb.com/news/company-announcement/') is None
    assert platform('https://www.facebook.com/a/posts/1')=='facebook'

def test_navigation_is_not_a_row_of_action_buttons():
    s=Settings();st=Store(s);d=Desk(s,st)
    try:
        home=ui.home(d,Actor('TEST','OWNER'))
        assert not any(e.get('type')=='button' and e.get('action_id','').startswith('nav_') for b in home['blocks'] for e in b.get('elements',[]))
    finally:d.pool.shutdown();st.db.close()


@pytest.mark.parametrize('paywalled',[False,True])
def test_public_reader_preserves_date_precision_and_respects_paywall(monkeypatch,paywalled):
    import io
    from coverage_desk import public_evidence as pe
    s=Settings(mode='live',allow_live=True);st=Store(s)
    monkeypatch.setattr(pe.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',80))])
    monkeypatch.setattr(pe.socket,'create_connection',lambda *a,**k:Mock())
    data={'datePublished':'2026-09-28','articleBody':'Public article evidence.','isAccessibleForFree':not paywalled}
    body=('<meta name="description" content="Public summary."><link rel="canonical" href="/story">'
        +'<script type="application/ld+json">'+json.dumps(data)+'</script>').encode()
    response=Mock(status=200);response.getheader.side_effect=lambda k:'text/html' if k=='Content-Type' else None
    response.read1.side_effect=io.BytesIO(body).read
    conn=Mock();conn.getresponse.return_value=response
    monkeypatch.setattr(pe.http.client,'HTTPConnection',lambda *a,**k:conn)
    try:
        result=pe.fetch_metadata('http://example.org/amp/story',s,st,threading.Event())
        assert result['published']=='2026-09-28' and result['date_precision']=='day'
        assert result['excerpt']==('Public summary.' if paywalled else 'Public article evidence.')
        assert result['canonical_url']=='http://example.org/story'
        assert st.budgets()['source']['used']==1
    finally:st.db.close()


def test_date_only_metadata_respects_exclusive_custom_period_end():
    from coverage_desk.overview import article_state
    m={'campaign':''};window={'start':'2026-09-20T00:00:00+00:00','end':'2026-09-29T00:00:00+00:00'}
    row={'date_precision':'day','date_kind':'publication','published':'2026-09-28','analysis':{'relevance':'relevant'}}
    assert article_state(row,m,window)=='confirmed'
    row['published']='2026-09-29'
    assert article_state(row,m,window)=='outside'


def test_denied_pages_are_cached_and_never_retried_on_resume(monkeypatch):
    from coverage_desk.workflow import read_sources
    from coverage_desk.sources import record
    s=Settings(mode='live',allow_live=True);st=Store(s);o=Actor('TEST','OWNER');d=Desk(s,st)
    m=d.monitor(o,{'name':'Example'})
    row=record('Example','https://example.org/story','Observed search evidence.','Codex web',{})
    row.update(monitor_id=m['id'],monitor_revision=m['revision'],scope_key=m['scope_key'])
    st.create(o,'finding',row)
    fetch=Mock(side_effect=DeskError('Public source did not permit page access.'))
    monkeypatch.setattr('coverage_desk.public_evidence.fetch_metadata',fetch)
    try:
        for _ in range(2):read_sources(d,o,m,coverage_overview(st,o,m)['rows'],threading.Event())
        assert fetch.call_count==1
        saved=st.list(o,'finding')[0]
        assert saved['text']=='Observed search evidence.' and not saved.get('published')
        assert 'did not permit' in saved['provenance']['publication_check']['status']
    finally:d.pool.shutdown();st.db.close()


def test_simple_filters_and_one_detail_correction():
    from coverage_desk.overview_ui import home_blocks,correction_modal
    s=Settings();st=Store(s);o=Actor('TEST','OWNER');d=Desk(s,st)
    try:
        m=d.monitor(o,{'name':'Example'})
        blocks=home_blocks(d,o,m,{'explore_view':'articles','coverage_state':'unassessed'})
        controls=[e for b in blocks for e in b.get('elements',[]) if e.get('action_id')=='coverage_state']
        assert [x['text']['text'] for x in controls[0]['options']]==['Relevant','Needs attention','All results']
        row={'id':'source','title':'Example','relevance':'relevant','content_type':'reporting'}
        for field in ('relevance','content_type','outlet_name','published'):
            modal=correction_modal(row,field,'Reviewed the source')
            inputs=[b for b in modal['blocks'] if b['type']=='input']
            assert len(inputs)==2
            assert inputs[-1]['element']['initial_value']=='Reviewed the source'
    finally:d.pool.shutdown();st.db.close()


def test_batch_sizing_includes_full_criteria_schema_and_publisher_metadata():
    from coverage_desk.workflow import batches
    from coverage_desk.runtime import CodexAnalyzer
    s=Settings(mode='live',allow_live=True);st=Store(s);o=Actor('TEST','OWNER');d=Desk(s,st)
    m=d.monitor(o,{'name':'Example','notes':'n'*1000,'messages':[str(i)+'m'*499 for i in range(8)]})
    rows=[{'id':str(i),'title':'Example report','text':'Evidence '*600,'url':'https://example.org/'+str(i),'access':'Public','provider':'Codex web',
        'provenance':{'publication_check':{'source_profile':{'publisher':'p'*180,'authors':['a'*180]*4,'article_types':['NewsArticle']}}}} for i in range(9)]
    ai=CodexAnalyzer(s,st);ai.status=Mock(return_value={'state':'Ready'});ai.call=Mock(return_value={'findings':[]})
    try:
        chunks=list(batches(rows,s,len(m['messages']),m))
        assert sum(map(len,chunks))==9 and len(chunks)>1
        for chunk in chunks:ai.analyze(chunk,m,threading.Event())
        assert all(len(json.dumps(c.args[1]))<=s.input_job for c in ai.call.call_args_list)
    finally:d.pool.shutdown();st.db.close()
