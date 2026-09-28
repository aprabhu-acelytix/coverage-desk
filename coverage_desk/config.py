from dataclasses import dataclass, field
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent

@dataclass
class Settings:
    mode: str = 'demo'
    allow_live: bool = False
    owner: str = 'OWNER'
    workspace: str = 'TEST'
    channel: str = ''
    bot_token: str = field(default='', repr=False)
    app_token: str = field(default='', repr=False)
    brave_key: str = field(default='', repr=False)
    storage_allowed: bool = False
    youtube_key: str = field(default='', repr=False)
    database: str = ':memory:'
    runtime_home: str = '~/.coverage-desk-codex'
    codex_bin: str = ''
    model: str = ''
    timeout: int = 90
    pages: int = 2
    results: int = 30
    calls: int = 12
    retention_days: int = 7
    schedules: bool = False
    ai_items: int = 15
    input_item: int = 8000
    input_job: int = 24000
    output_job: int = 16000
    queue_size: int = 3

    @classmethod
    def load(cls):
        from dotenv import load_dotenv
        load_dotenv(ROOT / '.env', override=False)
        e = os.environ
        return cls(mode=e.get('APP_MODE', 'demo'), allow_live=e.get('ALLOW_LIVE_CALLS') == 'true',
            owner=e.get('SLACK_OWNER_USER_ID', ''), workspace=e.get('SLACK_WORKSPACE_ID', ''),
            channel=e.get('SLACK_DEMO_CHANNEL_ID', ''), bot_token=e.get('SLACK_BOT_TOKEN', ''),
            app_token=e.get('SLACK_APP_TOKEN', ''), brave_key=e.get('BRAVE_API_KEY', ''),
            storage_allowed=e.get('BRAVE_STORAGE_ALLOWED') == 'true', youtube_key=e.get('YOUTUBE_API_KEY', ''),
            database=str(ROOT / e.get('DATABASE_PATH', 'data/coverage-desk.sqlite3')),
            runtime_home=e.get('COVERAGE_CODEX_HOME', '~/.coverage-desk-codex'),
            codex_bin=e.get('CODEX_BIN', ''), model=e.get('CODEX_MODEL', ''),
            timeout=min(180, max(15, int(e.get('CODEX_JOB_TIMEOUT_SECONDS', '90')))),
            pages=min(3, max(1, int(e.get('MAX_PAGES_PER_SOURCE', '2')))),
            results=min(60, max(1, int(e.get('MAX_RESULTS_PER_SOURCE', '30')))),
            calls=min(12, max(1, int(e.get('MAX_SOURCE_CALLS_PER_RUN', '12')))),
            retention_days=min(7, max(1, int(e.get('RECORD_RETENTION_DAYS', '7')))),
            schedules=e.get('ENABLE_SCHEDULED_DIGESTS')=='true',
            ai_items=min(15,max(1,int(e.get('MAX_AI_ITEMS_PER_RUN','15')))),
            input_item=min(8000,max(200,int(e.get('MAX_AI_INPUT_CHARS_PER_ITEM','8000')))),
            input_job=min(24000,max(1000,int(e.get('MAX_AI_INPUT_CHARS_PER_JOB','24000')))),
            output_job=min(16000,max(1000,int(e.get('MAX_AI_OUTPUT_CHARS_PER_JOB','16000')))),
            queue_size=min(3,max(0,int(e.get('CODEX_MAX_QUEUED_JOBS','3')))))

class DeskError(Exception):
    """Safe, user-facing errors only. Never wrap raw provider errors."""

def require_live(s):
    if s.mode != 'live' or not s.allow_live:
        raise DeskError('Live calls are disabled.')
