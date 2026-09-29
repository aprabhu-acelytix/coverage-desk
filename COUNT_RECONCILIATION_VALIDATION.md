# Overview and Relevant counts — 29 September 2026

The owner's existing Chipotle / Chili Lime Chips search reproduced the discrepancy
without running research: 37 relevant findings, one confirmed reporting article at
one outlet, 35 relevant findings with unconfirmed publication dates, and one dated
finding with unknown type. The counted reporting article was Delish; the dated
unknown-type item was a Copycat Spices recipe. Many other matches were social posts,
client pages or press releases. Relevance does not establish a verified publication
date or independent reporting.

Two regressions failed before the repair: the overview had no explicit count
reconciliation, and an outlet's Relevant drill-down included undated findings not
counted in its total. The repaired deterministic projection exposes the exclusive
breakdown. Overview labels its stricter totals; Articles labels the actual filtered
list and its counted subset. Outlet drill-down now matches the chart count, while
Needs attention and All results preserve other evidence. Dates, classification,
source priority, chart counts and existing saved/sharing snapshots are unchanged.

The real Chipotle projection and updated Home structures were checked locally:
37 = 1 counted + 35 date-unconfirmed + 1 other/unknown type. No source or model
calls were made for this repair. An owner research job was active during review;
it was not cancelled or restarted. No database migration is needed.

All 207 offline tests passed in 24.45 seconds, including the two new regressions.

Native Slack visual inspection remains unavailable. Payload/schema checks are
not visual validation. Owner walkthrough: Overview shows the confirmed count and
the reconciliation; Articles shows the broader filtered count; View articles under
the counted outlet shows exactly that outlet's included sources. Check light/dark
and narrow layouts. Publishing still requires the unchanged exact preview.
