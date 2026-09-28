"""Explicit bounded live redesign validation; never imported by offline tests."""
import argparse,json,time,threading
from pathlib import Path
from dataclasses import replace
from coverage_desk.config import Settings,ROOT,DeskError
from coverage_desk.store import Store,Actor
from coverage_desk.slack_app import bind
from coverage_desk.runtime import CodexAnalyzer
from coverage_desk.service import Desk
from coverage_desk.sources import Brave
from coverage_desk.scope import snapshot
from coverage_desk.discovery import finding_selection


def main(case):
 s=Settings.load();st=Store(s);client,_=bind(s);st.s.workspace=s.workspace;o=Actor(s.workspace,s.owner)
 st.migrate_research();d=Desk(s,st,CodexAnalyzer(s,st));path=ROOT/'data'/('research-comparison-'+case+'.json')
 originals=st.list(o,'monitor')
 name='Patagonia' if case=='brand' else 'Stephen Curry'
 base=next(m for m in originals if m['name']==name and not m.get('validation_case'))
 values={**base,'campaign':'' if case=='person' else base['campaign'],
     'research_path':'AI-planned Brave' if case=='brand' else 'Codex native web'}
 claim='research-redesign:comparison:'+case+':v1'
 if not st.claim(claim):raise DeskError('This validation case was already attempted; inspect its persisted results. No automatic retry.')
 m=d.monitor(o,values);m['validation_case']=case;st.update(o,m['id'],m)
 result={'case':case,'monitor_id':m['id'],'scope':snapshot(m),'before':{},'after':{}}
 def save():path.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
 try:
  start=time.monotonic();before,status=Brave(replace(s,calls=1,pages=1,results=10),st).retrieve(m,threading.Event())
  result['before']={'path':'Reviewed baseline Brave queries; one request budget','rows':before,'statuses':status,'elapsed':round(time.monotonic()-start,2)};save()
  start=time.monotonic();d.research(o,m['id'],threading.Event())
  result['after']={'path':m['research_path'],'rows':finding_selection(st,o,{'monitor':m['id'],'filter':'all','snapshot':time.time()})['rows'],
    'run':next(r for r in st.list(o,'run') if r['monitor_id']==m['id']),'elapsed':round(time.monotonic()-start,2)};save()
  st.preferences(o,{'tab':'explore','monitor':m['id'],'filter':'relevant','source_filter':'all','snapshot':time.time(),'page':0})
  print(json.dumps({'case':case,'before_count':len(before),'after_count':len(result['after']['rows']),'run':{k:result['after']['run'].get(k) for k in ('outcome','assessed_count','pending_count','error')},'budgets':st.budgets(),'elapsed':result['after']['elapsed']}))
 except Exception:
  save();raise
 finally:d.pool.shutdown()

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('case',choices=['person','campaign','brand']);main(parser.parse_args().case)
