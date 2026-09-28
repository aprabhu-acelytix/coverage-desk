# Coverage Desk — Codex implementation brief

**Revision 2 · ChatGPT-authenticated local runtime · 27 September 2026**

This version supersedes the API-key starter. The application must use the owner's Codex-managed ChatGPT sign-in for live AI analysis. No OpenAI API key, API billing setup, or API fallback. Read `CODEX_RUNTIME.md` alongside this brief; it defines the runtime boundary, not additional product features.

## 1. Objective and scope

**Approved usability revision:** The user-approved redesign supersedes older UI labels and source defaults below. Use New coverage search → Save & collect, expandable advanced options, focused finding modals, profile mentions, readable provenance, independent source/assessment filters, and persisted collection progress. New UI searches default to News, Web, Instagram, X and LinkedIn through Brave web discovery; preserve existing searches. This is not direct social-platform integration. Redesign validation adds at most two source requests and zero AI jobs within the original persistent ledger.

**Active owner authorization (27 September 2026):** The current goal authorizes implementation and bounded live integration now, superseding later wording that asks for another live-call approval or limits validation to one tiny check. Load the configured `.env` without exposing it, preserve values, and use `APP_MODE=live`. Tests remain offline. Persist a total cap of 30 source requests and 10 runtime AI jobs across restarts/retries. Brave storage permission is owner-supplied, not independently verified. No purchases, API fallback, deployment, automatic channel posts or scheduled AI. Exact owner UI preview/confirmation is still required for publishing.

Build a professional, usable custom Slack app called **Coverage Desk** for discovering client coverage, examining campaign-message evidence, and collaborating on selected findings. It should feel like an editorial research desk, not a generic chatbot. Users can monitor any company, brand, product, or public-facing person; do not hard-code Day One's clients.

This is a take-home prototype for a Junior Freelance AI Engineer interview at Day One Agency. The supplied assignment's media-monitoring option requires online-news coverage and key-message scanning, plus an outline of Slack/email integration with scheduled notifications. The assignment specifies **2–3 hours total effort**, including preparation, and separately requests a presentation of at most 10 slides and a nontechnical VP email. Source: `Freelance AI Engineer Assignment(1).pdf`, pages 1–2. Social discovery and working collaboration are the applicant's chosen extensions, not additional requirements imposed by Day One.

Prioritize one convincing end-to-end workflow: **create a monitor → retrieve coverage → inspect AI message evidence → save to a shared board → add a teammate's perspective → preview and publish a briefing**.

Make a short plan, then implement. Budget the work to respect the assignment; reserve time for validation, handoff, and the applicant's preparation. If the budget is insufficient, finish and clearly identify the smallest working core rather than expanding indefinitely. Never invent time spent, test results, source coverage, or demo evidence.

**Core:** news/web discovery, manual contributions, AI message tracking, polished native Slack views, private/shared boards, previewed channel briefings, transparent source status, tests and setup instructions.

**Next, only after the core works and within the remaining budget:** YouTube discovery and opt-in scheduled notifications. **Stretch:** explicitly permitted publisher RSS feeds. Explain deferred capabilities; do not depict them as implemented. Collaboration is part of the core and must not be discarded in favor of more source integrations.

## 2. Implementation approach

- Use a small Python application with Slack Bolt, Socket Mode, SQLite, the official **Codex Python SDK (`openai-codex`)**, schema validation, an HTTP client, and focused tests. Check the currently supported SDK and its pinned Codex runtime before choosing dependency versions. Avoid unnecessary frameworks. The Codex SDK is not the ordinary OpenAI API client; do not add an API-key dependency.
- Put live analysis behind a small `CodexAnalyzer` adapter using the official Codex SDK and its local App Server. Use documented structured-output support, plus application-side validation. Direct App Server JSON-RPC over stdio is an acceptable fallback only if needed for a documented SDK capability gap; do not build both implementations. No Custom GPT, model training, general chatbot, browser automation, or autonomous research agent. Set `CODEX_MODEL` to a model actually available through the owner's ChatGPT-authenticated runtime; do not assume the build agent's model is available or optimal for runtime analysis. See `CODEX_RUNTIME.md`.
- Keep source adapters, analysis, storage, and Slack rendering separate but lightweight. No microservices, Redis, vector database, LangGraph, custom OAuth distribution service, billing system, or separate React dashboard.
- Use a bounded background worker for retrieval/analysis. Acknowledge Slack actions immediately, within Slack's documented three-second requirement; never wait on search or the model before acknowledging. Show progress and update App Home when finished. Handle errors and stale view updates without breaking navigation.
- Target **one explicitly installed development workspace**, with multiple collaborating users but **one owner-operated AI runtime**. Bind requests and database access to the authenticated workspace and acting user. Only `SLACK_OWNER_USER_ID` may initiate any live AI job, including briefing generation or reanalysis. Teammates can browse explicitly shared findings, add perspectives, update review status, and edit shared drafts without access to the owner's subscription or Codex history. The app is a personal prototype, not a pooled AI service. Do not build public distribution or deploy cloud resources.
- Start with labeled synthetic fixtures and mocked network calls. Missing source credentials or Codex sign-in must not block offline implementation. `APP_MODE=demo` uses clearly labeled fixture retrieval and fixture analysis, never live AI/search. `APP_MODE=live` uses real configured providers only, with `ALLOW_LIVE_CALLS=true` required for source/model work. Neither flag alone authorizes deployment or channel publishing. A failed live provider must never silently fall back to fixtures. Pin SDK/runtime versions and verify a small compatibility slice before expanding UI features.

## 3. Monitoring and data collection

A client identity has a display name, aliases, optional official handles/domains, and disambiguation notes. A saved monitor references that identity plus optional campaign/product terms, desired messages, date range, language/region, and enabled sources. General coverage works without campaign terms. Campaign filtering and message tracking can be combined; they are not mutually exclusive modes.

### Core sources

**Brave News and Web Search:** implement separate adapters using `BRAVE_API_KEY`. Use ordinary search-result endpoints, not the Answers product. Fetch actual provider results with bounded pagination. Preserve which endpoint, query variant, filters, and page produced each finding. General client searches must run alongside narrower campaign searches so desired-message keywords do not preselect the evidence.

Brave explicitly requires a plan granting storage rights to retain API results. Keep `BRAVE_STORAGE_ALLOWED=false` until the owner confirms the applicable entitlement. Do not silently persist results, snippets, derived copies, or shared outputs when permission is unconfirmed. Mark that live connector as awaiting storage configuration and continue offline/manual-source work; do not treat a working key as proof of licensing. Do not bypass this restriction with another collection route. Record the owner's non-secret entitlement confirmation in setup notes.

**Manual contributions:** accept a source URL, title, optional user-supplied excerpt, and optional comment. Label provenance as user-submitted and distinguish submitted text from verified publisher text. For the core build, do not automatically fetch arbitrary submitted URLs. Keep validation and safe link handling; this avoids creating an unnecessary scraping/SSRF surface.

### Optional sources

**YouTube:** when `YOUTUBE_API_KEY` is configured, implement public video discovery using the official Data API. Initially show attributed titles, descriptions, channel identity, publication dates, and links. Do not download media, scrape transcripts, imply access to video contents, infer audience demographics, or aggregate view counts across unrelated channels. Keep this source's discovery and display distinct from any unverified analysis permissions. Review current YouTube policies before forwarding API data to an AI service or retaining/exporting it. Apply required refresh/deletion handling to permitted stored data; do not keep API data indefinitely. Missing access means “Not connected,” not zero coverage.

**RSS:** add only explicitly configured feeds whose intended access/use is permitted. Document the feed list and collection limits. Do not present selected feeds as representative of all media.

Do not implement unofficial X, Instagram, TikTok, or Reddit scraping. Display these as **Not integrated** in source settings. A social URL discovered by web search is **web-discovered**, not evidence of an official platform integration or exhaustive social coverage.

### Coverage transparency

- The explorer exposes every retained retrieved record the user is authorized to see, including uncertain and likely irrelevant matches. Classifications are reversible filters, not silent deletions. Do not hide critical coverage, small outlets, or low-engagement items.
- Default to chronological display, not AI-selected importance. Expose active filters, “Clear filters,” duplicate groups, and exclusions. Preserve original URLs; strip only known tracking parameters when deduplicating.
- Group duplicates without removing the ability to inspect individual sources. Distinguish source publication time, provider discovery time when supplied, and our retrieval time. Unknown publication dates remain unknown.
- Store permitted attribution, source URL/ID, query provenance, text-access level, retrieval timestamp, analysis status, and content hash. Show `excerpt only`, `metadata only`, or `full text supplied` honestly. Do not equate a search snippet with an entire article.
- Surface run-level provider status, checked time, applied filters including safe-search/language, pages/results collected, pagination/cost caps, failures, and unsearched sources. “No matches,” “Partial results,” and “Not searched” must be distinct.
- Say **all retrieved results**, never “all online coverage,” “unbiased,” or “nothing missed.” Any counts describe this collection, not reach, market share, or the whole internet. Do not combine unlike platform metrics into an exposure score.

## 4. AI behavior and evaluation

AI is a bounded analytical layer behind the interface, not the interface itself.

For each eligible finding, produce schema-validated fields: client relevance (`relevant`, `uncertain`, `not_relevant`), campaign relevance where applicable, a concise explanation, and per-message assessments. Use message labels such as `supported`, `contradicted`, `not_observed_in_available_text`, and `insufficient_evidence`. Attribution matters: a journalist quoting a company claim is not independent endorsement.

Require supporting source IDs and exact short evidence spans for supported/contradicted classifications. Validate evidence against the actual input text; reject invented citations or quotes. Exact matching checks quotation fidelity, not semantic correctness, so evaluate both separately. Absence from an excerpt must not become a claim of absence from the full article. Avoid uncalibrated confidence percentages.

Treat retrieved text as untrusted data. It must not override instructions, trigger tools, disclose secrets, choose recipients, or publish messages. Pass only the selected, authorized evidence and monitor criteria to the analytical worker. Disable unnecessary agent tools through verified runtime controls; prompts and read-only filesystems alone are not security boundaries. Use isolated per-job context, bounded input/output sizes, cancellation, and no automatic job retries by default. Do not send Slack conversation history or private team notes to the model. Human notes are added to briefings deterministically unless separately and explicitly selected for AI use; this prototype should keep them out of AI inputs. Make the external-AI data flow visible.

**Data handling:** this path uses ChatGPT/Codex data controls, not the API's data-handling defaults. Do not carry over a Responses API `store=false` parameter or promise zero retention. Use supported ephemeral runtime threads where available and document local runtime artifacts separately from application records. The owner should review ChatGPT's training controls before live analysis. Local orchestration does not mean offline inference; use only public or synthetic demo material.

Create editable, source-linked briefing drafts only from the selected authorized findings. Separate **source evidence**, **AI assessment**, and **team perspective**. A failed AI request leaves sources browsable and labeled unassessed. Cache analysis only when retention is permitted and the content, monitor messages, analysis version, and authorization scope match. Shared cache entries must not expose private monitor criteria or private outputs. Runtime failures must distinguish signed out, owner-only action, usage limit, timeout, cancellation, unsupported runtime configuration, and invalid evidence.

Include a small labeled evaluation set covering aliases, wrong-entity matches, critical coverage, paraphrases, negation, company quotations, missing context, duplicates, and prompt injection. Report actual evaluated precision/recall or error counts with denominators; do not claim internet-wide recall from fixtures.

## 5. Slack experience and visual direction

Use native App Home, Block Kit, modals, and messages. App Home is personal; shared objects live in the application database, not in a supposedly shared Home tab. Use established components and validate supported surfaces/limits. Do not assume arbitrary HTML/CSS, custom fonts, charts, or paid Slack Lists are available.

Use **Explore · Team board · Briefings** as simple navigation inside Home, not invented top-level Slack tabs. Settings and source status can open in modals. Favor short headlines, clear spacing, consistent actions, restrained metadata, and readable native light/dark-mode presentation. No decorative emoji walls, giant text dumps, forced slang, fabricated trend scores, or Day One logo imitation.

### Explore

A compact header contains the selected monitor and visible freshness/status. Show a primary **New monitor** or **Refresh coverage** action, a **Filters** modal, and a concise summary of active filters. Display roughly five result rows per page with stable pagination. Each row shows its title/link, source/platform, date, access-level label, and concise message status. Actions: **Inspect**, **Save**, and an overflow menu where needed. Keep advanced filters out of the first screen.

The detail modal shows source metadata, the available excerpt, AI assessment, evidence, and team notes without conflating them. Clear empty, loading, partial-failure, missing-source-key, Codex-disconnected, usage-limit, and no-matches states must offer an actionable next step. Screens must remain useful when no AI output exists. Keep a compact AI status indicator rather than a developer-console panel. Owner-only controls should explain the personal-prototype limitation without showing account email, tokens, transcripts, or private usage details to teammates.

### Team board — required

Use two explicit visibility levels for this prototype: **Private to me** and **Shared with this workspace**. Sharing requires a clear confirmation explaining the audience. Workspace sharing is deliberate, not automatic. The owner controls the monitor configuration and visibility; teammates can contribute notes and review statuses to shared boards. Filtering remains personal and never changes a colleague's view.

Support saved findings, author-attributed **Add perspective**, and simple review status (`New`, `Reviewed`, `Use in briefing`). Human corrections annotate rather than erase the original evidence or AI output. Prevent duplicate saves. Authorize every read/write, including actions with tampered object IDs. A private finding saved into a shared board must have an explicit disclosure confirmation. Do not share private monitor configuration incidentally.

### Briefings — required

Select board findings, let the configured owner generate a short draft, allow authorized collaborators to edit it, and preview the exact message and destination before publishing. Require an explicit owner action to post in this prototype. Recheck source permissions and retention at generation and publication time. Use a compact structure: **What changed · Message evidence · Worth discussing**, with source links and clear AI labeling. A saved briefing is a dated snapshot, unlike a continuing monitor. A collaborator's edit or button click must never implicitly trigger the owner's AI worker.

For the prototype, posting is limited to the configured public demo channel where the bot has been invited. Do not send to arbitrary channels, external recipients, or private channels. After posting, users can discuss in Slack's native thread; the app need not read those replies. The app's structured notes are separate from Slack's thread history. Provide accessible fallback message text and prevent untrusted content from creating mass mentions or unintended unfurls.

### Day One alignment

Day One publicly identifies Fresh Perspective, Cultural Fluency, Earned Attention, and Strategic Balance as foundations. Translate these into behaviors: invite different team interpretations; preserve the source/platform context; make evidence worth sharing rather than chasing metrics; relate new coverage to saved campaign messages. These are proposed design interpretations, not official Day One product requirements. Make the result broadly useful without making it a Day One-only tool.

## 6. Scheduling, configuration, and safeguards

Implement scheduling only after the core is working. A minimal scheduler may periodically refresh an explicitly enabled monitor and send a deterministic, source-linked “new findings” digest. **Scheduled or teammate-triggered jobs must not invoke the owner's Codex session.** AI analysis stays owner-initiated, and AI-written conclusions require preview/review. Scheduling is disabled by default; the owner chooses the destination, cadence, and timezone and confirms before activation. Persist configuration and delivery IDs, avoid duplicate sends on retried events, and show failed/uncertain delivery rather than blindly reposting. Do not flood a channel with missed jobs on restart. State that the backend process must remain running. If deferred, document a concrete integration design and mark the UI accordingly.

Use the supplied starter manifest and `.env.example`. Review them against current documentation before use. Initial Slack bot scopes are only `commands`, `chat:write`, and `channels:read`; the separately created app-level token needs `connections:write`. Subscribe to `app_home_opened`, enable interactivity and Home, and implement `/coverage`. No channel-history, DM-history, or user-token permissions. `SLACK_DEMO_CHANNEL_ID` is configuration, not a secret.

Keep Slack and data-source credentials in local environment variables or a gitignored `.env`; keep **Codex authentication exclusively in Codex's managed credential store**. Never display secrets, place them in source/fixtures, copy auth files, or put them in screenshots/logs. Redact request headers and key-bearing URLs. Do not run commands that dump the environment, `.env`, or Codex credential files. Use a dedicated runtime configuration/home outside the project, without importing the development session's plugins, MCP servers, skills, hooks, or history. Pass no application-secret environment variables to the analysis child process. Preserve existing files, other Codex profiles, and unrelated projects.

Apply configurable per-run source-call, page, result, AI-job, input-size, output-size, concurrency, and time limits. Include retries in accounting; default application AI retries to zero. Do not invent a token-limit parameter that the chosen Codex interface does not support, or describe app-side output truncation as a hard provider billing cap. Subscription allowances still apply and are shared with the owner's other Codex use. Handle usage exhaustion without API fallback, automatic credit purchases, resets, or account switching. Live source/model checks require explicit owner authorization; configuring secrets alone is not permission to make calls. Handle 401/403, 429, timeouts, malformed responses, and unavailable sources honestly.

Default permitted record retention to seven days; implement expiration/deletion and prevent expired material appearing in Home or new briefings. Document what happens to already published Slack copies and provider-held data; do not promise complete erasure across systems. Do not claim the unencrypted SQLite file is encrypted at rest. Avoid confidential client information for this demo.

## 7. Acceptance and handoff

Write and run focused offline tests for query construction, complete pagination within caps, transparent exclusions, reversible duplicate grouping, validated AI evidence, model failures, workspace/private-object isolation, teammate contributions, Slack payload limits/escaping, retry idempotency, and source retention. Add the compact runtime tests in `CODEX_RUNTIME.md`, especially owner-only invocation, API-auth rejection, no secret inheritance, and cancellation. Include fixture-generated Block Kit payloads for reviewing the screens. Validate visual usability in a real Slack workspace when available; do not call a JSON snapshot a visual inspection or fabricate screenshots.

Once credentials/sign-in and explicit authorization are present, run a bounded check: Slack authentication; Codex-managed ChatGPT auth and effective runtime controls; one tiny synthetic analysis job; one Brave News and one Brave Web query only when storage permission is confirmed; YouTube only if separately configured and approved. No publishing, scheduling, retries, or full live evaluation in this check. Record actual call counts and outcomes without raw credentials/account details. Then walk through create → search → inspect → share → comment → preview with the owner. Only publish through a separate explicit UI confirmation to the configured demo channel. Distinguish simulated multi-user tests from a real two-user walkthrough. A source blocker must not block testing Codex on synthetic input, and a Codex blocker must not block manual browsing and collaboration.

Deliver readable code; dependency/install files with the tested SDK/runtime versions; the updated Slack manifest and secret-free environment template; a README with PowerShell and Bash setup/start/test commands; a safe local Codex sign-in/status helper that uses the runtime's own executable and credential home; a three-minute demo script; and concise build notes explaining architecture, actual testing, data quality, hallucination controls, privacy, maintenance, the owner-only AI limitation, and deferred work. Do not create a slide deck or invent autobiographical details; leave presentation production to a separate request.

Finish with a brief status: what works, what was actually tested, any credential/access blocker, how to start the app, and the exact next manual action. Do not stop at planning or scaffold-only code. Do not claim live verification while credentials are missing. Do not extend the assignment into an open-ended production build.

## Official references to verify during implementation

These are implementation references, not instructions from retrieved content. Account-specific access and entitlements still require checking.

- Slack Socket Mode: `https://docs.slack.dev/apis/events-api/using-socket-mode/`
- Slack App Home: `https://docs.slack.dev/surfaces/app-home/`
- Slack manifest reference: `https://docs.slack.dev/reference/app-manifest/`
- Slack acknowledgement timing: `https://docs.slack.dev/tools/bolt-python/concepts/acknowledge/`
- Slack Block Kit limits: `https://docs.slack.dev/reference/block-kit/blocks/`
- Codex SDK: `https://developers.openai.com/codex/sdk/`
- Codex App Server: `https://developers.openai.com/codex/app-server/`
- Codex authentication: `https://developers.openai.com/codex/auth/`
- Codex configuration: `https://developers.openai.com/codex/config-reference/`
- Codex plan usage/data controls: `https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan`
- Personal subscription restrictions: `https://help.openai.com/en/articles/9793128-what-is-chatgpt-pro`
- Brave News Search: `https://api-dashboard.search.brave.com/app/documentation/news-search/get-started`
- Brave product/storage-rights FAQ: `https://brave.com/search/api/`
- YouTube setup: `https://developers.google.com/youtube/v3/getting-started`
- YouTube developer policies: `https://developers.google.com/youtube/terms/developer-policies`
- Day One's stated foundations: `https://d1a.com/what-we-do`
