# Research completeness and simpler navigation - 28 September 2026

## Reproduced problem and repair

The owner's existing Meta / Muse AI Agent / past-week search had 126 observations, 97 unique findings, 30 assessed and 67 unassessed. The overview counted one confirmed-period reporting article. The old Refresh stopped after two assessment batches and checked only five publisher pages.

Refresh now checks the full finite eligible public-page set, then assesses every unique collected finding in bounded, cancellable batches independently of pagination. Content-type follow-up happens after relevance assessment. Payload sizing includes criteria, schema, URLs and publisher metadata. Per-job time/input/output/item bounds and durable usage accounting remain; no lifetime app cap is reinstated. No automatic retry loop is added. An interrupted operation retains completed work and offers Finish research.

Public checks retain short excerpts (up to 1,200 added characters), explicit dates, provenance and access outcomes. They use public-address validation, pinned connections, redirect/read/time limits and at most three concurrent requests. Known denials are not repeatedly retried. Social findings are assessed from retained public search evidence, without opening authenticated platform content. Paywall-marked article bodies are not used; public description metadata may be used. Date-only publisher metadata retains day precision and cannot become an invented publication instant.

Tracking parameters and publisher-declared same-host canonical article URLs deduplicate the projection without rewriting original finding IDs, observations or saved board references. about.fb.com is a company newsroom, not a Facebook post. Owner corrections and frozen-preview invalidation continue across canonical aliases.

## Actual Meta results

This validation reused the exact retained result set; it did not run new discovery or substitute fixtures. All 126 observations remain. Deduplication yields 94 unique findings, all assessed, with zero pending and assessment_complete=true.

- 55 relevant findings within the known period or with an unconfirmed date: 12 reporting, 9 client-owned, 32 social, 1 press-release distribution and 1 unknown type.
- Of those, six have confirmed publication dates: four reporting and two client-owned announcements. The remaining 49 have unconfirmed dates and remain visible in Articles without entering confirmed-period totals.
- Ten verified older findings are excluded from normal browsing; 26 findings were assessed as not relevant; three remain uncertain. These states sum to 94.
- Reporting overview: four articles at three outlets. TechCrunch: two; ABC News: one; Ars Technica: one. Critical reporting is included.

Confirmed reporting source reconciliation:

| Outlet | Article | Publisher publication metadata (UTC) |
| --- | --- | --- |
| TechCrunch | https://techcrunch.com/2026/09/25/meta-is-putting-its-muscle-behind-muse-as-the-ai-app-takes-off/ | 2026-09-25 16:16:52 |
| ABC News | https://abcnews.com/amp/Business/metas-muse-ai-agent/story?id=136680507 | 2026-09-24 21:08:56 |
| TechCrunch | https://techcrunch.com/2026/09/23/everything-new-coming-to-metas-ai-agent-muse/ | 2026-09-24 01:13:32 |
| Ars Technica | https://arstechnica.com/ai/2026/09/muse-metas-extraordinarily-privileged-ai-assistant-has-a-serious-0-day/ | 2026-09-21 22:24:38 |

Across the final unique set, 27 have verified publisher publication metadata, 19 public-page checks lacked an unambiguous date, nine denied access, two were unavailable, one was non-HTML, and 36 relied on public social/search evidence. These are access outcomes, not claims that every full article was read. For example, the WIRED Muse launch article has a verified September 8 date and is correctly outside this past-week search. Axios and The Information denied page access; their retained excerpts remain assessable, with date limitations visible.

Three explicit validation attempts were recorded. The first used 53 source requests and three AI jobs before the existing runtime event guard stopped one batch with its generic Unexpected tool activity error. The exact rejected event type was not recorded, so this is not proof of a particular tool invocation. An explicit resume used seven AI jobs and no source requests, completing all assessments and content-type checks. A final generalized check included seven previously negative public pages and one AI job. Final durable usage: source 161 -> 221 (+60, including redirects); AI 42 -> 53 (+11, including the interrupted job). Historical cap values remain recorded, inactive under the owner's previous limit-removal instruction. No automatic retries, paid fallback, new discovery or channel posts occurred.

The runtime guard remains restrictive. Its error now includes only the rejected event's safe type name for diagnosis; no additional tools or event types were allowed. Managed ChatGPT authentication and dedicated runtime isolation remain unchanged. Private before/after evidence reports remain in ignored data/research-comparison-overview-meta-complete-{1,2,3}.json under the existing retention policy; they are not committed to GitHub.

## UX and validation

Navigation is now a compact active-view text header with one native view selector, replacing the three-button row. Slack's documented Block Kit catalog has no custom Home tab element, so the labels are not falsely presented as clickable native tabs. Articles has one main filter: Relevant, Needs attention, All results. No Unassessed or Outside period option. Reporting-only counts remain the Overview default; Articles outside an outlet drill-down includes all source types. Correct changes one detail at a time with a short supporting note and a native date picker.

186 offline tests passed (19.49 seconds). Tests block network and DNS and never load .env. New regressions cover full-set assessment, public excerpt/paywall behavior, date precision and exclusive bounds, cached denials, large criteria and metadata payload sizing, simple navigation/filters/corrections, canonical deduplication, saved perspectives and correction invalidation of frozen previews. Existing privacy, owner-only AI, runtime isolation, collaboration, deletion and exact publishing confirmation tests pass.

Live Slack accepted updated Explore, Team board and Briefings Home payloads and each of the three Articles filter views. Correction forms passed local Slack SDK schema validation. This is not visual validation: the available computer inventory contained no apps or browsers. The owner must check light/dark/narrow layouts, the view switcher, Articles filters and correction field/date-picker interactions. Real teammate interaction and actual publishing were not performed. No sharing authorization was inferred from this validation.

Tested runtime remains Python 3.13.9, official Codex SDK/CLI 0.157.1, managed gpt-6-luna, Slack Bolt 1.30.0, Slack SDK 3.44.1, Pydantic 2.13.5 and pytest 9.1.1. No dependency update was necessary.

References: [Slack Block Kit](https://docs.slack.dev/reference/block-kit/blocks/), [Slack buttons](https://docs.slack.dev/reference/block-kit/block-elements/button-element/), [official Codex App Server events](https://learn.chatgpt.com/docs/app-server).

One local backend was started after validation: Socket Mode readiness True, PID 17096 at handoff. Manage it with `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/backend.ps1 status` (or start, stop, restart). It requires this Windows host to remain running.
