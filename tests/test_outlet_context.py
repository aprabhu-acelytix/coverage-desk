"""Offline owner review and transparent outlet-priority regressions."""
import json,time
import pytest
from coverage_desk import ui
from coverage_desk.config import DeskError
from coverage_desk.store import Actor
from coverage_desk.overview import coverage_overview
from test_overview import env,article
from test_redesign import app_env,action,await_true
from test_redesign import form_view,submit


def test_correction_moves_into_inspect_and_mark_relevant_is_in_row(env):
    d,st,o,m=env;r=article(st,o,m,assessed=False)
    st.preferences(o,{'monitor':m['id'],'explore_view':'articles','coverage_state':'attention','snapshot':time.time()})
    home=ui.home(d,o)
    assert 'coverage_correct' not in json.dumps(home)
    assert 'Mark relevant' in json.dumps(home)
    detail=ui.detail(d.finding_detail(o,r['id']))
    assert 'Edit finding' in json.dumps(detail)


def test_source_details_starts_with_outlet_context(env):
    d,st,o,m=env;r=article(st,o,m,'https://arstechnica.com/example')
    view=ui.detail(d.finding_detail(o,r['id']),tab='source')
    text=json.dumps(view)
    assert 'About this outlet' in text and 'Significance' in text and 'Editorial signals' in text
    assert 'https://arstechnica.com/about-us/' in text


def test_established_reporting_precedes_newer_unreviewed_without_changing_counts(env):
    d,st,o,m=env
    known=article(st,o,m,'https://arstechnica.com/example')
    unknown=[article(st,o,m,f'https://unreviewed.example/newer-{i}') for i in range(7)]
    data=coverage_overview(st,o,m)
    assert data['rows'][0]['id']==known['id']
    assert data['article_count']==8 and data['outlet_count']==2
    assert {r['id'] for r in data['rows'][1:]}=={r['id'] for r in unknown}
    from coverage_desk.discovery import finding_selection
    selected=finding_selection(st,o,{'monitor':m['id'],'filter':'all','snapshot':time.time()})
    assert selected['visible'][0]['id']==known['id']
    assert len(selected['rows'])==8
    st.preferences(o,{'monitor':m['id'],'explore_view':'articles','coverage_state':'confirmed','page':0,'snapshot':time.time()})
    assert known['id'] in json.dumps(ui.home(d,o))
    st.preferences(o,{'page':1})
    assert known['id'] not in json.dumps(ui.home(d,o))


def test_mark_relevant_dispatch_preserves_dates_messages_and_usage(app_env):
    app,d,st,c,o=app_env;m=d.monitor(o,{'name':'Synthetic client','campaign':'Launch'})
    r=article(st,o,m,date=None);r['analysis']['campaign_relevance']='uncertain';st.update(o,r['id'],r)
    before=st.get(o,r['id'])['analysis'];budget=st.budgets()
    st.preferences(o,{'monitor':m['id'],'snapshot':time.time()})
    action(app,'mark_relevant',r['id'])
    await_true(lambda:bool(st.list(o,'coverage_review')))
    data=coverage_overview(st,o,m)
    assert data['rows'][0]['relevance']=='relevant'
    assert data['rows'][0]['date_status']=='unconfirmed' and data['article_count']==1
    assert st.get(o,r['id'])['analysis']==before and st.budgets()==budget
    assert 'date' in st.preferences(o)['notice'].lower()
    d.mark_relevant(o,r['id'])
    assert len(st.list(o,'coverage_review'))==1


def test_outlet_priority_exact_host_private_and_snapshot_stable(env):
    d,st,o,m=env
    known=article(st,o,m,'https://arstechnica.com/example')
    unknown=article(st,o,m,'https://local.example/story')
    at=time.time();budget=st.budgets()
    d.set_outlet_priority(o,unknown['id'],'high','Relevant specialist for our audience')
    data=coverage_overview(st,o,m)
    assert data['rows'][0]['id']==unknown['id'] and data['article_count']==2
    assert coverage_overview(st,o,m,at=at)['rows'][0]['id']==known['id']
    assert not st.list(Actor('TEST','OTHER'),'outlet_priority')
    with pytest.raises(DeskError):d.set_outlet_priority(Actor('TEST','OTHER'),unknown['id'],'high','No')
    assert st.budgets()==budget


def test_profile_never_transfers_to_lookalikes_or_sponsored_content():
    from coverage_desk.outlets import outlet_context
    assert outlet_context({'url':'https://arstechnica.com/story','content_type':'reporting'})['rank']==2
    for url in ('https://arstechnica.com.evil.example/story','https://blogs.arstechnica.com/story'):
        assert outlet_context({'url':url,'content_type':'reporting'})['rank']==1
    assert outlet_context({'url':'https://arstechnica.com/story','content_type':'sponsored'})['rank']==1


def test_priority_form_dispatch_and_reset_refresh_parent(app_env):
    app,d,st,c,o=app_env;m=d.monitor(o,{'name':'Synthetic client','campaign':'Launch'})
    r=article(st,o,m,'https://arstechnica.com/story')
    parent=ui.detail(d.finding_detail(o,r['id']),tab='source');parent.update(id='INSPECT',hash='one')
    action(app,'outlet_priority',r['id'],parent)
    await_true(lambda:c.views_push.called)
    view=c.views_push.call_args.kwargs['view']
    meta=json.loads(view['private_metadata'])
    assert meta['parent']['id']=='INSPECT'
    form=form_view({'priority':'low','reason':'Lower priority for our audience'},meta)
    form['callback_id']='outlet_priority_submit';submit(app,form)
    await_true(lambda:c.views_update.called)
    assert c.views_update.call_args.kwargs['view_id']=='INSPECT'
    assert d.finding_detail(o,r['id'])['outlet_context']['rank']==0
    d.set_outlet_priority(o,r['id'],'default','Restore the reviewed default')
    assert d.finding_detail(o,r['id'])['outlet_context']['rank']==2


def test_private_priority_reason_never_enters_shared_snapshot_or_board(env):
    d,st,o,m=env;r=article(st,o,m)
    d.set_outlet_priority(o,r['id'],'high','PRIVATE OUTLET STRATEGY')
    board=d.save(o,r['id'],'shared',True)
    draft=d.overview_snapshot(o,m['id'],confirmed=True)
    assert 'PRIVATE OUTLET STRATEGY' not in json.dumps(board)
    assert 'PRIVATE OUTLET STRATEGY' not in json.dumps(draft)
    assert 'PRIVATE OUTLET STRATEGY' not in json.dumps(ui.detail(board,True,tab='source'))


def test_mark_relevant_rejects_teammates_old_scopes_and_wrong_workspace(env):
    d,st,o,m=env;r=article(st,o,m,assessed=False)
    for other in (Actor('TEST','OTHER'),Actor('OTHER',o.user)):
        with pytest.raises(DeskError):d.mark_relevant(other,r['id'])
    d.monitor(o,{**m,'campaign':'Changed'},m['id'])
    with pytest.raises(DeskError):d.mark_relevant(o,r['id'])
    assert not st.list(o,'coverage_review')


def test_catalog_has_reviewable_references_and_no_duplicate_hosts():
    from coverage_desk.outlets import catalog
    from pathlib import Path
    import coverage_desk.outlets as outlets
    raw=json.loads(Path(outlets.__file__).with_name('outlet_profiles.json').read_text(encoding='utf-8'))
    hosts=[host for e in raw for host in e['hosts']]
    assert len(hosts)==len(set(hosts))
    entries=list(catalog().values())
    assert entries and all(e['references'] and e['reviewed_on'] for e in entries)
    assert all(r['url'].startswith('https://') for e in entries for r in e['references'])
