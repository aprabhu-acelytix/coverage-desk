Historical overview implementation report. The subsequent completeness repair and current validation are in RESEARCH_COMPLETENESS_VALIDATION.md; the two-batch behavior below is superseded.

# Coverage Overview validation ? 28 September 2026

Implemented in the existing Python/Bolt/Socket Mode/SQLite application. No provider replacement, new platform, public chart hosting, deployment, API-key inference or automatic channel posting.

## Offline

**176 tests passed** (`.venv\Scripts\python -m pytest -q`, 19.42 seconds). Tests block network connections and DNS and never load .env. New regression coverage includes all-pages/all-runs aggregation, repeated URL observations, retained results after empty/failed refreshes, date windows and equivalent timezone timestamps, scope edits, independent relevance/date/type/assessment states, critical reporting and absent messages, exact-host aliases (including separate www hosts), syndicated appearances, correction evidence, retention/storage revocation, private aggregates, frozen snapshot/source consistency, all-outlet/source pagination, eight-plus-remainder charts, fallback on native chart rejection, disclosure/confirmation dispatch, separate no-tools type assessment, public-input allowlists and automatic overview generation within two bounded assessment slots. Existing collaboration, deletion, authentication/isolation and publishing tests remain green.

Mocked publishing tests are not evidence of a real channel post or teammate interaction.

## Live before and after

Client: **Stephen Curry**. Campaign: **Li-Ning "Everything is possible"**. Period: past month, effective UTC window on the final assessment **2026-08-28 15:33 to 2026-09-28 15:33**, end exclusive. Requested sources remain News, Web, Instagram, X and LinkedIn.

Before this revision, four retained articles already had relevant subject/campaign assessments and publisher-verified September dates. They did not have content-type evidence or an outlet overview. The new strict projection initially counted **0 reporting articles**, keeping all four as Unknown type. A real Refresh retained further observations without erasing the earlier coverage. It exposed an invalid strict output schema, then a separate assessment-quality problem: the larger message batch under-classified reporting. Repairs made the new schema required while preserving legacy data, prioritized current verified articles, included bounded public publisher metadata, and added a focused content-type-only operation in the existing two-slot workflow. No manual correction or fixture was used to force these four into the final count.

Final retained projection: **204 unique articles**: 4 confirmed-period relevant; 20 relevant/date-unconfirmed; 141 unassessed; 8 uncertain relevance; 13 outside the period; 18 not relevant. These independent states sum to 204. They do not all qualify as reporting. The default overview contains **4 reporting article appearances at 2 outlets**, marked **Partial collection**. The new retrieval did not establish additional qualifying in-period reporting beyond the four previously date-verified URLs. This is a counting/classification improvement, not a claim of improved search recall or complete coverage.

| Outlet | Count | Reporting and date evidence reviewed |
| --- | ---: | --- |
| PEL Sports | 3 | Distinct source URLs below; third-person reporting about Curry's partnership/tour/shoes, publisher metadata naming PEL Sports and author Andre Whitlock, September publication timestamps. |
| NBC Sports Bay Area & California | 1 | Retained journalist byline (Kevin Topley), campaign-related article headline, publisher NewsArticle metadata and September publication timestamp. |

Source reconciliation (each counts once; all timestamps UTC):

1. [PEL Sports ? signature shoe expected in 2027](https://www.pelsports.com/stephen-curry-li-ning-signature-shoe-2027/): **2026-09-19 11:21:49**. Source ID `2d750f81c0d44a529c257476188982b8`.
2. [NBC Sports Bay Area ? sneaker release and Warriors future](https://www.nbcsportsbayarea.com/nba/golden-state-warriors/steph-curry-sneaker-release-future-with-warriors/1964197/): **2026-09-18 21:44:46**. Source ID `a1f96e76ae26462ba90e992e33abc13e`.
3. [PEL Sports ? first signature shoe and interim footwear](https://www.pelsports.com/curry-first-li-ning-signature-shoe/): **2026-09-16 03:23:25**. Source ID `8a2602ba276749c3b9c3dce46553f2cb`.
4. [PEL Sports ? five tour footwear editions](https://www.pelsports.com/curry-moments-li-ning-five-pes/): **2026-09-15 14:43:19**. Source ID `0b133765bcfe41e6a731cd9ef3247023`.

This reconciliation reviews the retained excerpts, publication metadata, bylines, URL uniqueness and campaign connection; it does not claim full-text fact checking or independently verified editorial ownership. Three PEL appearances concern related developments, so four appearances must not be described as four independent stories. No redistribution label was applied without affirmative evidence. Date-unconfirmed social and other sources remain accessible. Exact quote matching verifies words, not every AI interpretation; evidence correction remains available.

The final type-only operation preserved existing message assessments. Historical message judgments are not newly certified by this overview test; source-linked evidence remains reviewable.

## Slack and private preview

Official native [data visualization](https://docs.slack.dev/reference/block-kit/blocks/data-visualization-block/), [data table](https://docs.slack.dev/reference/block-kit/blocks/data-table-block/) and [table](https://docs.slack.dev/reference/block-kit/blocks/table-block/) schemas were inspected. Live synthetic owner Home probes accepted all three; the table probe initially rejected numeric cells missing display text and passed after that correction. The real four-article Home chart and the actual Explore, Team board and Briefings payloads were also accepted.

A private **Stephen Curry | Coverage found** draft was prepared through the real snapshot/preview services. The frozen source ID set, outlet counts and chart values reconcile exactly: 3 + 1 = 4. It includes period, counts, public source excerpts and caveats; no monitor notes, raw queries or desired-message criteria. This was programmatic implementation validation, **not an owner click on Slack disclosure/confirmation controls**. The configured public internal channel has the bot invited. **No message was posted.** Open Preview & share overview from Explore for the complete disclosure flow, or inspect the private draft in Briefings and open a fresh exact preview; publishing additionally shares the frozen copy to the workspace and always requires the owner's final confirmation.

CUA returned no available apps or browser tabs. Therefore real **light/dark/narrow layout, zero-baseline rendering, long-label handling and modal spacing are unverified**. Slack's documented native chart schema has no explicit axis-minimum control. The code supplies nonnegative integer bars, but zero-baseline rendering must be checked in Slack; there is no fabricated renderer or hidden hosted chart. Use the full-name outlet controls rather than assuming bars are clickable or horizontal. An unsupported chart falls back to exact outlet counts.

## Migration and resource accounting

Backup-first `overview-v1` migration applied once. Actual backup `data/backups/overview-v1-1790608741.sqlite3` preserves original expiries. Both pre-existing saved board/briefing objects were compared against it and remained byte-for-byte unchanged, including owner/visibility/data/created/expiry. Findings/board IDs and usage history were not reset. Overview backups and task-owned public validation exports participate in retention cleanup.

Durable usage changed **112 ? 146 source requests** and **30 ? 38 AI jobs**: this revision used **34 source requests and 8 AI jobs**, including the failed schema attempt, targeted reassessments and one direct single-article diagnostic. The earlier cached diagnostic consumed no AI job. These are actual ledger deltas, not a reset or fresh allowance. The owner previously removed lifetime app caps; historical cap values remain 50 sources / 10 AI in SQLite and are explicitly not active enforcement. Per-search and provider/subscription limits remain. Approval review initially applied the old ten-job cap, then accepted the pre-existing user authorization evidence; there is no remaining approval block.

Local task-owned reports are `data/research-comparison-overview-live1.json` through `live5.json`, plus `research-comparison-overview-snapshot.json`; they retain the actual failed and successful attempts and are excluded from Git. They expire under the existing cleanup policy. No credential values, OAuth tokens or development-session configuration were copied into the reports.

Tested environment: **Python 3.13.9; openai-codex and pinned Codex CLI 0.157.1; Slack Bolt 1.30.0; Slack SDK 3.44.1; Pydantic 2.13.5; pytest 9.1.1**. Managed ChatGPT model remains **gpt-6-luna**. The official SDK/App Server and existing restricted runtime home are unchanged.

## Walkthrough and remaining checks

See [DEMO.md](DEMO.md) for client ? outlet overview ? articles ? evidence ? sharing preview. Required owner checks: actual Slack light/dark/narrow views, bar zero baseline, full-name correspondence, outlet/source navigation, disclosure and final exact preview. Actual channel posting and real teammate interactions were deliberately not performed. No sign-in, permission or provider blocker remains for local use.

Use `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/backend.ps1 status` and replace status with start, stop or restart as needed. The process manager and local port guard prevent duplicate backends. Keep the Windows host running; this is local Socket Mode, not persistent cloud hosting.
