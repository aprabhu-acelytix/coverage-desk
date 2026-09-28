import json
import os
import threading
from pathlib import Path
from unittest.mock import Mock
import pytest
from coverage_desk.config import Settings,DeskError,ROOT
from coverage_desk.store import Store
from coverage_desk.runtime import CodexAnalyzer
from coverage_desk.runtime_worker import prepare,DISABLED
from coverage_desk.models import validate_analysis,validate_briefing

@pytest.mark.parametrize('exit_code',[0,7])
def test_login_uses_supported_command_and_preserves_exit_code(tmp_path,monkeypatch,exit_code):
    from coverage_desk import runtime_worker as worker
    monkeypatch.setattr(worker,'job_guard',lambda:None)
    monkeypatch.setattr(worker,'prepare',lambda home:(tmp_path,tmp_path/'catalog.json'))
    monkeypatch.setattr(worker.sys,'argv',['runtime_worker.py','login',str(tmp_path),'codex.exe',''])
    monkeypatch.setattr(worker.subprocess,'run',Mock(return_value=Mock(stdout='codex-cli 0.157.1\n')))
    login=Mock(return_value=exit_code)
    monkeypatch.setattr(worker.subprocess,'call',login)
    assert worker.main()==exit_code
    login.assert_called_once_with(['codex.exe','login'],cwd=tmp_path)

def test_generated_controls_match_pinned_schema(tmp_path,monkeypatch):
    monkeypatch.setattr('coverage_desk.runtime_worker.secure_home',lambda home:home.mkdir(parents=True,exist_ok=True))
    work,catalog=prepare(tmp_path/'dedicated')
    import tomllib
    cfg=tomllib.loads((work.parent/'config.toml').read_text())
    assert all(cfg['features'][name] is False for name in DISABLED)
    assert cfg['permissions']['analysis']['filesystem'][':root']=='deny'
    assert cfg['web_search']=='disabled'
    assert cfg['forced_login_method']=='chatgpt'
    assert cfg['features']['skip_host_skill_discovery']
    for model in json.loads(catalog.read_text())['models']:
        assert model['apply_patch_tool_type'] is None
        assert model['shell_type']=='disabled'
        assert model['experimental_supported_tools']==[]

@pytest.mark.parametrize('state',['Sign-in needed','Unsupported authentication','Unavailable','Usage limit'])
def test_not_ready_never_starts_ai(state):
    s=Settings(mode='live',allow_live=True);st=Store(s);a=CodexAnalyzer(s,st)
    a.status=Mock(return_value={'state':state})
    a.call=Mock()
    with pytest.raises(DeskError):a.analyze([],dict(name='Acme',aliases=[],domains='',notes='',campaign='',messages=[]),threading.Event())
    a.call.assert_not_called()
    assert st.budgets()['ai']['used']==0

def test_failed_job_consumed_once_no_retry():
    st=Store(Settings());a=CodexAnalyzer(Settings(mode='live',allow_live=True),st)
    a.status=Mock(return_value={'state':'Ready'})
    a.call=Mock(side_effect=DeskError('Usage limit'))
    with pytest.raises(DeskError):a.analyze([],dict(name='Acme',aliases=[],domains='',notes='',campaign='',messages=[]),threading.Event())
    assert a.call.call_count==1 and st.budgets()['ai']['used']==1

def test_only_allowlisted_evidence_enters_runtime():
    st=Store(Settings());a=CodexAnalyzer(Settings(mode='live',allow_live=True),st)
    a.status=Mock(return_value={'state':'Ready'});a.call=Mock(return_value={})
    source={'id':'one','title':'A','text':'public','access':'excerpt only','provider':'Manual','perspectives':'PRIVATE_CANARY','comment':'PRIVATE_CANARY','workspace':'PRIVATE_CANARY'}
    a.analyze([source],dict(name='Acme',aliases=[],domains='',notes='',campaign='',messages=[]),threading.Event())
    sent=json.dumps(a.call.call_args.args[1])
    assert 'PRIVATE_CANARY' not in sent

def test_briefing_fidelity_rejects_invented_quote():
    value={'what_changed':[{'text':'Repair','source_id':'1','quote':'made up'}],'message_evidence':[],'worth_discussing':'What changed?'}
    with pytest.raises(DeskError):validate_briefing(value,[{'id':'1','text':'Original source.'}])

def test_nine_gold_cases_are_validation_fixtures():
    cases=json.loads((Path(__file__).parent/'eval_cases.json').read_text())
    assert len(cases)==9
    for case in cases:
        label=case['labels'][0]
        raw={'findings':[{'source_id':case['id'],'relevance':case['relevance'],'campaign_relevance':'not_applicable',
            'explanation':'Labeled fixture, not model output.','messages':[{'message':'Acme offers clothing repairs.','label':label,
            'explanation':'Labeled fixture.','evidence':[{'source_id':case['id'],'quote':case['text'][:100]}] if label in ('supported','contradicted') else []}]}]}
        assert validate_analysis(raw,[case],['Acme offers clothing repairs.'])

def test_demo_adapter_cannot_start_live_job():
    st=Store(Settings());a=CodexAnalyzer(Settings(),st);a.status=Mock()
    with pytest.raises(DeskError):a.analyze([],{},threading.Event())
    a.status.assert_not_called();assert st.budgets()['ai']['used']==0

def test_cancel_before_runtime_start(monkeypatch):
    spawn=Mock();monkeypatch.setattr('coverage_desk.runtime.subprocess.Popen',spawn)
    a=CodexAnalyzer(Settings(),Store(Settings()));cancel=threading.Event();cancel.set()
    with pytest.raises(DeskError,match='Cancelled'):a.call('analyze',{},cancel)
    spawn.assert_not_called()

def test_timeout_terminates_runtime_host(monkeypatch):
    import io
    proc=Mock();proc.stdin=io.StringIO();proc.poll.return_value=None
    monkeypatch.setattr('coverage_desk.runtime.subprocess.Popen',Mock(return_value=proc))
    s=Settings(runtime_home='C:/coverage-unit-test-isolated',timeout=-1)
    a=CodexAnalyzer(s,Store(s))
    with pytest.raises(DeskError,match='timeout'):a.call('analyze',{})
    proc.terminate.assert_called_once();proc.kill.assert_called_once()

def test_inference_lock_excludes_other_process_hosts(tmp_path):
    from coverage_desk.runtime_worker import acquire_inference_lock
    first=acquire_inference_lock(tmp_path)
    try:
        with pytest.raises(RuntimeError,match='Another AI job'):acquire_inference_lock(tmp_path)
    finally:first.close()
    second=acquire_inference_lock(tmp_path);second.close()


@pytest.mark.parametrize('kind',['commandExecution','fileChange','mcpToolCall','dynamicToolCall','imageView','collabAgentToolCall'])
def test_research_still_rejects_unrelated_tools(kind):
    from coverage_desk.runtime_worker import validate_item
    with pytest.raises(RuntimeError):validate_item({'type':kind},research=True)


def test_only_research_accepts_observed_web_actions():
    from coverage_desk.runtime_worker import validate_item
    item={'type':'webSearch','id':'one','action':{'type':'openPage','url':'https://example.org/story'}}
    validate_item(item,research=True)
    with pytest.raises(RuntimeError):validate_item(item,research=False)
    for url in ('file:///C:/secrets','http://127.0.0.1/x','http://169.254.169.254/x','http://localhost/x'):
        with pytest.raises(RuntimeError):validate_item({**item,'action':{'type':'openPage','url':url}},research=True)
