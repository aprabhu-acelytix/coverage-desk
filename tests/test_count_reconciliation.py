import json
from test_overview import env,article,overview
from coverage_desk.overview_ui import home_blocks

def test_relevant_findings_partition_into_counted_dates_and_types(env):
    d,st,o,m=env
    article(st,o,m)
    article(st,o,m,'https://a.example/undated',date=None)
    article(st,o,m,'https://social.example/post',kind='social',date=None)
    article(st,o,m,'https://unknown.example/post',kind='unknown')
    article(st,o,m,'https://a.example/old',date='2020-01-01T00:00:00Z')
    article(st,o,m,'https://a.example/pending',assessed=False)
    data=overview(env)
    assert data['reconciliation']=={'relevant':4,'counted':4,'date_unconfirmed':2,'other_type':0}
    assert overview(env,content_type='reporting')['reconciliation']=={'relevant':4,'counted':2,'date_unconfirmed':1,'other_type':2}
    text=json.dumps(home_blocks(d,o,m,{'explore_view':'overview'}))
    assert '4 relevant findings' in text and '2 dates unconfirmed' in text
    text=json.dumps(home_blocks(d,o,m,{'explore_view':'articles'}))
    assert '4 relevant findings' in text and '4 counted in Overview' in text

def test_outlet_relevant_drilldown_includes_counted_undated_matches(env):
    d,st,o,m=env
    counted=article(st,o,m)
    undated=article(st,o,m,'https://a.example/undated',date=None)
    data=overview(env);outlet=data['outlets'][0]
    text=json.dumps(home_blocks(d,o,m,{'explore_view':'articles','outlet':outlet['id'],'coverage_state':'confirmed'}))
    assert counted['id'] in text and undated['id'] in text
    assert '2 relevant findings' in text
    attention=json.dumps(home_blocks(d,o,m,{'explore_view':'articles','outlet':outlet['id'],'coverage_state':'attention'}))
    assert undated['id'] in attention

def test_shared_preview_freezes_unknown_dates_without_inventing_publication(env):
    from coverage_desk.overview_ui import snapshot_modal
    d,st,o,m=env
    r=article(st,o,m,date=None)
    draft=d.overview_snapshot(o,m['id'],confirmed=True)
    assert draft['overview']['article_count']==1
    assert draft['overview']['unconfirmed_date_count']==1
    assert draft['overview']['sources'][0]['published'] is None
    assert 'Publication date unconfirmed' in json.dumps(snapshot_modal(draft))
    assert any('unconfirmed' in c for c in draft['overview']['caveats'])

def test_inclusion_migration_preserves_records_usage_and_later_filter_choice(tmp_path):
    from coverage_desk.config import Settings
    from coverage_desk.store import Store,Actor
    st=Store(Settings(database=str(tmp_path/'desk.sqlite3')));o=Actor('TEST','OWNER')
    st.migrate_overview()
    st.db.execute("DELETE FROM migrations WHERE name='overview-v2'");st.db.commit()
    st.preferences(o,{'content_type':'reporting','monitor':'keep','outlet':'old'})
    saved=st.create(o,'briefing',{'title':'Keep frozen snapshot','overview':{'article_count':1}})
    st.consume('ai');st.consume('source');before=st.budgets()
    backup=st.migrate_overview()
    assert backup.exists() and st.preferences(o)['content_type']=='all'
    assert st.preferences(o)['monitor']=='keep' and not st.preferences(o)['outlet']
    assert st.get(o,saved['id'])==saved and st.budgets()==before
    st.preferences(o,{'content_type':'reporting'})
    assert st.migrate_overview() is None and st.preferences(o)['content_type']=='reporting'
    st.db.close()


def test_unknown_dates_count_across_pages_and_chart_remainder(env):
    from coverage_desk.overview import chart_block
    d,st,o,m=env
    for i in range(38):
        article(st,o,m,f'https://outlet{i%12}.example/{i}',date=None)
    article(st,o,m,'https://outlet0.example/0?utm_source=repeat',date=None)
    data=overview(env)
    assert data['article_count']==data['unconfirmed_date_count']==38
    assert data['outlet_count']==12
    assert sum(p['value'] for p in chart_block(data)['chart']['series'][0]['data'])==38
    assert sum(len(o['articles']) for o in data['outlets'])==38
