# Codex runtime — personal ChatGPT sign-in

Adaptive social discovery uses up to two existing `discover` operations, sharing the run allowance as described in [SOCIAL_SEARCH.md](SOCIAL_SEARCH.md). Each pass retains the same role isolation and one boundary reservation. The total reservation ceiling remains `calls + 1`; two-pass discovery therefore plans at most `calls - 1` searches. No runtime tool permissions or authentication interfaces change.

This document changes how the app obtains AI analysis; it does not turn Coverage Desk into a chatbot or a public AI service. Implement one small adapter, not a general agent platform.

## 1. Supported route and boundary

**Active authorization:** The current goal already authorizes owner-operated live runtime validation, with usage recorded durably, including retries. The owner removed the lifetime app caps on 28 September 2026; per-job limits and actual subscription limits remain. Do not ask again for live-call approval. Managed sign-in may still require the owner's browser intervention. No API-key fallback, token copying, shared inference, scheduled AI or deployment is authorized.

Use the official Codex Python SDK (`openai-codex`), which controls a local App Server. Check and pin a compatible published SDK/runtime pair. Use direct App Server stdio only when a documented SDK gap requires it; do not create an HTTP proxy or implement both routes. [R1, R2]

The runtime must use **Codex-managed ChatGPT authentication**, not external-token mode. Codex performs its own login, storage, and refresh. Confirm the active authentication method through the documented account surface, not by opening credential files. Reject API-key, external-token, third-party-provider, and unauthenticated modes for live analysis. Do not use `OPENAI_API_KEY`, `CODEX_API_KEY`, a custom model endpoint, browser cookies, or copied OAuth tokens. [R2, R3]

This is a local, owner-operated demonstration. Technical SDK support does not establish permission for any conceivable deployment. Personal-plan restrictions include account sharing and third-party-service use; a hosted/team-wide inference product requires a separately verified arrangement. Do not market this design as a universal “Sign in with ChatGPT” backend for Slack users. [R4]

Only the configured Slack owner can request a live AI job. Teammates collaborate on explicitly shared artifacts; they do not use the owner's session. No scheduled AI, public endpoint, background polling for AI work, account pooling, automatic credit purchases, allowance resets, or separately billed fallback. Normal subscription limits apply. [R5]

## 2. Credentials and process setup

`COVERAGE_CODEX_HOME` is an **application setting**, not a Codex configuration key. Expand `~` and pass that resolved directory as `CODEX_HOME` only to the runtime/login child process using the SDK's documented process configuration. Default to `~/.coverage-desk-codex`, outside the repository and synced folders. Do not globally modify the developer's `CODEX_HOME`.

The owner signs in to that dedicated runtime home through the normal Codex browser flow. A separate local sign-in can be required even when the development session is already signed in; it uses the same subscription, not a new API key. Do not copy an existing `auth.json`. Prefer the supported OS credential store; where unavailable, clearly disclose Codex's file storage and restrict filesystem access. Verify that the chosen home/store combination does not change unrelated Codex sessions. [R3]

Add simple local auth/status commands using the **same executable and home as the runtime**. Never launch login from an untrusted Slack action, display login challenges in shared channels, or log raw account responses. The app may tell the owner to finish sign-in locally. `CODEX_BIN`, when supplied, is a local executable path, not an arbitrary shell command.

Do not ask the owner to expose private configuration for diagnosis. A diagnostic summary should contain only runtime/SDK versions, auth-mode status, model availability, control checks, and categorized errors.

## 3. Minimal analysis job

A proposed application-level operation is `analyze(evidence, criteria, actor)`; this is **not an SDK method name**. Codex must use the installed SDK's actual documented interfaces.

1. Verify the workspace, acting Slack user, ownership, selected records, source-use permission, and requested operation in backend code. The UI is not an authorization boundary.
2. Freeze the authorized source text and monitor criteria for this job. Do not add team notes, other client records, a development chat, arbitrary attachments, or Slack history. Treat source text as data, never as instructions.
3. Check ChatGPT auth and runtime controls before starting inference. Choose a model actually listed for the account; a configured unavailable model gives an actionable error rather than a silent substitution.
4. Start a fresh, isolated analytical thread. Use documented per-turn structured output (`outputSchema` in App Server) and compatible SDK support. Use ephemeral context where supported; otherwise disclose and bound local retention. Do not resume the development thread or reuse a conversation across private monitors. [R2]
5. Collect the completed final response, not partial tokens or reasoning. Validate the JSON shape, selected source IDs, exact evidence spans, and size limits in ordinary code before saving/displaying it. The model supplies classifications/text only; it cannot choose database IDs, visibility, posting destinations, or actions.
6. Recheck access before publishing the result into a view or board. Mark timeout, cancellation, invalid evidence, or uncertain completion explicitly. Never automatically rerun a job whose remote outcome is unknown.

Use one concurrent AI job, a small bounded queue, input/output limits, and a configurable timeout. Deduplicate repeated Slack action deliveries. Read-only account/rate-limit metadata can improve owner-facing status when supported; no credit-purchase or reset methods. A timeout or output-size check is not a guarantee of zero server-side consumption. [R2]

## 4. Runtime tool and secret isolation

The analysis worker is intentionally **not** a coding agent. Retrieval, database writes, and Slack posts belong to trusted application code.

Generate a dedicated, version-appropriate runtime config after checking official documentation and the installed schema. Do not ship guessed flags. Constrain the worker with all of the following:

- Clean working directory outside the repository, with no inherited project instructions, personal memories, plugins, MCP servers, skills, or hooks. Do not import the build agent's configuration or history.
- An allowlisted subprocess environment. Retain only variables required for the executable, OS credential access, and approved authentication/transport. Exclude Slack/search/YouTube keys and unrelated service secrets. Use safe argument arrays/stdio, never shell interpolation of source text.
- Disable model-accessible shell/exec, code-execution alternatives, editing, connected tools, and subagent delegation through supported controls. Do not assume an empty dynamic-tools list removes built-in tools. Verify the effective configuration. [R6]
- No privilege escalation or auto-approved actions. Deny unexpected tool/approval requests and terminate that job safely.
- Least-privilege filesystem/tool network access where supported. **Read-only does not mean unreadable:** the documented sandbox can have broad read access unless explicitly restricted. Do not claim an empty working directory or `approvalPolicy=never` alone prevents file reads or execution. [R2, R6]

Codex itself still needs outbound connectivity for authenticated inference. Do not block the entire child process network while expecting model access; distinguish model transport from tool network permissions.

Use harmless canary files and mocks to test isolation. Never prove a secret-read denial by placing real credentials in a prompt. When the installed model/runtime cannot support the intended boundary, select a supported compatible configuration or mark live AI unavailable; continue offline implementation rather than weakening controls. Keep the solution small—do not build a new sandbox platform.

## 5. Data handling and user experience

This route follows ChatGPT/Codex data controls, **not the ordinary API defaults**. For personal Plus/Pro accounts, OpenAI states that conversations may be used to improve models unless training is turned off in ChatGPT data controls. Explain that before sending real source material. Public/synthetic evidence only for this demo; no confidential client material. Ephemeral/local cleanup does not imply zero OpenAI retention. [R5]

Show a compact owner-facing state: `Demo fixtures`, `Ready`, `Sign-in needed`, `Working`, `Usage limit`, or `Unavailable`. Keep sources and boards usable independently. Give the owner a Cancel action while work runs. Other users should see the appropriate saved assessment or “AI analysis is owner-operated in this prototype,” not a misleading authentication button.

Shared analysis must never reveal the owner's email, session identifiers, detailed subscription usage, credential location, or development conversation. Preserve the distinction between source evidence, AI assessment, and human perspective.

## 6. Focused tests and live verification

Add focused tests alongside ordinary app tests:

- Demo mode never starts a live Codex job; live failures never become fixture success.
- Non-owner and wrong-workspace requests fail before enqueue and are rechecked by the worker.
- Signed-out, API-auth, usage-limit, and unsupported-runtime cases give truthful states.
- Subprocess environment is allowlisted; no app secrets or project files enter analysis inputs.
- Fresh job context, output schema, exact evidence checks, and invalid-output rejection.
- Cancellation, timeouts, queue limits, duplicate Slack deliveries, and no automatic retry after uncertain completion.
- Collaborators can save/comment/review/edit authorized shared artifacts without invoking AI.
- Private configuration/output cannot leak through a shared cache, board, draft, or status message.

Offline mocks establish application behavior, not live runtime isolation. Within existing owner authorization, inspect effective runtime controls and run **one tiny synthetic analysis** with no tools or external source fetching. Record actual SDK/runtime versions, auth mode, model, outcome, and validation checks without account details. Report a blocked live check honestly.

## References

Official documentation checked while preparing this revision on 27 September 2026. Recheck against the version actually installed. The process restrictions above are design requirements, not claims of a completed implementation.

- [R1] Codex SDK: `https://developers.openai.com/codex/sdk/`
- [R2] App Server protocol/auth/structured outputs/sandbox: `https://developers.openai.com/codex/app-server/`
- [R3] Codex authentication and credential storage: `https://developers.openai.com/codex/auth/`
- [R4] Personal plan restrictions: `https://help.openai.com/en/articles/9793128-what-is-chatgpt-pro`
- [R5] Codex plan usage and data controls: `https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan`
- [R6] Codex configuration: `https://developers.openai.com/codex/config-reference/`


## Research redesign: two explicit operations

`research` is a separate role in the same pinned SDK/App Server architecture. It enables `web_search="live"` through per-client config overrides; analysis, query planning and briefing keep `web_search="disabled"`. The inference lock is acquired before preparing shared generated configuration. Both roles keep the clean environment, dedicated runtime home, root filesystem denial, no shell/editing/MCP/plugins/images/delegation, and fresh ephemeral threads. No development-session tools or credentials are inherited.

The 0.157.1 SDK exposes optional `WebSearchThreadItem.results`. The live slice returned `text_result` objects with source refs, URLs and snippets. A registry is built only from those observed results. A generated URL/quote or attempted open is not evidence. Discovery returns only a completion summary; model-authored candidate lists and citations do not enter the evidence registry. Separate tool-free assessment receives the app-retained snippets. Each supported/contradicted message requires a validated exact quotation. An invalid assessment leaves that finding in review without rejecting other valid findings. Completed web events are checkpointed to the parent so cancellation can preserve observed sources. Model-generated text is never used to verify itself.

The earlier combined discovery/classification trials showed poor date control and exact-evidence failures. The revised default is **Codex native web**, requested by the owner: one no-tools planning job, a separate restricted discovery job, and no-tools assessment batches across the full finite unique current evidence set. Calendar-word queries supplement date operators; independently verified dates gate the Relevant view. Each eligible public article gets a bounded publisher check before assessment, with three concurrent requests maximum. Retain short public excerpts and explicit publication metadata; respect access denials and cache attempts. Incomplete work has a Finish research action. Brave remains an explicit alternative with the same category expansion and assessment pipeline; no mid-run provider fallback occurs.

Native discovery reserves one durable source slot per instructed search task (at most 12) plus one cancellation-boundary action. The guard interrupts when observed actions exceed the task bound; events occur after initiation and are not a hard network-request firewall. One search event can contain multiple queries and does not reveal the provider's internal requests. Reservations are not refunded. AI-planned Brave and public metadata checks charge each outbound request including redirects, before sending. Lifetime app caps were removed by the owner on 28 September 2026. All usage and historical cap values remain recorded; per-turn action limits remain enforced.

Application metadata verification applies only to provider-returned research URLs, never arbitrary manual contributions. DNS answers and every redirect must be public; connections pin the validated address and preserve TLS hostname checks. Requests have port, time, redirect and byte limits, carry no cookies or provider credentials, and do not bypass denied access. Only explicit publisher publication metadata is retained. Brave page_age can mean published or modified, so it alone never establishes publication eligibility.


## Coverage Overview assessment

The tool-free assessment now returns content type independently of relevance, message evidence and publication certainty. Store exact classification/outlet/redistribution quotations; reject unmatched quotes and leave unsupported types unknown. A news search hit alone does not establish reporting. Counts and grouping are computed in Python, never model prose. Browsing, correction, chart generation and snapshot creation do not invoke the model.

New runtime output uses `LiveAnalysis` with every property required; legacy stored classifications may omit the new coverage object. This follows the [strict structured-output requirement](https://developers.openai.com/api/docs/guides/structured-outputs). The existing official [App Server output schema interface](https://learn.chatgpt.com/docs/app-server) and managed ChatGPT authentication remain in use; no API key or paid fallback was introduced. A required-field regression test guards the schema sent to the runtime.


A separate `classify_coverage` operation runs in the same restricted no-tools worker when an already-assessed article still needs content-type evidence. It receives only allowlisted public title/excerpt/URL/access and publisher metadata, not private notes, queries, message criteria or team perspectives. It preserves existing message assessments and runs only after relevance assessment has covered all collected findings. Each job retains its input/output/item/time bounds; no automatic retry loop is introduced. Unknown type is an explicit result, not a hidden exclusion or automatic retry. A schema/evidence-version key prevents redoing unchanged type assessments.
