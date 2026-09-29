# Coverage Overview: active product and implementation guidance

Public social discovery now follows [SOCIAL_SEARCH.md](SOCIAL_SEARCH.md). It preserves this projection and ranking: filters never undo outlet priority or discard lower-priority findings. Social search excerpts do not enter reporting totals merely because they were discovered.

This revision supersedes article-list-first and latest-run-only instructions in earlier briefs. Preserve Python/Bolt/Socket Mode/SQLite, the existing providers, managed ChatGPT authentication, private/shared collaboration and exact publishing confirmation. No new platforms, scheduler features, chat, dashboard or hosting.

## Owner workflow

Explore defaults to Overview. Select the client/campaign search, edit its period/scope if needed, then Refresh. One action performs the existing bounded planning, discovery, assessment and date checks, and returns to the overview automatically. The order is controls, Coverage found totals and freshness, one native bar chart, then the outlet breakdown. Completed-job detail and diagnostics stay secondary.

The chart contains up to eight outlets in descending article count, ties by case-folded name then exact outlet key, followed by a labeled combined remainder. Indexed short chart labels map to full names below. Every outlet is accessible through the paginated breakdown. Bars are not assumed clickable or horizontal; use View articles. Articles has dates, source links, Inspect, Save, classification review and Back/Clear outlet controls. Browsing and filtering are read-only and never invoke AI. Source & history filters keeps previous scopes and selected discovery sources inspectable.

## One projection, explicit evidence

`overview.project_articles` authorizes access, chooses retained observations compatible with the monitor scope/revision, groups canonical article identities before pagination, and selects the newest compatible assessment. Unassessed repeat observations do not erase an earlier assessment; a newer negative assessment takes precedence. All retrieval observations remain retained. Empty or failed runs do not erase compatible coverage. Edits to criteria isolate older scopes. Dates are rechecked against the selected effective UTC window; the end is exclusive. Opening Home advances a relative window; paging preserves its timestamp.

`coverage_overview` feeds totals, chart, outlet drill-down and frozen snapshots. No model computes counts. Report unique qualifying URL/article appearances at each outlet, not independent stories, reach, exposure, or a complete census. Syndicated copies at distinct outlets remain appearances. Show redistribution only with an explicit retained quotation or an evidence-backed owner correction; similar wording and shared ownership are insufficient.

Keep these facets independent:

- Relevance to the client and optional campaign; critical reporting and absent desired messages do not imply irrelevance.
- Publication certainty: timezone-aware publisher metadata or an attributed owner correction. Never use collection time, a URL date, or a provider page-modification date as publication.
- Content type: reporting (default), client-owned announcements, press-release distribution, sponsored, social, unknown. A news-search hit is not proof of reporting.
- Assessment status: unassessed, AI assessed, or owner-reviewed relevance. Relevant/date-unconfirmed is separate from unassessed and neither enters confirmed-period counts.

Native tool-observed source evidence and existing Brave restrictions remain unchanged. Legacy assessments without type evidence stay Unknown type. Bounded public metadata may supply publisher, byline and page-type evidence; these fields never prove campaign-message claims or editorial independence. Assessment batches reserve output space for each tracked message. Bounded publisher checks run before assessment for the full eligible finite set. Relevance assessment covers all unique collected findings in bounded batches; focused content-type assessment follows without starving relevance. Finish research resumes incomplete work without retrying unchanged denied pages. Publisher-declared same-host canonical URLs and tracking parameters deduplicate observations without rewriting saved source IDs. Publisher date-only metadata retains calendar-day precision; retrieval time is never publication evidence. Invalid type quotations degrade to unknown without discarding independently valid message evidence.

Use observed publisher metadata or an exact publisher name in retained source text; otherwise display the exact hostname. Do not collapse subdomains, even www, or common-owner publications. An owner can create reviewable exact-host aliases with a reason. Classification corrections record actor, source ID, timestamp, scope and evidence; past review records are preserved until retention expiry. Corrected outlet/type/relevance/date values feed the same projection.

## Slack and sharing

Official schemas verified: [data visualization](https://docs.slack.dev/reference/block-kit/blocks/data-visualization-block/), [data table](https://docs.slack.dev/reference/block-kit/blocks/data-table-block/), and [table](https://docs.slack.dev/reference/block-kit/blocks/table-block/). Live owner Home accepted all three. The application uses a single native bar series with nonnegative integer values and text totals/outlet controls. It does not rely on table blocks for essential navigation. If capability is unavailable/unverified, show the exact outlet breakdown instead. No images are hosted publicly.

The documented chart schema does not expose an explicit axis-minimum or orientation control. Zero-baseline rendering, light/dark contrast, label truncation and narrow layout require inspection in the actual Slack client; payload acceptance is not visual validation. Do not claim those checks passed without seeing them.

Preview & share overview explicitly discloses private client/campaign information, aggregates, outlet names, source links and excerpts. Monitor notes, raw queries and desired message criteria are excluded. Create a private immutable briefing snapshot containing the effective period, category, exact counts, outlet identities, source IDs, retained source text, classification evidence, caveats and retention deadlines. The owner can review the complete frozen source list and outlet breakdown before confirming the exact channel preview. The snapshot is read-only; ordinary editorial briefings remain editable.

Publishing rechecks owner identity, retention, storage permission, post-snapshot corrections, channel membership/internal-public status, preview expiry, digest, revision and single use. Only successful exact confirmation publishes and exposes the frozen snapshot to the workspace. Original private findings remain private. An uncertain send is never retried automatically. Published Slack messages are not silently deleted by local retention; delete saved snapshots through the existing confirmed Briefings action.

## Migration, limits and verification

`Store.migrate_overview` first ensures the earlier research migration, then takes a consistent SQLite backup before an idempotent overview preference migration. It changes no finding IDs, board references, drafts, perspectives, privacy, expiry or usage totals. Existing backup/source retention cleanup also covers overview backups and task-owned validation exports. Never reset durable attempts/usage or restore expired records from a backup without applying retention.

The owner previously removed lifetime app caps. Historical caps remain stored as history, with all attempts counted across restarts. Per-search/task/batch/input/output/time/concurrency limits and provider/subscription restrictions remain. No source/model work occurs in offline tests, and no tests load .env.

Run `.venv\Scripts\python -m pytest -q`. Explicit live helpers are `python -m scripts.probe_overview_blocks` (temporary synthetic owner Home capability probe) and `python -m scripts.validate_overview --client "Existing public client" --operation report --attempt unique-name`. Changing operation to refresh/assess consumes authorized live resources and records its attempt durably. They never post to a channel. See OVERVIEW_VALIDATION.md for actual results and remaining visual checks.

## Outlet context and owner review (29 September 2026)

This revision overrides newest-only Explore ordering and the standalone Correct row control. Finding rows contain Inspect, Save and, for owner-reviewable matches not already relevant, Mark relevant. Move detailed corrections into Inspect > Edit finding. Mark relevant writes an attributed human relevance correction, without AI, changing dates or types, overwriting message evidence, or claiming full-page access. Relevant findings with unconfirmed dates remain outside dated totals and are labeled accordingly; Needs attention may therefore overlap Relevant. Only the owner can change these research classifications, and only for the current scope/revision.

Inspect > Source details leads with About this outlet: description, significance/topic focus, editorial signals, linked sources, profile review date and list-priority rationale. The initial public catalog in coverage_desk/outlet_profiles.json covers ten outlets. It is a reviewed reference set, not a universal reputation database. Publisher statements of editorial policy and identifiable newsrooms support prioritization, not a certified reliability score or a guarantee that an article is accurate. Unknown sites are explicitly not reviewed, never automatically called disreputable. No audience/reach numbers are invented. Updating the catalog requires reviewing its references and restarting the backend; browsing never fetches profiles or invokes AI.

Apply the same deterministic ordering to the full eligible projection before pagination: owner Higher priority; reporting from an outlet with a reviewed profile; Standard priority; owner Lower priority. Within each group retain publication/recency/identity ordering. Only explicitly listed hostnames receive a profile: no suffix matching, common-owner inheritance, or automatic trust for an alias. Profiles do not merge outlet identities. Sponsored, client-owned, press-release, social and unknown-type items receive no automatic established-reporting boost. Sorting never changes inclusion, deduplication, relevance, date certainty, article counts or the count-descending outlet chart.

Inspect > Source details > Outlet priority lets the owner set Higher, Standard, Lower or Use default with a short reason. It applies to that exact host in the owner's Explore lists. Overrides are private, attributed and retained no longer than their source evidence; they are evaluated at the pagination snapshot time. Private priority notes are excluded from saved board snapshots and briefings. Existing SQLite objects support the new record kind without rewriting existing findings or performing a schema migration. Existing expiry cleanup applies. See OUTLET_UX_VALIDATION.md for evidence and remaining visual checks.
