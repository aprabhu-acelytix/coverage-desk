# Coverage Desk

A local Slack application for exploring coverage, inspecting message evidence, sharing selected findings, and preparing reviewed briefings. The interface is native Slack App Home: **Explore · Team board · Briefings**. There is no hosted dashboard or shared inference service.

## Run on this Windows machine

```powershell
cd C:\Users\anike\Apps\coverage-desk-chatgpt-starter
.venv\Scripts\python -m coverage_desk status
.venv\Scripts\python -m coverage_desk runtime-login
.venv\Scripts\python -m coverage_desk runtime-status
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/backend.ps1 start
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/backend.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/backend.ps1 stop
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/backend.ps1 restart
```

Only run `runtime-login` when sign-in is needed. Complete the normal browser sign-in yourself. It uses the same pinned executable and dedicated home as analysis. No OAuth token is copied from your development session. Do not paste credentials into chat.

The process manager checks the recorded PID and the project-specific command line. The backend also holds local port 47831 as a single-instance lock. Closing the machine/session or terminating its host can stop it; Socket Mode is not hosting. Logs are under `logs/`, readiness under `data/backend.json`.

For a visible foreground process, run `.venv\Scripts\python -m coverage_desk start` instead, and stop it with Ctrl+C. Do not run foreground and background instances together.

## Fresh setup

Python 3.13.9 was tested on Windows. The SDK requires Python 3.10+; other OS combinations have not been verified here.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.venv\Scripts\python -m pytest -q
```

Bash equivalent (foreground; not validated on this machine):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
[ -f .env ] || cp .env.example .env
.venv/bin/python -m pytest -q
.venv/bin/python -m coverage_desk runtime-login
.venv/bin/python -m coverage_desk runtime-status
.venv/bin/python -m coverage_desk start
# Ctrl+C stops the foreground host. Start again to restart.
```

The app loads `.env` without printing values. Tests never load it and block network access. Current owner authorization sets `APP_MODE=live`; `ALLOW_LIVE_CALLS=true` is also required. `APP_MODE=demo` uses explicitly labeled synthetic retrieval/analysis and never silently substitutes for live failures. Keep fixture tests separate from real evidence.

The tested direct dependencies are pinned in `requirements.txt`; the full installed set is in `requirements.lock.txt`: Slack Bolt 1.30.0, Slack SDK 3.44.1, HTTPX 0.28.1, Pydantic 2.13.5, python-dotenv 1.2.3, pytest 9.1.1, **openai-codex 0.157.1 and its pinned Codex CLI 0.157.1**.

## Slack installation

Import `slack-app-manifest.yaml` into your development workspace, enable Socket Mode and interactivity, install the bot, and enable the Home tab. The bot needs only `commands`, `chat:write`, and `channels:read`. Create a separate app token with `connections:write`. Configure `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_OWNER_USER_ID`, and the public `SLACK_DEMO_CHANNEL_ID` locally. Invite the bot to that channel. `SLACK_WORKSPACE_ID` optionally pins the installation; otherwise `auth.test` binds it on startup.

Open **Coverage Desk → Home**. `/coverage` refreshes Home and explains where to go. The app does not read channel or DM history. It only posts after the configured owner submits an exact, unexpired preview. Public external-shared channels, private channels, archived channels and channels without the bot are rejected. Failed or uncertain sends are never automatically retried.

The bot is a verified member of `#coverage-desk-demo`. Authentication and all three owner Home views have passed live validation.

## Workflow

1. In **Explore**, choose **New coverage search**. Enter a company, brand, or person; campaign focus and messages are optional. **More options** contains alternate names, identification guidance, language/region and custom dates. Each tab has a short explanation and **How it works**.
2. **Save & collect** saves the private search and starts retrieval. New searches default to News, Web, Instagram, X and LinkedIn for the past week. Existing searches keep their settings. Editing a search saves only; use **Collect coverage** to retrieve again. AI never runs merely because a search was saved.
3. Follow the collection panel: Queued, Searching, Saving, then Ready / Partial results / No matches. It shows actual checked-source and retained-result counts. Pages are saved as they arrive. Cancellation, caps, or later failures do not discard earlier pages. **Collection details** explains each source; no raw JSON is displayed.
4. Use **Filters** to independently select a platform/source and assessment. Filtering costs no requests. **Analyze these N findings** analyzes exactly the matching selected-search findings on the displayed page. All permitted retrieved records remain available. New results never move an existing page; use **Show new findings**. A newly created search displays its first collection automatically.
5. **View finding** opens Overview, Evidence, Source details, and Discussion within one modal. Source details uses readable fields and dates; complete provenance remains stored internally. Save privately or explicitly share with the workspace. Including AI separately discloses its assessment and message wording, never private queries or identification notes.
6. On **Team board**, open a finding to add a perspective or change review status. Authors render as Slack profile mentions. Teammates can collaborate on shared objects but cannot initiate AI. User-written note text is escaped and cannot create mentions.
7. In **Briefings**, select up to five saved findings for a source-linked or AI-assisted draft. Team perspectives stay out of AI inputs and are attached separately. For Slack length limits, the latest eight perspectives are included, with an explicit count when more remain on the board. Any private source keeps the draft private.
8. Edit, then **Preview & publish**. Only the owner can confirm the exact content and destination. Contributor profile mentions may notify those contributors on publication. Changes invalidate previews, which expire after ten minutes. No unattended publishing is enabled.


## Runtime isolation and data flow

`COVERAGE_CODEX_HOME` defaults to `~/.coverage-desk-codex`, outside this repository and the development Codex home. Only its generated config is managed; unrelated Codex configuration is never changed. Runtime status exposes categorized status and model names, never account email, tokens or transcripts. `CODEX_BIN` is an executable path, never a shell command.

The SDK inherits environment variables by design, so it runs in a separate Python process launched with an OS-only allowlist. Slack, Brave, YouTube and unrelated service keys are absent. The SDK launches its App Server from an empty dedicated working directory. Host skill discovery, plugins, MCP, hooks, memories, shell, alternate code execution, browsing, images, connected tools and delegation are disabled using the pinned version's schema. A pinned official model catalog removes built-in apply-patch registration and disables shell support; model selection must still appear in the unmodified authenticated `model/list` response. It changes tool capability metadata, not endpoints or credentials. Effective config and catalog path are checked before inference. Unknown versions/configurations fail closed. Any unexpected SDK approval/tool request terminates the job instead of using the SDK's permissive default approval handler.

The filesystem permission profile denies root access; no tool network access is enabled. Model transport remains online. The boundary primarily removes model-accessible tools; a read-only sandbox or prompt alone is not treated as a secret boundary. The Windows worker uses a kill-on-close job object so timeout, cancellation or host termination kills its runtime descendant. Application analysis has one worker, a bounded queue, no automatic job retry, fresh ephemeral threads, input/output limits and exact source/evidence validation. App-side size/time limits do not guarantee zero remote consumption after cancellation.

Authentication uses Codex-managed ChatGPT sign-in only. API-key, external-token, third-party and signed-out modes are rejected. Credential storage prefers the supported OS store with `auto`; if Codex falls back to a file, it remains inside the dedicated home with restrictive owner permissions. The app never reads the auth file. Ephemeral threads and disabled history reduce local retention but do not promise zero provider retention. Runtime operational artifacts are separate from the application database. Review ChatGPT training/data controls before live use; this prototype uses public or synthetic material only.

## Sources, storage and limits

Brave storage permission was supplied by the owner (`BRAVE_STORAGE_ALLOWED=true`). This is **not independent verification of licensing or plan entitlement**. Disabling that setting blocks new retention, board saves, AI and publication using Brave material. A valid key alone does not establish storage rights. No arbitrary manual URL is fetched.

Every retained finding has its original URL, tracking-stripped duplicate key, source/endpoint, query/page/filter provenance, retrieval time, publication time when supplied, text-access label and content hash. A snippet is not a full article. Manual excerpts are user-supplied, not verified publisher text. These are all *retrieved results*, not all online coverage or a representative sample.

Default source/board/draft/cache retention is seven days, configurable downward. Expired records disappear from reads and are deleted on startup and every 30 seconds while running; WAL checkpointing follows deletion. Briefing snapshots expire no later than their sources. Monitor configuration persists separately. SQLite is not encrypted. Local expiry does not erase already-published Slack copies or provider-held records.

The build-wide validation ledger in SQLite permanently caps **30 source requests and 10 runtime AI jobs**, counting attempts before sending. It survives restarts; do not remove/reset the database to bypass it. No automatic AI retry, paid fallback, purchasing, deployment or automatic channel post is enabled. Per-run source pages/results/calls are also bounded. Documentation and package downloads are not source-provider retrievals.

## Validation and current limitations

Run `.venv\Scripts\python -m pytest -q` for isolated offline tests. `tests/eval_cases.json` contains nine labeled cases: alias, wrong entity, critical coverage, paraphrase, negation, company quote, missing context, duplicate, injection. Passing their schema/fidelity tests is not a model precision/recall claim. See `BUILD_NOTES.md` for actual results and `data/live-validation.json` for the local live check record.

The explicitly authorized validation command is `.venv\Scripts\python -m coverage_desk validate-live`. It resumes using persistent stage claims and budgets, preserves retrieved results, and never posts. It checks Slack, runs one News and one Web request once, then performs bounded AI checks when managed sign-in is ready. Failed/uncertain stages are not automatically retried. Repair before explicitly authorizing a new stage; the total budget still applies.

No browser/Slack UI surface was available to the build agent. Slack accepting a view payload is not a visual inspection. Check Home and modals in native light/dark mode, narrow width, five-row pagination, long headlines, empty/error states, and two actual teammate accounts. Simulated multi-user tests are not a real two-person walkthrough.

Social discovery uses Brave Web domain-targeted queries for Instagram, X (including twitter.com), LinkedIn, Facebook, TikTok, Reddit and YouTube. Platform classification uses URL hostnames, separately from the retrieval provider. These are public indexed pages, not direct integrations or complete social monitoring. No transcripts, media downloads, engagement metrics, or scraping. Sources receive their first general-query page before campaign queries or additional pages, within the unchanged request budget; result limits apply to each selected target. Broader selections use more requests. YouTube Data API and RSS remain unconnected.

The redesign check is `.venv\Scripts\python scripts/validate_redesign.py`: at most two additional Brave requests, no AI and no posts, with a persistent stage claim preventing repeats. Its report is `data/redesign-validation.json`. Its initial Instagram/LinkedIn queries returned mostly off-target pages (0 Instagram and 1 LinkedIn hostname matches). Query construction has been corrected and offline-tested; live verification of that correction remains pending the additional-request allowance. Platform filters use actual URL hostnames, and all off-target returned records remain in All sources. Existing user-edited briefing text is preserved. Only a verified, unedited generated attribution suffix is migrated to structured perspectives; old preview confirmations then become invalid.

Optional scheduling is **implemented but disabled**. The owner opens Settings & sources → Configure schedule, chooses a monitor, cadence, local hour and timezone, and confirms the state. Enabling also requires `ENABLE_SCHEDULED_DIGESTS=true` locally and a restart. The timer performs source retrieval and prepares a **private source-linked briefing preview** from up to five new links; all other returned records remain in Explore. It never invokes Codex or posts automatically. The owner must inspect and publish the exact preview through the normal UI. Persistent `(schedule_id, due_at)` claims prevent repeats; restart skips missed runs instead of replaying a backlog. The configured demo channel is the only possible eventual destination. Windows timezone data is pinned with `tzdata==2026.2`. Automatic channel delivery and email are deferred; email would require separate recipient consent and a delivery provider.

## Official implementation references

- [Codex SDK](https://developers.openai.com/codex/sdk/), [App Server](https://developers.openai.com/codex/app-server/), [configuration](https://developers.openai.com/codex/config-reference/), [authentication](https://developers.openai.com/codex/auth/)
- [Slack Socket Mode](https://docs.slack.dev/apis/events-api/using-socket-mode/), [acknowledgements](https://docs.slack.dev/tools/bolt-python/concepts/acknowledge/), [Block Kit limits](https://docs.slack.dev/reference/block-kit/blocks/), [manifest](https://docs.slack.dev/reference/app-manifest/)
- [Brave News](https://api-dashboard.search.brave.com/app/documentation/news-search/get-started), [Web parameters](https://api-dashboard.search.brave.com/app/documentation/web-search/query), [storage terms](https://brave.com/search/api/)
- [YouTube developer policies](https://developers.google.com/youtube/terms/developer-policies)

Pinned upstream schema/catalog and reviewed tool-registration excerpts are under `docs/reference/`; they are version evidence, not user configuration.
