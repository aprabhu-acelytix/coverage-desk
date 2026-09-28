"""Opt-in source refresh → private preview. Never AI and never channel posting."""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
import time
from .config import DeskError

def next_due(now,hour,zone,cadence):
    try:tz=ZoneInfo(zone)
    except ZoneInfoNotFoundError:raise DeskError('Timezone unavailable. Install the pinned tzdata dependency.') from None
    current=datetime.fromtimestamp(now,tz)
    candidate=current.replace(hour=hour,minute=0,second=0,microsecond=0)
    if candidate<=current:candidate+=timedelta(days=1 if cadence=='daily' else 7)
    return candidate.timestamp()

class Scheduler:
    def __init__(self,desk,actor):
        self.desk,self.actor=desk,actor
        # Skip missed runs. Never replay a backlog on startup.
        for schedule in desk.store.list(actor,'schedule'):
            if schedule['next_due']<time.time():
                schedule['next_due']=next_due(time.time(),schedule['hour'],schedule['timezone'],schedule['cadence'])
                schedule['last_status']='Missed while backend was offline; advanced to next future run.'
                desk.store.update(actor,schedule['id'],schedule)

    def configure(self,actor,monitor_id,cadence,zone,hour,enabled):
        st=self.desk.store;st.authorize(actor,owner=True)
        st.get(actor,monitor_id,'monitor')
        if cadence not in ('daily','weekly') or zone not in ('UTC','America/New_York','Europe/London','America/Los_Angeles') or not 0<=hour<=23:
            raise DeskError('Choose a supported cadence, timezone and hour from 0–23.')
        if enabled and not self.desk.s.schedules:
            raise DeskError('Scheduling is disabled locally. Set ENABLE_SCHEDULED_DIGESTS=true and restart before explicitly enabling a schedule.')
        data={'monitor_id':monitor_id,'cadence':cadence,'timezone':zone,'hour':hour,'enabled':enabled,
            'next_due':next_due(time.time(),hour,zone,cadence),'destination':self.desk.s.channel,
            'last_status':'Configured. Previews only; no automatic posts or AI.'}
        old=next((x for x in st.list(actor,'schedule') if x['monitor_id']==monitor_id),None)
        return st.update(actor,old['id'],data,owner_only=True) if old else st.create(actor,'schedule',data,expires=time.time()+10*365*86400)

    def tick(self):
        if not self.desk.s.schedules:return
        st=self.desk.store
        for schedule in st.list(self.actor,'schedule'):
            if not schedule['enabled'] or schedule['next_due']>time.time():continue
            if self.desk.jobs.get(self.actor.user,{}).get('state') in ('Queued','Working'):continue
            slot=schedule['next_due']
            schedule['next_due']=next_due(time.time(),schedule['hour'],schedule['timezone'],schedule['cadence'])
            schedule['last_status']='Queued source refresh; no AI or automatic post.'
            st.update(self.actor,schedule['id'],schedule)
            if not st.claim(f"schedule:{schedule['id']}:{slot}"):continue
            def prepare(cancel,schedule=schedule):
                try:
                    existing={r['canonical'] for r in st.list(self.actor,'finding') if r.get('monitor_id')==schedule['monitor_id']}
                    self.desk.refresh(self.actor,schedule['monitor_id'],cancel)
                    fresh=[r for r in st.list(self.actor,'finding') if r.get('monitor_id')==schedule['monitor_id'] and r['canonical'] not in existing]
                    selected={}
                    for r in fresh:selected.setdefault(r['canonical'],r)
                    if selected and not cancel.is_set():
                        boards=[self.desk.save(self.actor,r['id'],'private') for r in list(selected.values())[:5]]
                        draft=self.desk.draft(self.actor,[b['id'] for b in boards],cancel,use_ai=False)
                        schedule['last_status']=f'{len(selected)} new links; private preview prepared from up to five. Owner confirmation required to publish.'
                        schedule['draft_id']=draft['id']
                    else:schedule['last_status']='No new links or refresh cancelled. Inspect collection status for provider failures.'
                except Exception:
                    schedule['last_status']='Scheduled refresh failed. No retry, AI job or channel post.'
                    raise
                finally:st.update(self.actor,schedule['id'],schedule)
            self.desk.submit(self.actor,'Scheduled source preview',prepare,owner=True)
