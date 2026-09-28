# General search fixes — 28 September 2026

This revision supersedes the earlier default-provider recommendation in RESEARCH_VALIDATION.md. The implementation uses no company-specific retrieval rules. Existing code, source observations, board references, perspectives, drafts, privacy, and usage history remain intact.

## Behavior

- Codex web research is the default for new searches. The owner's requested switch applies to existing searches once, without changing their criteria revisions or rewriting earlier runs. An explicit later Brave preference is respected.
- One Refresh performs tool-free planning, restricted native discovery, deduplication, and two bounded tool-free assessment batches. Discovery receives no desired-message criteria. Only SDK-observed URLs, titles and excerpts enter the source registry; a generated citation or attempted page open cannot create evidence.
- Campaign/product focus describes a topic. A slogan is not required in every article. Every selected category receives a query, with subject-wide and topical alternatives. For short date windows, a calendar-word variant supplements date operators, which native search sometimes ignores. All queries and actual target attempts are inspectable.
- Assessment interleaves provider rankings across queries. A prolific query cannot consume the entire batch. Individual invalid quotations leave their source in review without discarding valid assessments. Exact quotes may come from retained headlines or excerpts; the details view identifies headline quotes. Quotation matching checks words, not the correctness of an AI interpretation.
- Unrelated undated results are excluded from Relevant rather than mislabeled as a date-review task. Message absence and critical reporting do not exclude topical coverage. Up to five promising public publication dates are checked per action; large pages can supply metadata in their bounded prefix. Missing dates and denied access remain reviewable.
- All collected remains available. Filters → Earlier searches also exposes earlier runs of the same scope, including evidence retained before an empty or failed refresh. Check pending works across the collection, independent of the visible page, and can continue date verification.

Native discovery uses the official openai-codex/App Server 0.157.1 and managed ChatGPT authentication. Planning, assessment and briefings have no tools. The research role has only hosted public web tools, an isolated runtime home/environment, filesystem denial, and no shell, editing, Slack, MCP, plugins or development tools. It never switches to Brave mid-run. Brave remains an explicit alternative using the expanded query plan.

## Offline validation

139 tests passed with networking and DNS blocked and without loading `.env`. Regressions cover multiple company/person/topic combinations, all selected targets, temporal query hints, query-ranking fairness, irrelevant undated results, critical coverage, independent invalid-quote handling, retained headline evidence, oversized-page metadata, earlier-run inspection, owner-only access, one-time preference migration and unchanged usage history. Existing collaboration, privacy, publishing confirmation, cancellation and isolation tests continue to pass.

## Live evidence

All checks used the real configured owner runtime and durable usage ledger. Public-source evidence and per-run audit records are retained in `data/research-comparison-general-v2-*.json` under the existing expiry policy. These are live results, not fixtures or model self-scores.

The original Curry monitor made two Brave requests, left Instagram/X/LinkedIn unsearched, and returned ten generic articles. Nine assessments were campaign-irrelevant, but the old date-first filter displayed all ten as Needs review. The corrected filter alone distinguishes those exclusions; it does not manufacture new coverage.

Early native iterations were not successful: the first retained 90 unique findings but rejected the entire assessment batch after one missing quotation; the next assessed 26 of 79 unique findings but still had zero verified current matches because old deal announcements dominated the queries. Those failures were retained and prompted the general fixes above.

The repaired full campaign Refresh retained 154 observations / 103 unique findings, validated 17 assessments, and displayed two current relevant articles. It attempted all five selected categories. Twelve LinkedIn results were returned; Instagram and X returned no indexed matches. This is public index coverage, not direct social-platform access or evidence that no posts exist.

Two inspectable current examples are PEL Sports' [signature-shoe report](https://www.pelsports.com/stephen-curry-li-ning-signature-shoe-2027/) (publisher metadata: 19 September) and [China-tour report](https://www.pelsports.com/curry-first-li-ning-signature-shoe/) (16 September). Their observed titles/excerpts connect Curry, Li-Ning and shoes. The slogan is absent from these excerpts, which does not erase their topical relevance. Some message-level interpretations still need human review: an exact but truncated quotation need not prove a broader message. The NBA and LA Times original deal stories were verified as June publications and correctly excluded from the past-month view.

The calendar-word search also retrieved NBC Sports' recent sneaker-release report and other recent product coverage. Retrieval alone does not count as a verified current assessment. Pending and unknown-date findings remain visible.

The separate general-brand check created a public Patagonia validation search (clothing company, past month, five selected categories, with “Repair and reuse clothing” as a message criterion). It retained 88 observations / 71 unique findings and validated 30 assessments. One verified current finding was Patagonia's [9 September PSI Vest announcement](https://www.patagoniaworks.com/press/2026/9/9/patagonia-introduces-the-next-generation-psi-vest-advancing-big-wave-surfing-safety). It remained relevant even though its excerpt did not discuss repair/reuse. This is an attributed company announcement, not independent earned-media coverage. The remaining view contained 69 review items and one exclusion; 41 unique findings had not yet been assessed. All five categories were attempted; LinkedIn returned 12 indexed results, while Instagram and X returned none. This case validates general-brand disambiguation and message absence without tailoring the search to the Curry example.

One explicit campaign **Check pending** action then validated 15 additional assessments without repeating discovery. The current campaign view contains **4 relevant / 88 review / 103 total**, with 32 assessments validated and 71 not yet assessed. Newly verified current examples are [NBC Sports' sneaker-release report](https://www.nbcsportsbayarea.com/nba/golden-state-warriors/steph-curry-sneaker-release-future-with-warriors/1964197/) (18 September, explicit publisher metadata) and [PEL Sports' China-tour product roundup](https://www.pelsports.com/curry-moments-li-ning-five-pes/) (15 September). These retained excerpts concern the named person, partner and products; they do not establish that every requested message appears in the full articles. Review counts include pending assessment and unverifiable dates, not only ambiguous topical relevance.

| Live action | Unique sources | Validated assessments | Verified current relevant | Elapsed |
| --- | ---: | ---: | ---: | ---: |
| Campaign iteration 1 (failed batch validation) | 90 | 0 | 0 | 140.9 s |
| Campaign iteration 2 (old announcements dominated) | 79 | 26 | 0 | 228.7 s |
| Campaign repaired Refresh | 103 | 17 | 2 | 176.2 s |
| General Patagonia Refresh | 71 | 30 | 1 | 150.6 s |
| Campaign Check pending (same collection) | 103 | 32 cumulative | 4 | 74.9 s |

The ledger increased from **60 source slots / 13 AI jobs** to **112 source slots / 29 AI jobs** across these checks, including failed iterations and conservative native reservations. No usage or claims were reset. The live role used the existing managed-auth model `gpt-6-luna`; dependencies were unchanged.

## Operational limits and walkthrough

Lifetime app source/AI caps remain removed as explicitly requested; historical caps and all usage remain recorded. Each Refresh remains bounded: at most 12 search tasks, one conservative cancellation-boundary source reservation for native discovery, two assessment batches (at most 15 sources each), and up to five bounded metadata checks. Continuation is another explicit owner action. Provider/subscription limits still apply. No automatic retries, channel posts, purchases, API-key inference fallback, scheduled AI or deployment were used.

No Slack/browser surface was available for visual inspection (`apps: []`, `browsers: []`). Offline Slack dispatch/rendering tests and API payload acceptance are not visual evidence. In Slack, check Explore's first results, Filters → Earlier searches, Search details by platform, headline/excerpt quotes, and Check pending. Existing Team board and exact Preview & publish confirmation remain unchanged. Real teammate behavior and desktop/narrow/light/dark visual checks remain owner walkthrough tasks.

Backend commands: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/backend.ps1 status` (replace `status` with `start`, `stop`, or `restart`). The single local Socket Mode backend requires its host/session to remain running.

Handoff check: managed runtime **Ready**, application mode **live**, backend PID **8996**, Socket Mode readiness **True**, and updated owner App Home accepted. The validated campaign is selected in Explore. This confirms connection and payload delivery, not visual rendering.
