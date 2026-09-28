import argparse
import json
import subprocess
import sys
from pathlib import Path
from .config import Settings, ROOT, DeskError
from .store import Store
from .runtime import CodexAnalyzer, child_env

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['start','runtime-status','runtime-login','status','validate-live'])
    args=parser.parse_args()
    s=Settings.load()
    if args.command=='runtime-login':
        home=Path(s.runtime_home).expanduser().resolve()
        if home==Path.home()/'.codex' or home.is_relative_to(ROOT):
            raise DeskError('Choose a dedicated runtime home outside the project.')
        return subprocess.call([sys.executable,'-I',str(ROOT/'coverage_desk/runtime_worker.py'),'login',str(home),s.codex_bin,s.model],env=child_env(home))
    store=Store(s)
    if args.command=='runtime-status':
        print(json.dumps(CodexAnalyzer(s,store).status(),indent=2))
    elif args.command=='status':
        print(json.dumps({'mode':s.mode,'live_enabled':s.allow_live,'storage_permission':'owner-supplied' if s.storage_allowed else 'not confirmed',
            'slack_configured':bool(s.bot_token and s.app_token and s.owner),'brave_configured':bool(s.brave_key),
            'youtube_configured':bool(s.youtube_key),'budgets':store.budgets()},indent=2))
    elif args.command=='start':
        from .slack_app import run
        run(s,store)
    elif args.command=='validate-live':
        from .validation import run
        run(s,store)

if __name__=='__main__':
    try:
        sys.exit(main() or 0)
    except DeskError as e:
        print(str(e))
        sys.exit(1)
