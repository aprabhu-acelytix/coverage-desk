# Social discovery validation — 29 September 2026

## Offline

205 tests passed in 21.50 seconds with networking and DNS blocked. Coverage includes every selected
platform, aliases and supplied handles, separate focus/broad queries, fair initial
coverage, unchanged per-run reservation ceilings, observed-evidence-only follow-up,
profile/lookalike exclusion from URL follow-up, cancellation/incomplete discovery,
cross-pass event-ID collisions, same-URL excerpt combination, exact original-text
preservation, scope isolation, earliest expiry, explicit publication-day evidence,
and priority-preserving pagination. Existing privacy, sharing, runtime isolation,
message evidence and overview tests remain green. Python compilation also passed.

No dependency or runtime permission changes. Tests continue to use the existing
pinned environment; no API key, new integration or social scraper was introduced.
No schema migration is needed. Observation IDs, board references, drafts and usage
history remain intact. Combined excerpts record original text and source IDs and
shorten (never extend) their representative's retention deadline when necessary.

## Live owner workflow

Ran `scripts.validate_overview --client Meta --operation refresh` against the
existing Meta / Muse search and actual SQLite ledger. The initial implementation
completed planning, two discovery passes, public publisher checks and assessment
in 310.9 seconds. Owner Home payload accepted; no channel posts.

| Retained current-scope evidence | Before | After refresh |
|---|---:|---:|
| Unique findings | 129 | 175 |
| Social URLs (including incidental platforms) | 44 | 87 |
| Social URLs with both Meta and Muse in observed title/excerpt | 34 | 41 |
| Confirmed reporting appearances | 12 | 12 |
| Confirmed reporting outlets | 8 | 8 |

The lexical check is a transparent diagnostic, **not precision, recall, or proof
of relevance**. Existing compatible findings were retained. Added undated social
evidence did not inflate confirmed-period reporting counts. The refresh assessed
174 of 175 findings; one unrelated X athletics result failed structured/evidence
validation and remained flagged. A separate explicit assessment repair attempt
was run and recorded, without an automatic retry loop. It succeeded in 21.2
seconds: all 175 findings are now assessed and the unrelated result is excluded.

Reviewable examples from the new retained evidence:

| Source | What the observed evidence establishes |
|---|---|
| [I Tested Muse, Meta's Agentic Commerce App](https://www.linkedin.com/pulse/i-tested-muse-metas-agentic-commerce-app-debra-aho-williamson-qnd9f) | Title and excerpt explicitly connect Meta and its Muse agent; full post and publication date remain unverified. |
| [Meta Muse — Full Technical Explanation](https://www.linkedin.com/pulse/meta-muse-full-technical-explanation-hiran-wyatt-s8egf) | Excerpt describes Muse as Meta's personal AI agent; does not establish the accuracy of its technical claims. |
| [Muse challenge discussion](https://www.reddit.com/r/MetaAI/comments/1wnci1j/i_gave_muse_ai_a_challenge_make_100_in_30_days/) | Retained excerpt describes using Muse AI; the date printed in snippet prose is not promoted to verified publication metadata. |
| [Meta advertising post](https://x.com/Sheeema_market/status/2023675031654367396) | Concerns advertising delivery, not Muse; broad search can retrieve unrelated client mentions, which stay inspectable. |

## Live iteration across all seven platforms

Two explicit discovery-only probes used the existing ledger and public Meta/Muse
scope, without editing saved searches. Each used 13 reserved source slots and two
managed Codex jobs. Complete observations and source snippets are retained in the
gitignored, retention-cleaned `research-comparison-social-*.json` exports.

The first draft combined campaign and brand-only alternatives in one OR query.
It returned 70 unique URLs, only 12 of which explicitly named both Meta and Muse.
Inspection exposed unrelated profiles and generic Meta posts. The code was then
corrected to keep the topical query separate from broad fallback and to reserve
URL follow-up for actual post/article paths.

The corrected probe returned 26 unique URLs; 12 explicitly named both Meta and
Muse. This reduced noise in this small test while retaining that lexical match
count. It does not establish broad internet recall or reliability across clients.
These probes do not run assessments, so their counts are discoveries, not AI
relevance labels or confirmed-period counts.

| Platform | Corrected probe: unique public URLs | Limitation |
|---|---:|---|
| Instagram | 2 | One had an excerpt; one metadata only. |
| X | 0 | Initial and follow-up searches returned no accessible results. |
| LinkedIn | 12 | Search excerpts only; useful explicit Muse mentions observed. |
| Facebook | 0 | Initial and follow-up searches returned no accessible results. |
| TikTok | 12 | Discovery only; result quantity is not relevance evidence. |
| Reddit | 0 | Initial and follow-up searches returned no accessible results. |
| YouTube | 0 | Initial search ran; the shared allowance did not reach a follow-up. |

These empty results are genuine limitations, not proof that those platforms lack
coverage. Earlier compatible findings are not removed by an empty refresh. No
login, scraping, paid fallback or extra source integration was used to bypass the
gaps. URL-targeted evidence expansion and hashtag follow-up have offline workflow
coverage; the live sparse-site allocation did not exercise every possible variant.

## Usage and UI boundaries

Usage began at 490 source reservations/requests and 91 AI jobs. After the refresh
and both discovery probes it was 534 and 103. Historical caps remain 50/10 in the
ledger and are inactive under the owner's existing authorization. The separate
assessment repair added one AI job. Final usage is 534 source reservations/requests
and 104 AI jobs: this revision used 44 and 13 respectively. No counter or allowance
was reset.

There was no available Slack browser/native inspection surface. Home payload
acceptance is an API check, not visual validation. Owner checks: More options
handle hint, Articles source filtering and default priority, Search details
platform counts on a narrow window, light/dark readability, Inspect evidence and
the unchanged exact publishing preview. No live teammate or channel-publishing
test was performed in this revision.

The final retained-data check covered four monitors and 557 unique findings:
priority order and counts reconciled, all three owner Home filters were accepted,
and usage remained unchanged. Modal checks were local schema validation only.
