import json
import time
from unittest.mock import Mock
from slack_sdk import WebClient
from slack_bolt.request import BoltRequest
from coverage_desk.config import Settings
from coverage_desk.store import Store,Actor
from coverage_desk.slack_app import create_app

def test_real_bolt_action_dispatch_ack_and_modal():
    s=Settings(bot_token='xoxb-fixture',app_token='xapp-fixture')
    st=Store(s);client=WebClient(token=s.bot_token)
    client.auth_test=Mock(return_value={'ok':True,'team_id':'TEST','user_id':'BOT','bot_id':'BOT'})
    client.views_open=Mock(return_value={'ok':True});client.views_publish=Mock(return_value={'ok':True})
    app,d,home=create_app(s,st,client)
    body={'type':'block_actions','team':{'id':'TEST'},'user':{'id':'OWNER'},'trigger_id':'trigger',
        'api_app_id':'APP','container':{'type':'view'},'view':{'type':'home','id':'HOME'},
        'actions':[{'action_id':'new_monitor','type':'button','value':'-','action_ts':'1'}]}
    start=time.monotonic()
    response=app.dispatch(BoltRequest(body=body,mode='socket_mode'))
    assert response.status==200 and time.monotonic()-start<3
    deadline=time.monotonic()+2
    while not client.views_open.called and time.monotonic()<deadline:time.sleep(.01)
    assert client.views_open.call_args.kwargs['view']['callback_id']=='monitor_submit'
    d.pool.shutdown()

def test_real_bolt_teammate_owner_action_denied():
    s=Settings(bot_token='xoxb-fixture',app_token='xapp-fixture');st=Store(s)
    client=WebClient(token=s.bot_token)
    client.auth_test=Mock(return_value={'ok':True,'team_id':'TEST','user_id':'BOT','bot_id':'BOT'})
    client.views_open=Mock();client.views_publish=Mock()
    app,d,home=create_app(s,st,client)
    body={'type':'block_actions','team':{'id':'TEST'},'user':{'id':'TEAM'},'trigger_id':'trigger',
        'api_app_id':'APP','container':{'type':'view'},'view':{'type':'home','id':'HOME'},
        'actions':[{'action_id':'new_monitor','type':'button','value':'-','action_ts':'1'}]}
    assert app.dispatch(BoltRequest(body=body,mode='socket_mode')).status==200
    deadline=time.monotonic()+2
    while not client.views_publish.called and time.monotonic()<deadline:time.sleep(.01)
    client.views_open.assert_not_called()
    assert 'owner-operated' in st.preferences(Actor('TEST','TEAM'))['notice']
    d.pool.shutdown()
