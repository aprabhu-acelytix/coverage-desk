"""Explicit owner-operated live comparison. No posts or automatic retries."""
import argparse,json,threading,time
from coverage_desk.config import Settings,ROOT,DeskError
from coverage_desk.store import Store,Actor
from coverage_desk.slack_app import bind
from coverage_desk.runtime import CodexAnalyzer
from coverage_desk.service import Desk
from coverage_desk.discovery import finding_selection

def main(case,attempt,continue_only=False):
    s=Settings.load();client,_=bind(s);st=Store(s);owner=Actor(s.workspace,s.owner)
    desk=Desk(s,st,CodexAnalyzer(s,st))
    name={'campaign':'Stephen Curry','brand':'Patagonia'}[case]
    monitors=[m for m in st.list(owner,'monitor') if m['name']==name and m.get('validation_case') in (None,'general-v2-brand')]
    if not st.claim(f'general-research-v2:{case}:{attempt}'):
        raise DeskError('Already attempted; inspect saved evidence. Use a new explicit attempt only after review.')
    if monitors:monitor=monitors[0]
    elif case=='brand':
        monitor=desk.monitor(owner,{'name':'Patagonia','campaign':'','notes':'The outdoor clothing company, not the region.',
            'messages':['Repair and reuse clothing'],'sources':['news','web','instagram','x','linkedin'],'freshness':'pm'})
        monitor['validation_case']='general-v2-brand';st.update(owner,monitor['id'],monitor)
    else:raise DeskError('The original campaign monitor is no longer available.')
    before=finding_selection(st,owner,{'monitor':monitor['id'],'filter':'all','snapshot':time.time()})
    # Provider preference is not a criteria revision. Prior runs retain their actual provider.
    monitor['research_path']='Codex native web';st.update(owner,monitor['id'],monitor)
    report={'case':case,'operation':'Check pending' if continue_only else 'Refresh','monitor_id':monitor['id'],'before_counts':before['counts'],
        'before_rows':before['rows'],'usage_before':st.budgets()}
    path=ROOT/'data'/f'research-comparison-general-v2-{case}-{attempt}.json'
    desk.progress=lambda actor,data:print(json.dumps({'progress':data.get('stage')}),flush=True) if data.get('stage') else None
    start=time.monotonic()
    try:
        if continue_only:desk.continue_research(owner,monitor['id'],threading.Event())
        else:desk.research(owner,monitor['id'],threading.Event())
    except Exception as exc:
        report['error']=str(exc) if isinstance(exc,DeskError) else type(exc).__name__
    finally:
        after=finding_selection(st,owner,{'monitor':monitor['id'],'filter':'all','snapshot':time.time()})
        report.update(after_counts=after['counts'],after_rows=after['rows'],run=after['run'],
            usage_after=st.budgets(),elapsed=round(time.monotonic()-start,1))
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:report.get(k) for k in ('case','before_counts','after_counts','error','elapsed','usage_after')}),flush=True)
        desk.pool.shutdown();st.db.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('case',choices=['campaign','brand']);parser.add_argument('--attempt',default='1');parser.add_argument('--continue-only',action='store_true')
    args=parser.parse_args();main(args.case,args.attempt,args.continue_only)
