from datetime import datetime,timezone
from unittest.mock import Mock
import threading
import time
import pytest
from coverage_desk.scheduling import Scheduler,next_due
from coverage_desk.config import Settings,DeskError
from coverage_desk.store import Store,Actor
from coverage_desk.service import Desk

def test_schedule_disabled_and_owner_only():
    s=Settings();st=Store(s);d=Desk(s,st);o=Actor('TEST','OWNER')
    m=d.monitor(o,{'name':'Acme'})
    sc=Scheduler(d,o)
    with pytest.raises(DeskError):sc.configure(o,m['id'],'daily','UTC',9,True)
    with pytest.raises(DeskError):sc.configure(Actor('TEST','TEAM'),m['id'],'daily','UTC',9,False)
    assert not st.list(o,'schedule')
    sc.tick();assert st.budgets()['ai']['used']==0
    d.pool.shutdown()

def test_schedule_prepares_preview_without_ai_or_posting():
    s=Settings(schedules=True);st=Store(s);analyzer=Mock();d=Desk(s,st,analyzer);o=Actor('TEST','OWNER')
    m=d.monitor(o,{'name':'Acme'});sc=Scheduler(d,o)
    schedule=sc.configure(o,m['id'],'daily','UTC',9,True)
    schedule['next_due']=time.time()-1;st.update(o,schedule['id'],schedule)
    d.submit=lambda actor,label,callback,**kwargs:callback(threading.Event())
    sc.tick();sc.tick()
    assert len(st.list(o,'briefing'))==1
    assert st.list(o,'briefing')[0]['visibility']=='private'
    analyzer.analyze.assert_not_called();analyzer.briefing.assert_not_called()
    assert st.budgets()['ai']['used']==0
    d.pool.shutdown()

def test_restart_skips_missed_schedule():
    s=Settings(schedules=True);st=Store(s);d=Desk(s,st);o=Actor('TEST','OWNER')
    m=d.monitor(o,{'name':'Acme'});sc=Scheduler(d,o)
    schedule=sc.configure(o,m['id'],'weekly','America/New_York',9,True)
    schedule['next_due']=1;st.update(o,schedule['id'],schedule)
    restarted=Scheduler(d,o)
    assert st.get(o,schedule['id'])['next_due']>time.time()
    restarted.tick();assert not st.list(o,'briefing')
    d.pool.shutdown()

def test_timezone_cadence_has_future_due():
    now=datetime(2026,11,1,12,tzinfo=timezone.utc).timestamp()
    assert next_due(now,9,'America/New_York','daily')>now
    with pytest.raises(DeskError):next_due(now,9,'Invalid/Zone','daily')
