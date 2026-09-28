"""Read-only source reconciliation and private preview preparation; no posting."""
import argparse,json,time
from coverage_desk.config import Settings,ROOT,DeskError
from coverage_desk.store import Store,Actor
from coverage_desk.slack_app import bind
from coverage_desk.service import Desk
from coverage_desk.overview import coverage_overview,chart_block
from coverage_desk import ui

def main(name):
    s=Settings.load();client,_=bind(s);st=Store(s);o=Actor(s.workspace,s.owner);d=Desk(s,st)
    def never_post(**kwargs):raise AssertionError('Validation cannot publish')
    client.chat_postMessage=never_post
    try:
        m=next(m for m in st.list(o,'monitor') if m['name']==name)
        at=time.time();data=coverage_overview(st,o,m,at=at)
        ids={r['article_id'] for r in data['articles']}
        assert len(ids)==data['article_count']==sum(x['count'] for x in data['outlets'])
        assert sum(x['value'] for x in chart_block(data)['chart']['series'][0]['data'])==len(ids)
        # Local private preparation is authorized implementation validation.
        # No claim that the owner clicked a disclosure or publishing control.
        draft=d.overview_snapshot(o,m['id'],{'snapshot':at},confirmed=True)
        draft['validation_note']='Prepared privately during implementation validation; no owner UI confirmation or channel publication performed.'
        st.update(o,draft['id'],draft)
        preview=d.preview(o,draft['id'])
        assert {r['article_id'] for r in draft['sources']}==ids
        assert draft['overview']['outlets']==[{k:x[k] for k in ('id','key','name','count')} for x in data['outlets']]
        views=[]
        for tab in ('explore','board','briefings'):
            st.preferences(o,{'tab':tab,'monitor':m['id'],'snapshot':at,'explore_view':'overview','outlet':'','content_type':'reporting','page':0})
            client.views_publish(user_id=o.user,view=ui.home(d,o));views.append(tab)
        channel=client.conversations_info(channel=s.channel)['channel']
        report={'at':at,'client':name,'article_count':len(ids),'outlets':data['outlet_count'],'source_ids':[r['id'] for r in draft['sources']],
            'draft_id':draft['id'],'preview_id':preview['id'],'preview_expires':preview['expires'],'partial':data['partial'],
            'views_payload_accepted':views,'channel_ready':bool(channel.get('is_member') and not any(channel.get(k) for k in ('is_private','is_shared','is_ext_shared','is_archived'))),
            'published':False,'usage':st.budgets()}
        (ROOT/'data'/'research-comparison-overview-snapshot.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))
    finally:
        st.preferences(o,{'tab':'explore','explore_view':'overview','page':0,'outlet_page':0,'notice':''})
        client.views_publish(user_id=o.user,view=ui.home(d,o));d.pool.shutdown();st.db.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--client',required=True);args=parser.parse_args();main(args.client)
