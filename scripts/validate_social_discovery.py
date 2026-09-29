"""Explicit all-platform public discovery probe; no posts or monitor edits.

Uses the existing durable usage ledger and isolated runtime. All observed results
are retained in a task-owned, retention-cleaned research-comparison export.
"""
import argparse,json,threading,time
from coverage_desk.config import Settings,ROOT,DeskError
from coverage_desk.slack_app import bind
from coverage_desk.store import Store,Actor
from coverage_desk.runtime import CodexAnalyzer
from coverage_desk.scope import snapshot
from coverage_desk.discovery import PLATFORMS
from coverage_desk.research import search_tasks,initial_tasks,followup_tasks,registry,search_statuses,platform_summary

def main(args):
    s=Settings.load();bind(s);st=Store(s);a=Actor(s.workspace,s.owner)
    st.authorize(a,owner=True)
    if any(j.get('state') in ('Working','Queued') for j in st.list(a,'job')):raise DeskError('Wait for the active owner job.')
    original=next(m for m in st.list(a,'monitor') if m['name']==args.client)
    monitor={**original,'sources':list(PLATFORMS)};scope=snapshot(monitor)
    path=ROOT/'data'/('research-comparison-social-'+args.attempt+'.json')
    if path.exists() or not st.claim('social-validation:'+args.attempt):raise DeskError('Use a new explicit attempt name; never silently retry.')
    # Deterministic public criteria probe avoids an extra planning job. The owner
    # workflow itself is validated separately through validate_overview refresh.
    plan={'queries':[{'query':monitor['name']+' '+monitor.get('campaign',''),'purpose':'focus'}]}
    tasks=initial_tasks(search_tasks(monitor,plan,scope),s.calls);observed=[];follow=[]
    report={'scope':scope,'usage_before':st.budgets(),'assessment':'Discovery only; labels are not quality judgments'}
    ai=CodexAnalyzer(s,st);started=time.monotonic()
    try:
        envelope=ai.discover(scope,tasks,threading.Event());observed=envelope.get('observed',[])
        if not envelope.get('limited') and not envelope.get('interrupted'):
            follow=followup_tasks(monitor,scope,tasks,observed,s.calls-len(tasks)-1)
            if follow:
                second=ai.discover(scope,follow,threading.Event())
                observed += [{**e,'id':'follow:'+str(e.get('id',''))} for e in second.get('observed',[])]
                envelope=second
        report['interrupted']=envelope.get('interrupted','');report['limited']=envelope.get('limited',False)
    except DeskError as exc:report['error']=str(exc)
    finally:
        statuses=search_statuses(tasks+follow,observed);rows=registry({'observed':observed})
        report.update(tasks=tasks+follow,statuses=statuses,observed=observed,rows=rows,
            platforms=platform_summary(monitor,rows,statuses,follow),usage_after=st.budgets(),elapsed=round(time.monotonic()-started,1))
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:report.get(k) for k in ('platforms','error','interrupted','limited','elapsed','usage_before','usage_after')}))
        st.db.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--client',required=True)
    p.add_argument('--attempt',required=True,type=lambda x:x if x.replace('-','').isalnum() else p.error('Use an alphanumeric attempt.'))
    main(p.parse_args())
