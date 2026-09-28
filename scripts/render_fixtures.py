"""Generate explicitly synthetic Block Kit payloads, without loading .env or networking."""
import json
from pathlib import Path
import sys
import threading
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from coverage_desk.config import Settings,ROOT
from coverage_desk.store import Store,Actor
from coverage_desk.service import Desk
from coverage_desk import ui
from slack_sdk.models.views import View

s=Settings(channel='C_FIXTURE');st=Store(s);desk=Desk(s,st);actor=Actor('TEST','OWNER')
out=ROOT/'docs/fixtures';out.mkdir(parents=True,exist_ok=True)
generated=[]
def save(name,view):
    generated.append(name)
    View(**view).validate_json()
    (out/(name+'.json')).write_text(json.dumps(view,indent=2,ensure_ascii=False),encoding='utf-8')
save('explore-empty',ui.home(desk,actor))
monitor=desk.monitor(actor,{'name':'Northstar · synthetic fixture','messages':['Products can be repaired.']})
desk.refresh(actor,monitor['id'],threading.Event())
st.preferences(actor,{'monitor':monitor['id']})
finding=st.list(actor,'finding')[0]
desk.analyze(actor,monitor['id'],[finding['id']],threading.Event())
save('explore',ui.home(desk,actor))
save('inspect',ui.detail(st.get(actor,finding['id'])))
board=desk.save(actor,finding['id'],'shared',True,True)
desk.perspective(Actor('TEST','FIXTURE_TEAMMATE'),board['id'],'Synthetic teammate perspective for offline payload review only.','Use in briefing')
st.preferences(actor,{'tab':'board'})
save('board',ui.home(desk,actor))
draft=desk.draft(actor,[board['id']])
st.preferences(actor,{'tab':'briefings'})
save('briefings',ui.home(desk,actor))
save('preview',ui.modal('Fixture preview',ui.briefing_blocks(draft),'publish_submit',{'id':'fixture'},'Publish'))
save('monitor-form',ui.monitor_modal())
save('settings',ui.settings_modal(desk,actor))
st.preferences(actor,{'tab':'explore'})
desk.jobs[actor.user]={'label':'Fixture work','state':'Working'}
save('loading',ui.home(desk,actor))
desk.jobs[actor.user]['state']='Usage limit — fixture state; no live request.'
save('error',ui.home(desk,actor))
save('monitor-advanced',ui.monitor_modal(expanded=True))
save('source-filters',ui.filters_modal({}))
for tab in ('overview','evidence','source','discussion'):
    save('finding-'+tab,ui.detail(st.get(actor,board['id']),True,tab))
for tab in ('explore','board','briefings'):
    save('help-'+tab,ui.help_modal(tab))
desk.jobs[actor.user]={'label':'Collecting coverage','state':'Working','stage':'Searching','active_target':'Instagram','retained':12,'checked_targets':2,'total_targets':5}
save('collection-progress',ui.home(desk,actor))
desk.jobs[actor.user].update(state='Partial results',retained=12)
save('collection-partial',ui.home(desk,actor))
desk.pool.shutdown()
print(f'{len(generated)} synthetic Slack payloads generated and validated; this is not a visual inspection.')
