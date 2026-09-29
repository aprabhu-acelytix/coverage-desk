# Relevant Overview validation - 29 September 2026

The owner explicitly requested relevant findings be counted even without publication dates. This supersedes the previous confirmed-reporting-only default. Overview now defaults to all source types; Reporting is an optional filter. Unknown dates are labeled, never invented. Confirmed outside-period and unassessed findings remain excluded.

## Actual retained Chipotle evidence

Before: 1 confirmed reporting appearance at 1 outlet versus 38 Relevant findings. After: 38 relevant findings across 11 sources, including 2 verified publication dates and 36 unconfirmed dates. These are findings, not 38 independently verified news stories. Social, owned and unknown types retain their classifications. Chart sum, outlet sum and complete drill-down source IDs reconcile exactly. No new source requests or AI jobs were used; durable usage remained 680 source attempts and 135 AI attempts.

The owner Home update was accepted by Slack. The supplied dark desktop screenshots were reviewed; the updated chart has not been visually inspected in Slack. Owner should reopen Explore and check the 38/11 summary, date caveat, source bars, outlet navigation and unknown-date labels, including narrow/light views.

## Preservation and tests

Backup-first overview-v2 migrates old Reporting defaults to All source types once. It preserves sources, perspectives, drafts, frozen snapshots, privacy and usage history. Later explicit filter choices persist. New snapshots freeze the inclusion policy, date counts and caveats; existing snapshots retain original counts.

Offline regressions cover unknown dates across pages and runs, deduplication, chart remainder sums, outlet drill-down, snapshot evidence, corrections, migration idempotence and usage preservation. Full suite: 211 passed.

A small retrieval adjustment reserves the first available follow-up for a date-relaxed topical reporting query before optional social variations, within the same request limit. Offline regression passed; retrieval improvement has not been live measured in this change. No claims of broader source access are made.
