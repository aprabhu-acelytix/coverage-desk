> Active revision: [COVERAGE_OVERVIEW.md](COVERAGE_OVERVIEW.md) supersedes article-list defaults and latest-run-only counting in this earlier research brief. Preserve its privacy, owner-only research, evidence, collaboration and publishing boundaries.

Owner revision - 29 September 2026: Overview defaults to all relevant findings across all source types, including unknown or conflicting publication dates. Label these as relevant findings, with verified-date and unconfirmed-date counts; do not imply all are reporting or verified within the period. Confirmed outside-period and non-relevant/unassessed findings remain excluded. Default Overview, chart, outlet drill-down and Relevant use the same deduplicated retained-scope projection before pagination. Reporting remains an optional filter. Sharing freezes date caveats and counts; existing snapshots remain unchanged. This supersedes conflicting confirmed-period-only or reporting-only default requirements below.


# Coverage Desk — research quality and Slack experience redesign

The bounded adaptive social search extension is specified in [SOCIAL_SEARCH.md](SOCIAL_SEARCH.md). It retains the existing provider, restrictions, assessment pipeline, filtering and source-priority rules.

## Objective

Repair the existing application in `aprabhu-acelytix/coverage-desk`, rather than replacing it with another scaffold. The reviewed baseline is `4eccc07deb09d78cbb797431fcb0f8bc42e4d579` on `main`. Reconcile against the actual checkout before editing; do not reset newer work to this baseline.

The owner wants a professional, simple, useful research product: open a saved monitor, refresh it once, see current relevant findings, inspect the evidence, save findings for colleagues, and prepare a reviewed briefing. The owner should not operate separate collection and five-item analysis stages.

This brief overrides earlier requirements for an all-records default view, optional page-by-page AI, and a universal ban on web tools **only for the new restricted research operation**. Preserve the no-tools analysis operation, ChatGPT-managed authentication, owner-only inference, privacy, retention, and explicit publishing confirmation. Update conflicting instructions in `AGENTS.md`, `BUILD_SPEC.md`, `CODEX_RUNTIME.md`, and user-facing documentation.

No general chatbot, new frontend framework, extra social integrations, new scheduler features, cloud deployment, or public multi-user subscription service is in scope.

## 1. Findings from the reviewed code

These are source-review findings, not a claim that the app was executed during this review.

| Location | Observed behavior | Required correction |
|---|---|---|
| `service.py: Desk.refresh/save_page` | Every returned item becomes a new finding object, including repeated retrievals. | Separate an article's identity from observations of that article; repeated refreshes should not produce repeated visible cards. |
| `ui.py: home/finding_row`; `discovery.py: finding_selection` | A canonical-URL `Counter` labels matching records, but each record is still rendered and paginated separately. | Deduplicate the visible projection before filtering totals and pagination, while preserving expandable provenance. |
| `slack_app.py: monitor_submit`; `service.py: monitor` | Editing saves a new revision but does not start a new collection. | Make the primary edit action explicitly Save & refresh, and clearly mark the old run while the new one runs. |
| `discovery.py: finding_selection` | Selection checks monitor ID, platform and client-relevance filter, but not current monitor revision, campaign relevance, or the monitor's date window. | Make the current view correspond to current scope and compatible analysis. Keep prior results separately accessible. |
| `sources.py: queries/retrieve` | Queries are quoted names/aliases plus an appended campaign string. Notes/handles are not used to plan discovery. General queries across platforms precede campaign queries. | Interpret intent before searching and reserve query budget for the actual campaign/focus, without losing broad or contrary coverage. |
| `slack_app.py: refresh/analyze_page`; `store.py: preferences` | Collection and analysis are separate actions, only the visible page is analyzed, and the default filter is `all`. | One bounded owner-initiated research workflow; relevant results by default, with review/all views available. |
| `runtime_worker.py: prepare/main` | Web search is disabled in config/features/catalog, and the event guard rejects tool items. | A verified, narrowly web-capable research operation is necessary; changing a prompt or one flag is insufficient. |
| `ui.py: home` | Repeated headings, instructions, help/settings, progress and separate actions precede results. Published briefings retain the View draft label. | Results-first composition and state-correct actions, not just shorter text. |
| `store.py: consume`; `README.md` | The persistent 30-source/10-AI validation allowance also limits ordinary app actions. | Preserve the allowance and usage history. Explain remaining capacity and request an explicit amendment if needed; never reset it to make the demo work. |

The existing tests protect useful security, disclosure, idempotency and evidence checks. Some tests intentionally preserve raw duplicate records; retain that audit capability and add tests for the **unique visible projection**. Do not confuse correct raw retention with good results presentation. `BUILD_NOTES.md` reports limited evaluation and acknowledges errors; it is not proof of reliable relevance ranking.

## 2. Repair identity, scope and relevance first

### Article identity and safe migration

- Distinguish a source/article from each retrieval observation. Use canonical URLs and verified provider identifiers where appropriate. Preserve original URLs, queries, endpoint/provider, retrieval times, run IDs, and source-text versions.
- Deduplicate before pagination, counts, analysis batches and board-save identity checks. A repeat refresh of unchanged articles must not inflate the number of unique findings or claim they are newly published.
- Do not merge distinct articles merely because headlines resemble each other. Distinguish the same URL found three times from three outlets reporting the same story. Related-story grouping is secondary to fixing exact duplicates.
- Keep repeated observations inspectable in a detail view. Avoid raw-JSON clutter.
- Make a consistent local database backup before migration. Preserve existing monitor IDs, saved findings, perspectives, reviews, drafts, visibility and published references. Keep an old-ID mapping if identities change. Invalidate affected preview tokens rather than publishing stale content. Migration must be safe to rerun and must not erase budgets or extend expired source rights.

### Current scope

- Persist an immutable monitor-scope snapshot or fingerprint on every run and analysis. Scope includes entity identity, aliases, identification notes/handles, campaign focus, requested messages, source selection, language/region, and effective date window.
- Bind relative windows to the run's actual clock/timezone; do not hard-code dates from the screenshots.
- A changed monitor must not silently reuse incompatible old classifications. Prevent in-flight old results from replacing the current run. Keep earlier results labeled as previous-scope history; existing shared snapshots are not retroactively rewritten.
- Filter current results against the requested time window using verified publication dates where available. Retrieval/indexing time is not publication time. Unknown or ambiguous dates go into an explicit review state, not silently inside the time window.
- In general coverage, client relevance is sufficient. With an explicit campaign focus, use client **and campaign** relevance for the default view. Missing a desired message must not exclude otherwise relevant campaign coverage. Critical or contradictory reporting is still relevant reporting.
- Do not invent an unstated editorial restriction: a general public-person monitor may legitimately include personal, professional and business coverage. Show a short editable interpretation of the request.
- Default to relevant current findings, newest first within that group. Offer Needs review and All collected with honest counts, explanatory labels and reversible filters. Pending/unassessed is not irrelevant. No relevant findings is a valid result; do not pad it with unrelated articles.

## 3. Add intent-aware research without weakening the analytical worker

### Preferred path: Codex live research

Use the existing official Codex SDK/App Server and the owner's managed ChatGPT sign-in. First prove a small compatibility slice against the actual pinned SDK/runtime: live web search, observable search/open events, structured final output, source provenance, cancellation and disallowed-tool rejection. Upgrade compatible runtime/dependency pins only if genuinely necessary, with regression coverage.

Create two explicit operations in the existing runtime architecture, not two services:

- **Research:** only supported public web search/open/find capabilities, with `web_search = "live"` and appropriately verified controls. Interpret the monitor, search, inspect sources, refine queries within limits, and return structured candidates and observed source references.
- **Analysis/briefing:** retain the no-tools behavior; classify only eligible supplied evidence and produce source-linked drafts.

Account for `prepare()`, the generated model catalog, effective-config checks, prompts, item allowlists, process isolation, input/output validation and runtime tests together. Do not merely remove the event guard or grant full access. Do not allow concurrent operations to rewrite a shared config into the wrong role. Keep the existing managed credential home, without reading/copying tokens or modifying the developer's global configuration.

The research runtime must not gain shell/editing tools, arbitrary MCP/plugins, Slack tools, local secret access, browser-profile access, private conversations, or permission to publish. Search queries should contain only the intended public research criteria, not team notes or credentials. Treat retrieved pages as untrusted content.

### Evidence is the provider-selection gate

The App Server's documented `webSearch` item records a search or open action; do not assume it exposes every raw search hit or the full page text. An attempted open is not proof of successful reading. A model-authored URL, quotation or date is not independently verified evidence merely because it appears in valid JSON.

Build a source registry from tool-observed data. Require an inspectable URL and provenance for every surfaced item. Validate supporting quotes against source text the application actually obtained, not another quote generated by the same model. When available data supports only a title/snippet, say so and limit the analysis accordingly. Unverified metadata or quotations must be labeled and excluded from evidence-backed claims.

If native search does not expose sufficient evidence, choose the smallest viable solution: safely verify permitted public source text through application code, or use a Codex-generated query plan with the existing Brave adapter. Any application-side URL retrieval needs HTTP(S)-only validation, private/loopback/link-local and redirect protection, time/size limits, and no paywall or login bypass. Do not expand arbitrary manual-URL fetching by accident.

Prefer native search if its capability slice and the small quality comparison support it. Otherwise keep an explicitly documented AI-planned Brave path. Do not silently switch providers mid-run or create a complicated default multi-provider orchestration system. Record which path actually ran.

### Research behavior

- Use all relevant user criteria, not just a quoted entity name. Resolve obvious entity ambiguity from supplied notes/handles; ask only when ambiguity materially changes the search.
- Include broad mentions alongside campaign searches and semantically varied queries. Desired messages guide analysis, not an exclusive search filter that hides their absence or contradiction.
- Allocate limited searches to the user's core focus before spending the entire budget on optional platform breadth. Record what was and was not attempted.
- Separate reported articles, owned/official statements, social posts, evergreen profiles and commerce pages when supported. Do not label every indexed social URL a news article or imply a direct platform integration.
- Preserve source freshness, attributed authors/outlets where known, text-access level, relevance explanation and exact message evidence. No fabricated reach, confidence percentages, or completeness claims.
- Show **all evidence collected by this run**, not all results the search engine may have considered internally.

## 4. One useful action and a compact Slack experience

### Workflow

The primary owner action is **Find coverage** for a new monitor and **Refresh** for an existing one. Saving the initial monitor or choosing Save & refresh after an edit starts one authorized job: understand scope → discover → deduplicate → assess eligible unique findings → show results. AI work is not tied to the current five-row page.

Reuse valid unchanged evidence/analysis where permission allows. Cache by source content/version, scope, model/analysis version and authorization context, rather than newly allocated duplicate record IDs. Batch within real runtime limits. Stop honestly at caps; show pending counts and an owner continuation action rather than demanding manual analysis of each page.

Loading Home, filtering, pagination and teammate contributions must not trigger inference or web research. Stream useful progress, retain partial evidence, and do not report the entire job Ready if only collection completed. A failure in analysis leaves collected sources available for inspection.

### Explore

- Keep Explore / Team board / Briefings, with an unambiguous active destination.
- Remove the repeated Coverage Desk heading beneath Slack's own app header. Put the monitor selector, short scope/timeframe, primary Refresh action and compact filters near the top.
- Move new/edit search, help, settings, source diagnostics and manual contribution into sensible secondary controls or modals. Do not conceal active filters or errors that materially affect interpretation.
- Replace persistent completed-job banners and repetitive collection counters with one useful status line. Diagnostics belong behind Search details.
- Render compact rows: headline, outlet/platform and date, one short reason it matches, and a clear inspect/save interaction. Show the full available title and evidence in the detail view; do not alter quoted text for stylistic reasons.
- At the desktop size shown in the owner's screenshots, the first finding should be visible without scrolling, with useful results occupying much of the initial viewport. Validate actual rendering, not just block counts.
- Empty, loading, partial, outdated-scope, no-relevant-results, signed-out and usage-limit states should explain the next action plainly.

### Team board and Briefings

Keep the working collaboration implementation. Make saved findings easy to recognize, attribute perspectives, show review state, and expose the difference between private and workspace-shared material. No private criteria leakage or duplicate board cards through alternate finding IDs. Preserve intentional disclosure before sharing.

Briefing labels and actions must match state: View briefing for published content, Edit/Preview & publish for drafts. Give drafts distinguishable, editable titles without leaking private monitor configuration. Fix singular/plural copy. Preserve exact-preview, revision/expiry checks, destination restrictions and uncertain-delivery handling. Teammates may edit authorized drafts without invoking the owner's AI worker.

Use native Slack components, restrained hierarchy and concise editorial writing. Do not add decorative banners, artificial scores, emoji walls, a wall of buttons, or unsupported CSS/charts. The benefit over a one-off chat is remembered scope, reliable new/seen coverage, inspectable evidence and shared review—not another summary screen.

## 5. Validation and acceptance

Before repairs, write failing regression tests for the actual defects. Then retain and run the existing focused suite plus the new tests.

Required cases:

1. Three observations of the same canonical article produce one visible card and one analysis target, with all three observations inspectable.
2. Unchanged repeat refreshes do not inflate unique counts, create duplicate board cards, or count an old article as newly published.
3. Different articles with similar headlines remain distinct. Tracking-parameter normalization does not remove meaningful identity parameters.
4. Editing the entity, campaign, messages, date window or sources cannot surface stale classifications as current. Old in-flight jobs cannot overwrite a newer scope; shared snapshots and notes survive.
5. Campaign-irrelevant coverage is not in the focused default list; relevant critical coverage and relevant coverage lacking the desired message remain available. Unknown dates and unassessed items have correct states.
6. Relevant, Needs review and All counts, unique pagination, continuation and cache invalidation agree with the data.
7. One explicit owner refresh reaches analyzed results without a second page-analysis click. Browse/filter actions and teammates do not initiate AI.
8. The research role can use only permitted web capabilities; the analytical role remains tool-free. Invalid source IDs/quotes, injected instructions, secret inheritance, unintended tool events, timeouts and cancellations fail safely.
9. Migration preserves workspace/private isolation, board references, perspectives, edited drafts, ledger usage and expiry.
10. Published/draft labels, long headlines, narrow layout, empty/partial states, Slack payload limits, escaping and duplicate-event handling are covered.

Run a small before/after research comparison with consistent time windows and public scopes: a general person monitor, a campaign-focused variant, and a brand with entity ambiguity. Use the owner's actual public test monitors when suitable. Record queries/path, unique findings, source access, dates, elapsed time, relevance judgments and examples of errors. Assess top-result relevance against predefined human-readable criteria; do not call the model's self-labels ground truth. Retain permitted case-level evidence so the comparison is reviewable. Do not claim internet recall or native-search superiority from a tiny demonstration.

Use current remaining live authorization. The existing ledger is shared across builds and real owner actions: inspect it, do not reset it or create another database to evade its limits. Count research turns and observable tool actions honestly; a visible search event is not proof of the provider's internal request count. If capacity is insufficient, state the exact additional bounded allowance needed once and continue offline/UI repairs. No purchases, credit resets, plan changes, or paid API fallback.

Validate the real Slack interface when a permitted inspection surface is available. Capture actual before/after views of Explore, finding details, Team board and Briefings and iterate on them. Fixture JSON and Slack accepting payloads are not visual inspection. If no such surface is accessible, identify the exact owner visual checks rather than claim them complete.

## 6. Handoff

Keep the existing Python/Bolt/Socket Mode/SQLite architecture. Reuse working source/evidence, privacy, collaboration and process-management code. No repository rewrite or unrelated features.

Deliver repaired code, safe migration, updated instructions and regression tests; a concise research comparison; actual validation outcomes; and a three-minute walkthrough. Restart only this project's backend, preserve credentials/configuration, and leave one ready local instance. No unapproved channel posts or deployment. Commit coherent changes locally; do not publish a PR or push without an existing explicit instruction to do so.

Do not stop after planning, renaming buttons, enabling web search, or getting tests green. Demonstrate the changed owner workflow through finding → shared board → perspective → briefing preview, distinguishing live, simulated, visually inspected and still-unverified steps. Report remaining blockers without inventing successful research, test or collaboration evidence.

## Primary implementation references

Repository paths above refer to the pinned reviewed commit. Verify current official interfaces before changing runtime controls:

- https://github.com/aprabhu-acelytix/coverage-desk/tree/4eccc07deb09d78cbb797431fcb0f8bc42e4d579
- https://developers.openai.com/codex/app-server/
- https://developers.openai.com/codex/config-basic/
- https://developers.openai.com/codex/sdk/
- https://docs.slack.dev/surfaces/app-home/
- https://docs.slack.dev/reference/block-kit/blocks/

## Complete assessment and simpler browsing (28 September 2026)

The latest owner request supersedes the two-batch/five-page collection limits and older Unassessed/Outside-period filter controls. One Refresh reads available publisher evidence and assesses the full finite collected scope using bounded, cancellable jobs. Access restrictions remain enforced; unavailable full pages may be assessed only from retained search evidence, clearly labeled. Normal browsing excludes confirmed outside-period findings, with publisher calendar-day flexibility but no invented dates. Use Relevant, Needs attention and All results. Corrections change one detail at a time. Native Slack Home has no documented custom tabs: use a compact active-view header and one view selector, not a row of navigation buttons.
