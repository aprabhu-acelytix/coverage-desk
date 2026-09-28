"""Parent-side runtime adapter. The SDK runs only inside a clean child process."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from .config import ROOT, DeskError, require_live

ENV_ALLOW = {'SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','USERPROFILE','HOMEDRIVE','HOMEPATH','LOCALAPPDATA','APPDATA','HOME','LANG','LC_ALL'}

def child_env(home):
    env = {k:v for k,v in os.environ.items() if k.upper() in ENV_ALLOW}
    env['CODEX_HOME'] = str(home)
    env['PYTHONIOENCODING'] = 'utf-8'
    # No inherited PATH, API keys, OAuth values, developer config, or tool endpoints.
    if os.name == 'nt':
        env['PATH'] = str(Path(env.get('SYSTEMROOT','C:/Windows')) / 'System32')
    else:
        env['PATH'] = '/usr/bin:/bin'
    return env

class CodexAnalyzer:
    def __init__(self,s,store):
        self.s,self.store = s,store

    def call(self,operation,payload=None,cancel=None):
        if cancel and cancel.is_set():
            raise DeskError('Cancelled before runtime start.')
        home = Path(self.s.runtime_home).expanduser().resolve()
        if home == Path.home()/'.codex' or home.is_relative_to(ROOT):
            raise DeskError('Runtime home must be dedicated and outside the project and development Codex home.')
        args = [sys.executable, '-I', str(ROOT/'coverage_desk'/'runtime_worker.py'),operation,str(home),self.s.codex_bin,self.s.model]
        proc = subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            env=child_env(home),text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),start_new_session=os.name!='nt')
        try:
            proc.stdin.write(json.dumps(payload or {}))
            proc.stdin.close()
            proc.stdin = None
            deadline=time.monotonic()+self.s.timeout
            while True:
                if cancel and cancel.is_set():
                    proc.terminate()
                    raise DeskError('Cancelled; remote completion may be uncertain. No automatic retry.')
                if time.monotonic()>deadline:
                    proc.terminate()
                    raise DeskError('AI timeout; remote completion may be uncertain. No automatic retry.')
                try:
                    output,_=proc.communicate(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if len(output)>self.s.output_job+2000:
                raise DeskError('AI output exceeded the application limit.')
            try:
                result=json.loads(output)
            except (ValueError,TypeError):
                raise DeskError('Runtime unavailable. Run the local runtime status helper.') from None
            if 'error' in result:
                raise DeskError(result['error'])
            return result
        finally:
            if os.name!='nt':
                import signal
                try:os.killpg(proc.pid,signal.SIGTERM)
                except ProcessLookupError:pass
            if proc.poll() is None:
                proc.kill()
            proc.wait()

    def status(self):
        return self.call('status')

    def analyze(self,sources,monitor,cancel):
        require_live(self.s)
        if cancel.is_set():raise DeskError('Cancelled before analysis.')
        from .models import Analysis
        selected = [{'id':r['id'],'title':r['title'],'text':r['text'],'access':r['access'],'provider':r['provider']} for r in sources]
        if any(len(r['text'])>self.s.input_item for r in selected):
            raise DeskError('One source exceeds the configured AI input limit. Its full retained text remains inspectable.')
        criteria={k:monitor[k] for k in ('name','aliases','domains','notes','campaign','messages')}
        payload={'sources':selected,'criteria':criteria,'schema':Analysis.model_json_schema()}
        if len(json.dumps(payload))>self.s.input_job:
            raise DeskError(f'Select fewer findings; the analysis input limit is {self.s.input_job:,} characters.')
        status=self.status()
        if status['state']!='Ready':
            raise DeskError(status['state']+'. Run: .venv/Scripts/python -m coverage_desk runtime-login')
        self.store.consume('ai')
        return self.call('analyze',payload,cancel)

    def briefing(self,sources,cancel):
        require_live(self.s)
        if cancel.is_set():raise DeskError('Cancelled before briefing analysis.')
        from .models import BriefingAnalysis,validate_briefing
        payload={'operation':'briefing','sources':[{'id':r['id'],'title':r['title'],'text':r['text'],'access':r['access']} for r in sources],
            'schema':BriefingAnalysis.model_json_schema()}
        if len(json.dumps(payload))>self.s.input_job or any(len(r['text'])>self.s.input_item for r in sources):
            raise DeskError('Select fewer findings for this briefing; input limit reached.')
        if self.status()['state']!='Ready':
            raise DeskError('Sign-in needed. Run the local runtime-login helper.')
        self.store.consume('ai')
        return validate_briefing(self.call('analyze',payload,cancel),sources)
