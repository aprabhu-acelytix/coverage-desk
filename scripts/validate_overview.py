"""Explicit local owner validation; retained public evidence, never channel posts."""
import argparse,json,threading,time
from coverage_desk.config import Settings,ROOT,DeskError
from coverage_desk.store import Store,Actor
from coverage_desk.slack_app import bind
from coverage_desk.runtime import CodexAnalyzer
from coverage_desk.service import Desk
from coverage_desk.overview import coverage_overview
from coverage_desk import ui

def main(args):
    s=Settings.load();client,_=bind(s);st=Store(s);actor=Actor(s.workspace,s.owner)
    if any(j.get('state') in ('Working','Queued') for j in st.list(actor,'job')):raise DeskError('Wait for the active owner job before validation.')
    backup=st.migrate_overview();desk=Desk(s,st,CodexAnalyzer(s,st))
    monitor=next((m for m in st.list(actor,'monitor') if m['name']==args.client),None)
    if not monitor:raise DeskError('Select an existing public-client monitor by exact name.')
    report={'client':monitor['name'],'operation':args.operation,'usage_before':st.budgets(),
        'before':coverage_overview(st,actor,monitor),'migration_backup':bool(backup)}
    path=ROOT/'data'/('research-comparison-overview-'+args.attempt+'.json')
    if path.exists() and args.operation!='report':raise DeskError('This attempt report already exists; use a new explicit attempt name.')
    desk.progress=lambda actor,data:print(json.dumps({'progress':data.get('stage')}),flush=True) if data.get('stage') else None
    started=time.monotonic()
    try:
        if args.operation!='report':
            if not st.claim('overview-validation:'+args.attempt):raise DeskError('This validation attempt already ran; inspect its report instead of retrying silently.')
            if args.operation=='refresh':desk.research(actor,monitor['id'],threading.Event())
            else:desk.complete_research(actor,monitor['id'],threading.Event())
    except Exception as exc:report['error']=str(exc) if isinstance(exc,DeskError) else type(exc).__name__
    finally:
        report.update(after=coverage_overview(st,actor,monitor),usage_after=st.budgets(),elapsed=round(time.monotonic()-started,1))
        st.preferences(actor,{'monitor':monitor['id'],'tab':'explore','explore_view':'overview','content_type':'all',
            'coverage_state':'confirmed','outlet':'','outlet_page':0,'page':0,'snapshot':time.time(),'notice':''})
        try:client.views_publish(user_id=actor.user,view=ui.home(desk,actor));report['home_payload_accepted']=True
        except Exception as exc:report['home_payload_error']=getattr(exc,'response',{}).get('error','request_failed')
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'operation':args.operation,'before_articles':report['before']['article_count'],
            'after_articles':report['after']['article_count'],'outlets':report['after']['outlet_count'],
            'states':report['after']['states'],'error':report.get('error'),'home_payload_accepted':report.get('home_payload_accepted'),
            'elapsed':report['elapsed'],'usage_after':report['usage_after']}),flush=True)
        desk.pool.shutdown();st.db.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--client',required=True)
    parser.add_argument('--operation',choices=['report','assess','refresh'],default='report')
    parser.add_argument('--attempt',required=True,type=lambda x:x if x.replace('-','').isalnum() else parser.error('Use an alphanumeric attempt name.'))
    main(parser.parse_args())
