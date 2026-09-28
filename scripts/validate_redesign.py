"""Explicit, resumable redesign check: <=2 source calls, no AI and no posts."""
from dataclasses import replace
import json
import argparse
from pathlib import Path
import sys
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from coverage_desk.config import Settings,ROOT,DeskError
from coverage_desk.store import Store,Actor
from coverage_desk.service import Desk
from coverage_desk.sources import Brave
from coverage_desk.slack_app import bind
from coverage_desk import ui


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--verify-social-fix',action='store_true',help='Explicitly authorize two further source checks of corrected queries, within the original ledger.')
    verify=parser.parse_args().verify_social_fix
    check_key='corrected_social_checks' if verify else 'social_checks'
    s=Settings.load();client,_=bind(s);st=Store(s);actor=Actor(s.workspace,s.owner);desk=Desk(s,st)
    path=ROOT/'data/redesign-validation.json'
    report=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    try:
        if st.claim('redesign-validation:source:v2' if verify else 'redesign-validation:source:v1'):
            monitor=next((m for m in st.list(actor,'monitor') if m['name'].casefold()=='patagonia'),None)
            if not monitor:monitor=desk.monitor(actor,{'name':'Patagonia','sources':['instagram','linkedin']})
            # An explicit one-off check leaves the owner's saved search configuration unchanged.
            check={**monitor,'sources':['instagram','linkedin'],'aliases':[],'campaign':''}
            run=st.create(actor,'run',{'monitor_id':monitor['id'],'statuses':[],'count':0,'mode':'live',
                'pages_cap':1,'calls_cap':2,'checked':time.time(),'enabled_sources':check['sources'],'outcome':'Searching'})
            saved=[]
            def retain(rows,statuses):
                for row in rows:
                    saved.append(st.create(actor,'finding',{**row,'monitor_id':monitor['id'],'monitor_revision':monitor['revision']}))
                run.update(statuses=statuses,count=len(saved),checked=time.time())
                st.update(actor,run['id'],run)
            try:
                rows,statuses=Brave(replace(s,pages=1,calls=2,results=5),st).retrieve(check,threading.Event(),on_page=retain)
                failures=any(x['status'] not in ('Results','No matches') for x in statuses)
                run.update(statuses=statuses,count=len(saved),outcome='Partial results' if failures and saved else 'Unavailable' if failures else 'Ready' if saved else 'No matches')
                st.update(actor,run['id'],run)
                report[check_key]=[{'target':x.get('target'),'outcome':x['status'],'results':x.get('results',0),'platform_matches':x.get('platform_matches',0)} for x in statuses]
                report['corrected_retained' if verify else 'retained']=len(saved)
            except Exception:
                run.update(outcome='Partial results' if saved else 'Interrupted',count=len(saved))
                st.update(actor,run['id'],run)
                report['social_check_error']='Interrupted; no automatic retry. Saved findings preserved.'
        desk.runtime_state='Use Check AI connection to verify'
        p=st.preferences(actor)
        report['home_views']={}
        try:
            for tab in ('explore','board','briefings'):
                st.preferences(actor,{'tab':tab,'page':0})
                client.views_publish(user_id=actor.user,view=ui.home(desk,actor))
                report['home_views'][tab]='accepted by Slack'
        finally:
            st.preferences(actor,p)
            client.views_publish(user_id=actor.user,view=ui.home(desk,actor))
        report.update(budgets=st.budgets(),ai_jobs_this_check=0,channel_posts=0,visual_inspection='No UI surface available')
        path.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
    finally:desk.pool.shutdown()


if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('Validation did not finish. No automatic retry; inspect the saved report and local readiness.') from None
