# Build and validation notes

## Architecture

Slack Bolt / Socket Mode → authorized service operations → scoped SQLite records. Brave adapters and manual sources are separate from AI. One bounded worker performs retrieval/analysis, immediately acknowledged Slack actions update Home on completion. Native Block Kit rendering is in `coverage_desk/ui.py`. `runtime.py` launches an isolated host for the official SDK in `runtime_worker.py`.

No public HTTP endpoint, ordinary OpenAI API client, API billing fallback, token copying, channel-history permission or shared subscription inference service was added. No channel post or deployment was made by validation.

## Recorded results

- Windows Python 3.13.9; Codex SDK and bundled CLI 0.157.1; dependencies pinned in requirements files.
- 78 offline tests passed after the usability redesign. They cover the source→analysis→board→perspective→draft→preview→publish service flow with mocked posting; wrong workspace/private IDs; owner-only actions; explicit assessment disclosure; retention; changed previews (including source links); uncertain-delivery idempotency; Brave pagination and provider errors; persistent caps; secret allowlisting; disabled tool configuration; busy/cancel/timeout controls; schema and exact quotations; Slack limits/escaping and accessible fallback; actual Bolt dispatcher acknowledgement/authorization; disabled scheduling, timezone cadence, missed-run handling and non-AI preview preparation. A regression test prevents demo cached assessments being relabeled as live AI.
- Nine labeled synthetic evaluation cases pass fixture/schema/fidelity checks. No model precision/recall or internet recall is claimed from those tests.
- Live Slack authentication passed; Explore, Team board and Briefings Home payloads were all accepted after fixing duplicate action IDs. Twenty-one explicitly synthetic Block Kit payloads were also generated and validated under `docs/fixtures/`.
- One live Brave News request and one Web request retained 39 results. All were preserved, including duplicates; no AI label was used to hide results.
- A real retained source was saved into a workspace-shared board and a source-linked briefing preview. No teammate was impersonated. No channel post occurred.
- Managed ChatGPT authentication passed with SDK/CLI 0.157.1 and available model `gpt-6-luna`. The synthetic live isolation canary file was unchanged, its marker was not returned, and no unexpected tool activity was observed. This is bounded observed behavior, not proof against every attack. Three retained real-source records passed schema/evidence validation; an AI-assisted shared briefing preview was saved.
- The live model evaluation on nine synthetic cases produced 2 relevance errors out of 9 and 1 message-label error out of 9. All returned quotations matched supplied text. Case-level outputs were not retained by this validation runner; these aggregate results do not establish reliable semantic accuracy. Human review remains required.
- Runtime login no longer passes unsupported `--strict-config` to `codex login`; regression tests cover exit propagation. A cross-process lock prevents concurrent inference sessions.
- Initial build validation used 2 source requests and 4 AI jobs. After subsequent owner use and the redesign check, the ledger reports 19/30 source requests and 5/10 AI jobs. Redesign validation added exactly 2 source requests and 0 AI jobs; no ledger reset. See `data/redesign-validation.json` and the `status` command for later checkpoints.
- One local Socket Mode backend was connected and ready. No accessible browser surface existed for visual inspection; payload acceptance is not a visual result.

## Usability redesign results

- Added short setup with Save & collect, expandable options and hints, per-tab help, focused finding modals, readable provenance, Slack author mentions, and independent platform/assessment filters.
- Added persistent per-page saving/progress, throttled Home updates, clear partial/cancelled/interrupted states, stable paging, and exact displayed-page AI selection. Regression tests cover setup preservation, duplicate submissions, inline errors, fair source ordering, hostname spoofing, source failures/caps, cancellation, restart recovery, mentions, migration and Slack payload limits.
- Initial Brave Web checks returned 5 records per targeted query, but hostname verification found 0 Instagram matches and 1 LinkedIn match; 9 returned pages were off-target. All 10 remain retained with their actual website attribution. Corrected query construction now uses standalone site: tokens, explicit operators and disabled spellcheck, plus separate alternate-domain queries. Off-target results produce an explicit partial-results warning. The correction is offline-tested; a further live check requires two additional requests beyond this revision's approved allowance. All three redesigned Home payloads were accepted by Slack.
- No new AI jobs, channel posts, Slack scopes, direct platform connections or scheduled work were introduced. Existing searches retain their selections. Native visual inspection is still unavailable to the agent and must be performed by the owner.

## Pending gates

Dedicated runtime sign-in is complete. No purchase or API key was required.

The configured `#coverage-desk-demo` channel is verified public, internal and active, with bot membership after the owner invitation. No additional bot scopes or automatic join were added.

Publishing remains an owner UI action against the exact preview. A real teammate walkthrough and native Slack visual checks remain unverified. YouTube Data API is not configured and RSS is deferred; public YouTube links can now be discovered through Brave Web. Optional scheduling is implemented and offline-tested but disabled: it prepares private previews only, with no AI or automatic channel posting. Live scheduled operation is not claimed tested.

## Quality and maintenance

Generated model text is schema-validated and quote spans are checked against selected source text. AI points remain interpretations requiring human review. Untrusted source text cannot choose IDs, recipients, visibility or tools. Team notes are excluded from AI. Cache keys include source content, criteria revision, actor and analysis version, and caches stay private.

Update the SDK, CLI, schema and catalog together, rerun the isolation tests, and validate the actual authenticated model list before enabling a newer runtime. Runtime startup fails closed on unknown versions. Review source licensing, provider limits, expiry behavior and Slack manifest compatibility when dependencies change. Local records are not encrypted at rest; keep confidential material out of this public prototype.
