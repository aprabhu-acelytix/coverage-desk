import threading,time
from unittest.mock import Mock
import pytest
from coverage_desk.config import Settings
from coverage_desk.store import Store,Actor
from coverage_desk.service import Desk
from coverage_desk.sources import record
from coverage_desk.discovery import finding_selection
from coverage_desk import ui

@pytest.fixture
def research_setup():
 s=Settings();st=Store(s);d=Desk(s,st);o=Actor('TEST','OWNER')
 m=d.monitor(o,{'name':'Patagonia','notes':'Clothing brand, not the region','campaign':'repair','messages':['Repair services'],'freshness':'pw'})
 yield d,st,o,m
 d.pool.shutdown()

def add(st,o,m,url='https://example.org/story',campaign='relevant',published='recent',assessed=True):
 if published=='recent':
  from datetime import datetime,timezone,timedelta
  published=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
 r=record('Critical report',url,'The repair program faces criticism.','Brave news',{},published)
 r.update(monitor_id=m['id'],monitor_revision=m['revision'],scope_key=m.get('scope_key','missing'),date_kind='publication',analysis_scope_key=m.get('scope_key','missing'))
 if assessed:r['analysis']={'source_id':'pending','relevance':'relevant','campaign_relevance':campaign,'explanation':'Critical campaign reporting.','messages':[{'message':'Repair services','label':'not_observed_in_available_text','explanation':'Not in excerpt','evidence':[]}]}
 return st.create(o,'finding',r)

def selection(st,o,m,view='all'):
 p={'monitor':m['id'],'filter':view,'source_filter':'all','page':0,'snapshot':time.time()+1,'history':'current'}
 return finding_selection(st,o,p)

def test_three_observations_project_to_one_card(research_setup):
 d,st,o,m=research_setup
 for i in range(3):add(st,o,m,'https://example.org/story?utm_source='+str(i))
 result=selection(st,o,m)
 assert len(result['rows'])==1
 assert len(result['rows'][0]['observations'])==3
 assert len(st.list(o,'finding'))==3

def test_alternate_observation_saves_same_board(research_setup):
 d,st,o,m=research_setup;d.s.storage_allowed=True
 a=add(st,o,m);b=add(st,o,m,'https://example.org/story?utm_source=repeat')
 first=d.save(o,a['id'],'shared',True);d.perspective(o,first['id'],'Preserve my note')
 second=d.save(o,b['id'],'shared',True)
 assert first['id']==second['id']
 assert second['perspectives'][0]['text']=='Preserve my note'

def test_similar_headlines_do_not_merge_meaningful_urls(research_setup):
 d,st,o,m=research_setup
 add(st,o,m,'https://example.org/story?id=1');add(st,o,m,'https://example.org/story?id=2')
 assert len(selection(st,o,m)['rows'])==2

@pytest.mark.parametrize('change',[{'name':'Other'},{'campaign':'climate'},{'messages':['Different']},{'freshness':'pd'},{'sources':['web']}])
def test_edits_cannot_show_old_scope_as_current(research_setup,change):
 d,st,o,m=research_setup;add(st,o,m)
 newer=d.monitor(o,{**m,**change},m['id'])
 assert not selection(st,o,newer)['rows']

def test_focused_default_preserves_critical_and_message_absence(research_setup):
 d,st,o,m=research_setup
 add(st,o,m,campaign='not_relevant');good=add(st,o,m,'https://example.org/critical')
 assert [r['id'] for r in selection(st,o,m,'relevant')['rows']]==[good['id']]

def test_unknown_dates_and_pending_are_review_not_relevant(research_setup):
 d,st,o,m=research_setup
 add(st,o,m,published=None);add(st,o,m,'https://example.org/pending',assessed=False)
 assert not selection(st,o,m,'relevant')['rows']
 assert len(selection(st,o,m,'review')['rows'])==2

def test_results_first_removes_repeated_heading_and_page_analysis(research_setup):
 d,st,o,m=research_setup;add(st,o,m);st.preferences(o,{'monitor':m['id']})
 blocks=ui.home(d,o)['blocks']
 assert not any(b.get('text',{}).get('text')=='Coverage Desk' for b in blocks)
 assert not any(e.get('action_id')=='analyze_page' for b in blocks for e in b.get('elements',[]))

def test_published_briefing_has_correct_action(research_setup):
 d,st,o,m=research_setup
 st.create(o,'briefing',{'title':'Published update','text':'Body','status':'Published','revision':1,'sources':[],'board_ids':[]})
 st.preferences(o,{'tab':'briefings'})
 labels=[e.get('text',{}).get('text') for b in ui.home(d,o)['blocks'] if b['type']=='actions' for e in b.get('elements',[])]
 assert 'View briefing' in labels and 'View draft' not in labels


def test_analysis_cache_reuses_identity_not_observation_id(research_setup):
 d,st,o,m=research_setup;d.s.storage_allowed=True
 a=add(st,o,m,assessed=False)
 d.analyze(o,m['id'],[a['id']],threading.Event())
 b=add(st,o,m,assessed=False);b.update(published=a['published']);st.update(o,b['id'],b)
 from coverage_desk.scope import version
 assert version(a)==version(b)
 d.analyzer=Mock()
 # A fixture result can be reused only in fixture mode; model and context changes invalidate.
 result=d.analyze(o,m['id'],[b['id']],threading.Event())
 assert result['findings'][0]['source_id']==b['id'] and not d.analyzer.analyze.called
 assert d.analysis_key(o,a,m)==d.analysis_key(o,b,m)
 changed=d.monitor(o,{**m,'messages':['Different']},m['id'])
 assert d.analysis_key(o,a,changed)!=d.analysis_key(o,a,m)
 with pytest.raises(Exception,match='previous search scope'):d.analyze(o,m['id'],[a['id']],threading.Event())


def test_unique_pagination_counts_and_previous_scope(research_setup):
 d,st,o,m=research_setup
 for i in range(12):
  add(st,o,m,'https://example.org/'+str(i//2))
 p={'monitor':m['id'],'filter':'all','snapshot':time.time(),'page':1}
 result=finding_selection(st,o,p)
 assert result['counts']['all']==6 and len(result['visible'])==1
 d.monitor(o,{**m,'campaign':'Changed'},m['id'])
 assert not finding_selection(st,o,p)['rows']
 assert len(finding_selection(st,o,{**p,'history':'previous'})['rows'])==6


def test_custom_date_end_is_exclusive_and_preview_title_invalidates(research_setup):
 from coverage_desk.scope import snapshot,eligibility
 d,st,o,m=research_setup
 m=d.monitor(o,{**m,'freshness':'2026-09-01to2026-09-02'},m['id'])
 r=add(st,o,m,published='2026-09-03T00:00:00+00:00')
 assert eligibility(r,m,snapshot(m))[0]=='outside'
 d.s.storage_allowed=True;d.s.channel='PUBLIC'
 b=d.save(o,r['id'],'shared',True);draft=d.draft(o,[b['id']]);preview=d.preview(o,draft['id'])
 d.edit_draft(o,draft['id'],draft['text'],1,'Changed title')
 with pytest.raises(Exception,match='changed'):d.publish(o,preview['id'],Mock())


def test_usage_error_remains_visible_without_a_run(research_setup):
 d,st,o,m=research_setup;st.preferences(o,{'monitor':m['id']})
 d.jobs[o.user]={'state':'Usage limit','label':'Researching','monitor_id':m['id'],'error':'Usage limit: two AI jobs needed.'}
 assert 'Usage limit: two AI jobs needed.' in str(ui.home(d,o))


def test_new_version_cannot_replace_saved_snapshot_assessment(research_setup):
 from coverage_desk.models import digest
 from coverage_desk.config import DeskError
 d,st,o,m=research_setup;d.s.storage_allowed=True
 first=add(st,o,m);board=d.save(o,first['id'],'shared',True)
 newer=add(st,o,m);newer.update(text='Different evidence',hash=digest('Different evidence'));st.update(o,newer['id'],newer)
 with pytest.raises(DeskError,match='earlier evidence snapshot'):d.save(o,newer['id'],'shared',True,True)
 assert st.get(o,board['id'])['text']==first['text']
