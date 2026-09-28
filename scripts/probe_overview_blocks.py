"""Explicit owner Home capability check; synthetic payloads, no channel posts."""
import json,time
from coverage_desk.config import Settings
from coverage_desk.store import Store,Actor
from coverage_desk.slack_app import bind
from coverage_desk.service import Desk
from coverage_desk import ui

def main():
    s=Settings.load();client,_=bind(s);store=Store(s);actor=Actor(s.workspace,s.owner);desk=Desk(s,store)
    rows=[[{'type':'raw_text','text':'Outlet'},{'type':'raw_text','text':'Articles'}],
          [{'type':'raw_text','text':'Synthetic outlet'},{'type':'raw_number','value':2,'text':'2'}]]
    candidates=[{'type':'data_visualization','title':'Articles by outlet','chart':{'type':'bar',
        'series':[{'name':'Articles','data':[{'label':'Synthetic outlet','value':2}]}],
        'axis_config':{'categories':['Synthetic outlet'],'x_label':'Outlet','y_label':'Unique articles'}}},
        {'type':'data_table','caption':'Synthetic capability check','page_size':8,'rows':rows},
        {'type':'table','rows':rows}]
    results={}
    try:
        for block in candidates:
            try:
                client.views_publish(user_id=s.owner,view={'type':'home','blocks':[ui.para('Temporary capability check: synthetic data.'),block]})
                result={'supported':True}
            except Exception as exc:
                response=getattr(exc,'response',{})
                result={'supported':False,'error':response.get('error','request_failed'),
                    'messages':response.get('response_metadata',{}).get('messages',[])}
            results[block['type']]=result
        for old in store.list(actor,'slack_capabilities'):store.db.execute('DELETE FROM objects WHERE id=?',(old['id'],))
        store.create(actor,'slack_capabilities',{'home':results,'checked':time.time()},expires=time.time()+365*86400)
        print(json.dumps(results))
    finally:
        client.views_publish(user_id=s.owner,view=ui.home(desk,actor))
        desk.pool.shutdown();store.db.close()

if __name__=='__main__':main()
