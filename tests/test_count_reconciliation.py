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
    assert data['reconciliation']=={'relevant':4,'counted':1,'date_unconfirmed':2,'other_type':1}
    assert overview(env,content_type='all')['reconciliation']=={'relevant':4,'counted':2,'date_unconfirmed':2,'other_type':0}
    text=json.dumps(home_blocks(d,o,m,{'explore_view':'overview'}))
    assert '1 confirmed reporting article' in text and '4 relevant findings' in text
    text=json.dumps(home_blocks(d,o,m,{'explore_view':'articles'}))
    assert '4 relevant findings' in text and '1 counted in Overview' in text

def test_outlet_relevant_drilldown_matches_its_count_not_undated_matches(env):
    d,st,o,m=env
    counted=article(st,o,m)
    undated=article(st,o,m,'https://a.example/undated',date=None)
    data=overview(env);outlet=data['outlets'][0]
    text=json.dumps(home_blocks(d,o,m,{'explore_view':'articles','outlet':outlet['id'],'coverage_state':'confirmed'}))
    assert counted['id'] in text and undated['id'] not in text
    assert '1 relevant finding' in text
    attention=json.dumps(home_blocks(d,o,m,{'explore_view':'articles','outlet':outlet['id'],'coverage_state':'attention'}))
    assert undated['id'] in attention
