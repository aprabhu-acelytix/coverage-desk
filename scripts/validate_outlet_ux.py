"""Explicit owner Home check against retained evidence; no AI or source retrieval."""
import json,time
from slack_sdk.models.views import View
from coverage_desk.config import Settings,DeskError
from coverage_desk.slack_app import bind
from coverage_desk.store import Store,Actor
from coverage_desk.service import Desk
from coverage_desk.overview import coverage_overview
from coverage_desk.overview_ui import correction_modal,outlet_priority_modal
from coverage_desk import ui


def main():
    s=Settings.load();client,_=bind(s);st=Store(s);owner=Actor(s.workspace,s.owner);desk=Desk(s,st)
    prefs=st.preferences(owner);before=st.budgets();report={'monitors_checked':0,'ranked_findings':0,'reviewed_profile_findings':0}
    try:
        if any(j.get('state') in ('Working','Queued') for j in st.list(owner,'job')):raise DeskError('Wait for the active owner job.')
        for monitor in st.list(owner,'monitor'):
            data=coverage_overview(st,owner,monitor,at=time.time())
            rows=data['rows'];ids={r['article_id'] for r in rows}
            assert len(ids)==len(rows)
            assert sum(o['count'] for o in data['outlets'])==data['article_count']==len(data['articles'])
            assert all(rows[i]['outlet_context']['rank']>=rows[i+1]['outlet_context']['rank'] for i in range(len(rows)-1))
            report['monitors_checked']+=1;report['ranked_findings']+=len(rows)
            report['reviewed_profile_findings']+=sum(r['outlet_context']['reviewed'] for r in rows)
            if rows:
                row=desk.finding_detail(owner,rows[0]['id'])
                for view in (ui.detail(row,tab='source'),correction_modal(row),outlet_priority_modal(row)):
                    View(**view).validate_json()
        accepted=[]
        for state in ('confirmed','attention','all'):
            st.preferences(owner,{'tab':'explore','explore_view':'articles','coverage_state':state,'snapshot':time.time(),'page':0})
            client.views_publish(user_id=owner.user,view=ui.home(desk,owner));accepted.append(state)
        report.update(home_filters_accepted=accepted,usage_unchanged=st.budgets()==before,modal_checks='Local schema only',visual_checks='Owner walkthrough required')
        print(json.dumps(report))
    finally:
        st.preferences(owner,prefs)
        client.views_publish(user_id=owner.user,view=ui.home(desk,owner))
        desk.pool.shutdown();st.db.close()


if __name__=='__main__':main()
