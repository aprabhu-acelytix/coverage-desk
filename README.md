# Coverage Desk

A local Slack application for exploring coverage, inspecting message evidence, sharing selected findings, and preparing reviewed briefings. The interface is native Slack App Home: **Explore · Team board · Briefings**. There is no hosted dashboard or shared inference service.

Current workflow: [Coverage Overview](COVERAGE_OVERVIEW.md). Actual validation: [Overview validation](OVERVIEW_VALIDATION.md). Earlier research comparison: [General search validation](GENERAL_SEARCH_VALIDATION.md).

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

**Delete saved work:** Team board and Briefings have a **Delete** button beside each item you can remove. Confirmation explains the audience and effect. Creators can delete their own items; the configured app owner can also remove workspace-shared items. Private items remain private. Deleting a board item preserves its evidence and included perspectives in existing briefings, and invalidates their old publishing previews. Deleting a briefing removes its saved previews but keeps board findings and any already-published Slack message. Deletion waits until active app jobs finish; it does not invoke AI or source retrieval.

1. In **Explore**, choose a monitor and **Refresh**, or **Find coverage** for a new search. Editing uses **Save & refresh**. Enter a subject, optional campaign and messages. More options contains identity guidance, editable interpretation, dates, region, sources and the explicit research path.
2. One owner action interprets scope, searches, deduplicates and assesses a bounded batch. **Codex web research** is now the default, using the owner's managed ChatGPT sign-in. A restricted discovery operation searches every selected category, while a separate tool-free operation assesses the exact retained excerpts. Brave remains an explicit alternative; no provider switches mid-run. Planning, assessment and briefing use the separate no-tools worker.
3. **Overview** opens automatically: confirmed reporting totals, native outlet bars and full outlet names. Counts include compatible retained evidence across refreshes, before pagination. Select **View articles** for an outlet, then **Inspect** for dates, source observations and message evidence. Articles is one action away. Relevant/date-unconfirmed, unassessed, uncertain relevance and other content types remain separate and inspectable; none inflate confirmed-period reporting counts. Critical reporting and absent desired messages remain eligible. Source & history filters includes previous search scopes.
4. **Collection details** shows the interpretation, actual queries/path, limits and partial outcomes. **Assess pending** continues a bounded batch across the run, never just the visible page. Browse/filter actions never invoke AI. Capacity is shared with this build's durable ledger.
5. **Inspect** shows evidence, source details and discussion. **Save** defaults to private; explicitly choosing workspace sharing discloses the source. Including an assessment separately discloses its message wording, never private queries or monitor notes.
6. On **Team board**, add a perspective or change review status. Authors use Slack profile mentions. Teammates can collaborate on shared objects without invoking AI.
7. In **Briefings**, select up to five board findings, create a source-linked or AI-assisted draft, and edit its title and text. Team perspectives are attached separately and never sent to AI. Private sources keep the draft private.
8. **Preview & publish** shows the exact destination and content. Only the owner can confirm. Edits invalidate previews; they expire after ten minutes. Published items use **View briefing**. No unattended publishing occurs.

To delete a search, select it in Explore, open **Search options → Delete search**, then confirm. This removes the search, its collected results, run history and schedule. Saved board findings, perspectives, briefing snapshots and usage history are preserved. Wait for active work to finish (or cancel it) before deleting. Deleting the selected search switches to another saved search, or the empty Explore view if none remain.

## Runtime isolation and data flow

`COVERAGE_CODEX_HOME` defaults to `~/.coverage-desk-codex`, outside this repository and the development Codex home. Only its generated config is managed; unrelated Codex configuration is never changed. Runtime status exposes categorized status and model names, never account email, tokens or transcripts. `CODEX_BIN` is an executable path, never a shell command.

The SDK inherits environment variables by design, so it runs in a separate Python process launched with an OS-only allowlist. Slack, Brave, YouTube and unrelated service keys are absent. The SDK launches its App Server from an empty dedicated working directory. Host skill discovery, plugins, MCP, hooks, memories, shell, alternate code execution, images, connected tools and delegation are disabled using the pinned version's schema. A pinned official model catalog removes built-in apply-patch registration and disables shell support; model selection must still appear in the unmodified authenticated `model/list` response. It changes tool capability metadata, not endpoints or credentials. Effective config and catalog path are checked before inference. Unknown versions/configurations fail closed. Any unexpected SDK approval/tool request terminates the job instead of using the SDK's permissive default approval handler.

The filesystem permission profile denies root access; local tool network access is disabled. Hosted public web search is enabled only in the restricted research role. Model transport remains online. The boundary primarily removes model-accessible tools; a read-only sandbox or prompt alone is not treated as a secret boundary. The Windows worker uses a kill-on-close job object so timeout, cancellation or host termination kills its runtime descendant. Application analysis has one worker, a bounded queue, no automatic job retry, fresh ephemeral threads, input/output limits and exact source/evidence validation. App-side size/time limits do not guarantee zero remote consumption after cancellation.

Authentication uses Codex-managed ChatGPT sign-in only. API-key, external-token, third-party and signed-out modes are rejected. Credential storage prefers the supported OS store with `auto`; if Codex falls back to a file, it remains inside the dedicated home with restrictive owner permissions. The app never reads the auth file. Ephemeral threads and disabled history reduce local retention but do not promise zero provider retention. Runtime operational artifacts are separate from the application database. Review ChatGPT training/data controls before live use; this prototype uses public or synthetic material only.

## Sources, storage and limits

Brave storage permission was supplied by the owner (`BRAVE_STORAGE_ALLOWED=true`). This is **not independent verification of licensing or plan entitlement**. Disabling that setting blocks new retention, board saves, AI and publication using Brave material. A valid key alone does not establish storage rights. No arbitrary manual URL is fetched.

Every retained finding has its original URL, tracking-stripped duplicate key, source/endpoint, query/page/filter provenance, retrieval time, publication time when supplied, text-access label and content hash. A snippet is not a full article. Manual excerpts are user-supplied, not verified publisher text. These are all *retrieved results*, not all online coverage or a representative sample.

Default source/board/draft/cache retention is seven days, configurable downward. Expired records disappear from reads and are deleted on startup and every 30 seconds while running; WAL checkpointing follows deletion. Briefing snapshots expire no later than their sources. Monitor configuration persists separately. SQLite is not encrypted. Local expiry does not erase already-published Slack copies or provider-held records.

The SQLite usage ledger records source slots and AI jobs across restarts, including attempts before sending. The owner removed the lifetime application caps on 28 September 2026; previous usage and historical cap values are preserved. Settings shows recorded usage without an enforced lifetime maximum. Per-search source calls, result counts, AI batches, queue size and timeouts remain bounded. Actual ChatGPT subscription and source-provider quotas still apply and cannot be removed by the app. No automatic retry, paid fallback, purchasing, deployment or automatic channel posting is enabled.

## Validation and current limitations

Run `.venv\Scripts\python -m pytest -q` for isolated offline tests. `tests/eval_cases.json` contains nine labeled cases: alias, wrong entity, critical coverage, paraphrase, negation, company quote, missing context, duplicate, injection. Passing their schema/fidelity tests is not a model precision/recall claim. See `BUILD_NOTES.md` for actual results and `data/live-validation.json` for the local live check record.

The explicitly authorized validation command is `.venv\Scripts\python -m coverage_desk validate-live`. It resumes using persistent stage claims and budgets, preserves retrieved results, and never posts. It checks Slack, runs one News and one Web request once, then performs bounded AI checks when managed sign-in is ready. Failed/uncertain stages are not automatically retried. Repair before explicitly authorizing a new stage; the total budget still applies.

No browser/Slack UI surface was available to the build agent. Slack accepting a view payload is not a visual inspection. Check Home and modals in native light/dark mode, narrow width, five-row pagination, long headlines, empty/error states, and two actual teammate accounts. Simulated multi-user tests are not a real two-person walkthrough.

Social discovery uses public indexed URLs, never direct social-platform connections. The planner treats campaign/product focus as a topic, not an exact slogan. Each selected category gets a query, with a subject-wide query, topical variation, and a calendar-word variant for short date windows. Search tasks stay within the configured per-run request limit (maximum 12); any unattempted target is reported. Date operators are hints, not verification. One Refresh assesses the full finite collected set in small cancellable batches, independently of pagination. Each eligible public publisher page is checked once for bounded excerpts and publication metadata; denials are retained and not repeatedly retried. Finish research resumes interrupted assessment. Articles offers one main filter: Relevant, Needs attention or All results. Outside an outlet drill-down it includes all source types; the Overview separately offers Reporting or All source types. Confirmed outside-period results stay out of normal browsing. Relevant results with unknown dates remain visible but do not inflate confirmed-period overview totals. Login restrictions are never bypassed. Search details records what was attempted. No new source integrations or scheduling features were added.

The earlier usability-only check (`scripts/validate_redesign.py`) is historical. Its source-only flow and page-based analysis were superseded by this research redesign. The active comparison is documented in `RESEARCH_VALIDATION.md`; it used the same durable ledger.

Optional scheduling is **implemented but disabled**. The owner opens Settings & sources → Configure schedule, chooses a monitor, cadence, local hour and timezone, and confirms the state. Enabling also requires `ENABLE_SCHEDULED_DIGESTS=true` locally and a restart. The timer performs source retrieval and prepares a **private source-linked briefing preview** from up to five new links; all other returned records remain in Explore. It never invokes Codex or posts automatically. The owner must inspect and publish the exact preview through the normal UI. Persistent `(schedule_id, due_at)` claims prevent repeats; restart skips missed runs instead of replaying a backlog. The configured demo channel is the only possible eventual destination. Windows timezone data is pinned with `tzdata==2026.2`. Automatic channel delivery and email are deferred; email would require separate recipient consent and a delivery provider.

## Official implementation references

- [Codex SDK](https://developers.openai.com/codex/sdk/), [App Server](https://developers.openai.com/codex/app-server/), [configuration](https://developers.openai.com/codex/config-reference/), [authentication](https://developers.openai.com/codex/auth/)
- [Slack Socket Mode](https://docs.slack.dev/apis/events-api/using-socket-mode/), [acknowledgements](https://docs.slack.dev/tools/bolt-python/concepts/acknowledge/), [Block Kit limits](https://docs.slack.dev/reference/block-kit/blocks/), [manifest](https://docs.slack.dev/reference/app-manifest/)
- [Brave News](https://api-dashboard.search.brave.com/app/documentation/news-search/get-started), [Web parameters](https://api-dashboard.search.brave.com/app/documentation/web-search/query), [storage terms](https://brave.com/search/api/)
- [YouTube developer policies](https://developers.google.com/youtube/terms/developer-policies)

Pinned upstream schema/catalog and reviewed tool-registration excerpts are under `docs/reference/`; they are version evidence, not user configuration.


## Research migration and evidence

Startup performs a consistent SQLite backup under `data/backups/` before the idempotent research metadata migration. Existing object IDs, board references, notes, draft text, privacy, expiry and budget history remain unchanged. Preview tokens are invalidated. Backups keep original expiries and are purged alongside the live store; restoring a backup must never roll back the live budget ledger. Prior-scope observations remain inspectable.

Source identity uses canonical URLs, preserving meaningful query parameters. Analysis reuse binds content/version, criteria, model, analysis version and private actor/workspace. Runs freeze relative windows to UTC timestamps. Publisher metadata verification is bounded and separate from source excerpts; unknown dates remain reviewable. Brave's [page-age field can mean publication or modification](https://api-dashboard.search.brave.com/api-reference/news/news_search/get), so it is not treated as a verified publication date.

See `RESEARCH_VALIDATION.md` for the before/after comparison, exact live limits and remaining unverified checks. `scripts/validate_research.py` is an explicit validation helper with durable attempt claims, not a startup task. Never rerun a claimed case by clearing its claim or ledger. Offline tests do not load `.env` or call the network.


**Share an overview:** Explore > Preview & share overview > explicitly approve disclosure of private client/campaign information, counts, outlet names and source excerpts > review all included sources > confirm the exact preview. This freezes counts, period, source IDs and caveats in a private draft. Only final Publish sends to the configured channel and makes the frozen copy workspace-visible. Source corrections or expiry invalidate pending publication; create a fresh snapshot. Editorial briefings remain editable; frozen overview snapshots are corrected by correcting evidence and creating a new snapshot.

Current search-completeness results and remaining visual checks: [RESEARCH_COMPLETENESS_VALIDATION.md](RESEARCH_COMPLETENESS_VALIDATION.md).

### Review findings and understand outlets

Use **Mark relevant** on an uncertain finding to record your decision. This changes its match status only: an unknown date stays unverified and excluded from dated overview totals. Already-relevant items may still appear in Needs attention when a date or article type needs checking.

**Inspect > Edit finding** replaces the old Correct buttons. Change one detail at a time. **Inspect > Source details** explains the outlet's focus, editorial signals and priority, with supporting links. Established reporting appears before standard-priority findings; items are newest-first within each priority. **Outlet priority** lets the owner raise, lower or reset an exact website's priority with a reason. No AI runs when reviewing or sorting.

The initial catalog covers ten reviewed outlets; other sites are explicitly unreviewed, not labeled unreliable. Priority is a transparent editorial convenience, not an independent trust certification. See [OUTLET_UX_VALIDATION.md](OUTLET_UX_VALIDATION.md) for scope and validation.
