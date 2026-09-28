# Research redesign validation

Reviewed checkout: `4eccc07deb09d78cbb797431fcb0f8bc42e4d579`. The checkout matched that baseline; no newer user work was reset. The supplied redesign brief was preserved.

## What was reproduced and repaired

Before implementation, 11 regression cases failed and one passed. The failures reproduced duplicate visible cards and saves, stale results after five kinds of scope edit, campaign-irrelevant default results, unknown dates treated as relevant, repeated headings/page analysis, and published items labeled View draft.

Article identity now precedes filtering, counts, pagination, assessment and board saves. Observations retain URLs, queries, timestamps, scope/run IDs and source versions. Relative windows freeze to the run clock in UTC. Current relevant results require compatible assessment, verified publication dates, subject relevance and campaign relevance where applicable. Message absence and critical coverage do not exclude a relevant source. Previous scope, Needs review and All collected remain inspectable. Assessment continuation operates across the run, not the displayed page.

Migration was applied to the actual database after stopping the old backend. A consistent SQLite backup was created first. IDs, board references, perspectives, draft text, visibility, expiry and budget history were preserved; preview tokens were invalidated. The migration is idempotent. Backups retain original expiry and participate in expiry deletion. Never restore an old budget ledger over the current one.

## Native capability and provider choice

The official Python SDK and Codex CLI remain pinned at **0.157.1**. Managed authentication reports **chatgpt**, selected model **gpt-6-luna**, fresh ephemeral threads and verified controls. The native slice returned 31 tool-observed text results in one observed hosted search event. It used one AI job and conservatively reserved three source slots. No page-open success was inferred.

The restricted native role permits only supported hosted public web search/open/find. Analysis, planning and briefing remain tool-free. Shell/editing/MCP/plugins/images/delegation, local files and development tools remain unavailable. The shared configuration lock is acquired before preparation. Observed action guards are not a preemptive hosted-network firewall: three source slots are reserved and the third observed action triggers interruption. Internal provider request counts are not observable. Unexpected tools, invalid quotes and generated citations cannot create evidence-backed claims.

Native evidence was auditable, but research quality did not justify it as the default. Two trials retrieved historical/undated material and many model quotations did not match the observed snippets. The explicit default is **AI-planned Brave**, followed by separate no-tools assessment of the exact retained excerpts. Native research remains a labeled limited option. No mid-run switch or API-key AI fallback occurs.

## Small live before/after comparison

The rubric came from each public monitor's scope: general Stephen Curry coverage includes personal, professional and business reporting; Everything is Possible requires evidence of that campaign; Patagonia means the clothing company, not the region. Desired repair/reuse messages are assessment criteria, not a requirement for relevance. Dates must satisfy the frozen window using verified publication metadata.

The before path used the reviewed quoted-name Brave query construction, bounded to one request and ten results per case. After paths used their documented separate limits. This is a diagnostic comparison with unequal retrieval budgets, not a controlled provider benchmark or internet-recall claim. The judgments below are implementation-agent review of retained evidence, not independent human annotation or AI self-scores.

| Public scope | Before unique / seconds | After path: unique / seconds | Validated assessments | Current relevance gate |
|---|---:|---|---:|---|
| Stephen Curry, general, past year | 10 / 1.04 | Native: 43 / 68.88 | 7 of 15 proposed; 36 pending | 0 relevant, 42 review, 1 outside dates |
| Stephen Curry, Everything is Possible, past year | 10 / 0.45 | Native: 43 / 51.26 | 1 of 10 proposed; 42 pending | 0 relevant, 43 review |
| Patagonia clothing brand, past month | 10 / 0.80 | AI-planned Brave: 20 / 86.74 | 15 of 15 selected; 5 pending | 1 relevant, 19 review |

Actual examples and errors:

- General-person before results included the contract extension, recovery/health reporting and a critical Defector column: all five inspected top snippets matched the subject. Native search over-focused on Curry Brand despite an empty campaign. Its [brand-launch release](https://www.prnewswire.com/news-releases/under-armour-and-stephen-curry-launch-curry-brand-301182761.html) had a publisher-verified 2020 date and was correctly excluded from current results. Another top result was Spanish despite the requested English language. Subject matching alone did not establish freshness.
- The first five campaign results in both paths lacked evidence of Everything is Possible. A native assessment incorrectly treated a [brand-separation report](https://www.bloomberg.com/news/articles/2025-11-13/stephen-curry-under-armour-agree-to-end-deal-with-his-brand) as campaign-relevant. Exact quote fidelity does not establish semantic correctness; the unverified date kept it out of the default current list. No campaign success is claimed.
- Brand before results correctly named Patagonia, but included a size-chart page. Among the first five collected after results, three snippets established the clothing brand, one did not establish it, and one discussed another brand. The assessments reflected those differences. The current eligible [Don't Buy This Jacket case study](https://thebrandhopper.com/campaigns/a-case-study-on-patagonias-dont-buy-this-jacket-campaign) stayed relevant even though its retained excerpt did not contain the repair/reuse message. A geography/disambiguation page was classified not relevant and remained inspectable.
- The planned brand trial over-focused its second query on a desired repair message despite no campaign. The planner now receives entity/editorial criteria without desired-message wording; messages remain in assessment. Broad queries are prioritized when no campaign is set. This correction has offline coverage; a fresh live run awaits additional allowance.

Reviewable case-level queries, URLs, bounded excerpts, dates, classifications and independent rubric notes are retained locally under `data/research-comparison-*.json`, including `research-comparison-review.json`. These are permitted public-source exports, not tracked fixtures, and expire after the configured retention interval. No full publisher pages are stored. Brave page_age may mean published or modified; it never proves publication freshness. Bounded application verification records explicit publisher metadata and honors denied access, redirects, public DNS, TLS, size and time limits.

## Actual workflow and limits

The live brand finding was saved to the workspace board, marked Reviewed, given an explicitly labeled implementation-agent validation note, and used to create **Patagonia | reviewed research example**. Its title/text were edited and an exact source-linked preview was validated. This was an owner-authorized implementation flow, not a real teammate contribution or a claim that the owner personally wrote the validation note. No channel message was posted. The owner must open a fresh Preview & publish modal and explicitly confirm any actual post.

Slack authenticated, confirmed the configured public channel's membership, and accepted all three redesigned owner Home payloads. No Slack/browser inspection surface was available (`apps: []`, `browsers: []`); payload acceptance is not visual validation. Actual desktop/narrow/light/dark rendering and a real two-account collaboration walkthrough remain unverified.

The durable ledger is **49/50 source slots and 10/10 AI jobs**. It includes all earlier builds/owner actions, the source-cap amendment, conservative native reservations, provider requests and metadata redirects. Nothing was reset. The owner approved raising source allowance from 30 to 50, not AI allowance. A request for caps of 57 source / 12 AI is pending; until approved, another full Refresh is blocked by the existing cap. Browsing, evidence inspection, discussion, editing and exact-preview preparation remain usable.

## Verification and walkthrough

- Offline suite: **118 passed** on the final focused suite; network calls are blocked and `.env` is not loaded. Tests cover identity, current/history scope, filtering, cache context, one-action research, partial evidence, migration, owner/private/workspace restrictions, exact evidence, tools, cancellation, Slack dispatch and publishing confirmation.
- Generated **21 explicitly synthetic Slack payloads**, validated with the Slack SDK; these are not screenshots.
- Dependencies: Python 3.13.9; Slack Bolt 1.30.0; Slack SDK 3.44.1; openai-codex / CLI 0.157.1. No dependency upgrade or paid fallback was introduced.
- Startup is a single local Socket Mode process, protected by the existing project PID check and port lock. Use `scripts/backend.ps1 status`, `start`, `stop`, or `restart`. It requires its local Windows host/session to remain alive.

Owner visual checks: open Explore on Patagonia and confirm the first finding fits above the initial scroll; inspect the full headline and evidence at narrow width; switch Relevant / Needs review / All collected and page without launching AI; inspect retrieval observations; open Team board and the reviewed example; edit its briefing title, open Preview & publish, and verify the exact channel/content. Publish only if desired. Ask a real teammate to add their own perspective and edit a shared draft to complete the real multi-user check.
