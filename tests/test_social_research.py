from datetime import datetime,timezone
from coverage_desk.scope import snapshot
from coverage_desk.research import search_tasks

def setup():
    m={'name':'Acme Robotics','aliases':['Acme Labs','@acme'],'campaign':'Nova launch',
       'sources':['news','web','instagram','x','linkedin','facebook','tiktok','reddit','youtube'],
       'freshness':'pm','messages':['PRIVATE MESSAGE'],'notes':'PRIVATE NOTE'}
    p={'queries':[{'query':'Acme Robotics Nova launch','purpose':'focus'}]}
    return m,p,snapshot(m,datetime(2026,9,29,tzinfo=timezone.utc).timestamp())

def test_social_initial_queries_include_aliases_without_collapsing_campaign():
    m,p,s=setup()
    m['domains']='example.org @acmeofficial'
    tasks=search_tasks(m,p,s)
    for target in m['sources'][2:]:
        q=next(t['query'] for t in tasks if t['target']==target)
        assert 'Acme Labs' in q and '@acme' in q and ' OR ' in q
        assert '@acmeofficial' in q
        assert ') Nova launch' in q and 'Nova launch OR' not in q
        assert 'PRIVATE' not in q


def test_general_entity_disambiguation_survives_social_expansion():
    m,p,s=setup();m.update(name='Juniper',aliases=[],campaign='',sources=['x'])
    p={'queries':[{'query':'Juniper Networks news','purpose':'broad'}]}
    tasks=search_tasks(m,p,s)
    assert 'Networks' in tasks[0]['query'] and ' news' not in tasks[0]['query']
    m.update(name='Meta',campaign='Metaverse')
    p={'queries':[{'query':'Meta Metaverse','purpose':'focus'}]}
    assert '(Meta) Metaverse' in search_tasks(m,p,s)[0]['query']

def test_breadth_before_followups_and_total_reservations_bounded():
    from coverage_desk.research import initial_tasks,followup_tasks
    m,p,s=setup();tasks=initial_tasks(search_tasks(m,p,s),12)
    assert len(tasks)==10 and {t['target'] for t in tasks}==set(m['sources'])
    assert any(t['target']=='news' and t['purpose']=='broad' for t in tasks)
    events=[{'query':t['query'],'results':[]} for t in tasks]
    follow=followup_tasks(m,s,tasks,events,12-len(tasks)-1)
    assert len(follow)==1 and len(tasks)+len(follow)+2<=13
    assert all('after:' not in t['query'] and 'before:' not in t['query'] for t in follow)
    assert all('Nova launch' in t['query'] for t in follow)

def test_followup_only_observed_selected_public_platform_and_no_retry():
    from coverage_desk.research import followup_tasks
    m,p,s=setup();m['sources']=['x']
    tasks=[{'target':'x','query':'Acme site:x.com','purpose':'focus'}]
    hit={'type':'text_result','url':'https://x.com/acme/status/123','title':'Acme Nova','snippet':'Acme launch #Nova'}
    events=[{'query':tasks[0]['query'],'results':[hit]}]
    follow=followup_tasks(m,s,tasks,events,3)
    assert any(t['purpose']=='evidence' and hit['url'] in t['query'] for t in follow)
    assert any('#Nova' in t['query'] for t in follow)
    assert not followup_tasks(m,s,tasks,[],3)
    events[0]['results']=[{**hit,'url':'https://x.com.evil.org/acme/status/123'}]
    assert all('evil' not in t['query'] for t in followup_tasks(m,s,tasks,events,3))
    events[0]['results']=[{**hit,'url':'https://x.com/acme'}]
    assert not any(t['purpose']=='evidence' for t in followup_tasks(m,s,tasks,events,3))

def test_platform_summary_counts_unique_evidence_not_generated_claims():
    from coverage_desk.research import platform_summary
    m,p,s=setup();m['sources']=['x','instagram']
    rows=[{'url':'https://x.com/a/status/1','text':'observed','analysis':{}},
          {'url':'https://x.com/a/status/1?utm_source=repeat','text':'observed','analysis':{'relevance':'relevant'}}]
    result=platform_summary(m,rows,[{'target':'x','requested':True}],[])
    assert result[0]['found']==1 and result[0]['assessed']==1 and result[0]['excerpt_only']==1
    assert result[1]['status']=='Not searched'


def test_social_date_only_requires_explicit_observed_publication_field():
    from coverage_desk.research import registry
    hit={'type':'text_result','url':'https://x.com/acme/status/1','title':'Acme','snippet':'Published September 2, 2026'}
    def result(**fields):
        return registry({'observed':[{'type':'webSearch','results':[{**hit,**fields}]}]})[0]
    assert result()['published'] is None
    assert result(date='2026-09-02',retrieved_at='2026-09-02')['published'] is None
    dated=result(datePublished='2026-09-02')
    assert dated['published']=='2026-09-02' and dated['date_precision']=='day'
    assert result(datePublished='2026-09-02T12:00:00')['published'] is None


def test_second_pass_integrates_observed_text_then_assesses_once(monkeypatch):
    import threading
    from unittest.mock import Mock
    from coverage_desk.config import Settings
    from coverage_desk.store import Store,Actor
    from coverage_desk.service import Desk
    from coverage_desk.overview import project_articles
    s=Settings(mode='live',allow_live=True,calls=5);st=Store(s);a=Actor('TEST','OWNER');ai=Mock();d=Desk(s,st,ai)
    m=d.monitor(a,{'name':'Acme','sources':['x'],'research_path':'Codex native web'})
    ai.plan.return_value={'interpretation':'Public Acme coverage','queries':[{'query':'Acme','target':'x','purpose':'broad'}]}
    def discover(scope,tasks,cancel):
        second=ai.discover.call_count==2
        return {'observed':[{'id':'reused','type':'webSearch','query':tasks[0]['query'],'results':[
            {'type':'text_result','url':'https://x.com/acme/status/123','title':'Acme launch',
             'snippet':'Acme launch #Nova' if not second else 'Acme launches Nova tomorrow.','ref_id':'result1'}]}]}
    ai.discover.side_effect=discover
    ai.analyze.side_effect=lambda rows,monitor,cancel:{'findings':[{'source_id':r['id'],'relevance':'relevant','campaign_relevance':'not_applicable','explanation':'Names client','messages':[]} for r in rows]}
    ai.classify_coverage.side_effect=lambda rows,cancel:{'findings':[{'source_id':r['id'],'coverage':{'content_type':'unknown','evidence':'','outlet_name':'','redistribution':''}} for r in rows]}
    monkeypatch.setattr('coverage_desk.public_evidence.fetch_metadata',lambda *a: (_ for _ in ()).throw(AssertionError('No social scraping')))
    try:
        d.research(a,m['id'],threading.Event())
        row=project_articles(st,a,m)['rows'][0];run=st.list(a,'run')[0]
        assert ai.discover.call_count==2 and ai.analyze.call_count==1
        assert 'Acme launch #Nova' in row['text'] and 'Acme launches Nova tomorrow.' in row['text']
        assert len(row['observations'])==2 and row['analysis']
        assert {o['provenance']['event_id'] for o in row['observations']}=={'1:reused','2:reused'}
        assert run['reserved_source_slots']<=s.calls+1 and run['platforms'][0]['assessed']==1
        assert sum(len(c.args[1]) for c in ai.discover.call_args_list)<=s.calls
    finally:d.pool.shutdown()


def test_combined_excerpts_preserve_scope_original_text_and_earliest_expiry():
    import time
    from coverage_desk.config import Settings
    from coverage_desk.store import Store,Actor
    from coverage_desk.service import Desk
    from coverage_desk.sources import record
    from coverage_desk.workflow import combine_social_evidence
    from coverage_desk.scope import scope_key
    from coverage_desk.overview import project_articles
    st=Store(Settings());a=Actor('TEST','OWNER');d=Desk(st.s,st)
    try:
        m=d.monitor(a,{'name':'Acme','sources':['x']});early=time.time()+100
        def create(text,scope,expiry):
            r=record('Acme','https://x.com/acme/status/1',text,'Codex web',{})
            r.update(monitor_id=m['id'],monitor_revision=m['revision'],scope_key=scope)
            return st.create(a,'finding',r,expires=expiry)
        first=create('First observed excerpt',scope_key(m),early)
        first.update(published='2026-09-02',date_kind='publication',date_precision='day');st.update(a,first['id'],first)
        second=create('Second observed excerpt',scope_key(m),early+100)
        create('Different scope private text','other',early+200)
        rows=project_articles(st,a,m)['rows']
        assert rows[0]['published']=='2026-09-02' and rows[0]['date_precision']=='day'
        combine_social_evidence(d,a,m,rows)
        updated=st.get(a,second['id'])
        assert updated['expires']==early and updated['text']=='Second observed excerpt\n\nFirst observed excerpt'
        assert st.get(a,first['id'])['text']=='First observed excerpt'
        assert updated['provenance']['original_search_excerpt']=='Second observed excerpt'
        combine_social_evidence(d,a,m,project_articles(st,a,m)['rows'])
        assert st.get(a,second['id'])['text']==updated['text']
    finally:d.pool.shutdown()


def test_limited_or_cancelled_discovery_never_runs_followup(monkeypatch):
    import threading
    from unittest.mock import Mock
    from coverage_desk.config import Settings
    from coverage_desk.store import Store,Actor
    from coverage_desk.service import Desk
    for limited in (True,False):
        st=Store(Settings(mode='live',allow_live=True));a=Actor('TEST','OWNER');ai=Mock();d=Desk(st.s,st,ai);cancel=threading.Event()
        m=d.monitor(a,{'name':'Acme','sources':['x']})
        ai.plan.return_value={'interpretation':'Acme','queries':[{'query':'Acme','target':'x','purpose':'broad'}]}
        def discover(scope,tasks,event):
            if not limited:event.set()
            return {'observed':[{'id':'a','type':'webSearch','query':tasks[0]['query'],'results':[]}],'limited':limited}
        ai.discover.side_effect=discover
        try:
            d.research(a,m['id'],cancel)
            assert ai.discover.call_count==1 and not ai.analyze.called
        finally:d.pool.shutdown()
