# Public social discovery

Coverage Desk searches public web results for Instagram, X, LinkedIn, Facebook,
TikTok, Reddit and YouTube. These are search targets, not authenticated platform
integrations. No scraping, login, video/transcript download or new provider is
introduced. Access to private or unindexed posts is not implied.

## One owner Refresh

1. Plan the public topic without desired-message restrictions.
2. Search each selected source before allocating follow-up capacity. Social
   queries use the supplied name and aliases/handles as alternative identities,
   while retaining the planned campaign topic. Broad brand-only queries are a
   separate route, so they cannot overwhelm the focused query. Put known public
   handles in Other names or public handles (More options), or the handles field.
3. If the first discovery pass completes, use remaining capacity for one bounded
   second pass. Sparse platforms get a topical query with relaxed date operators,
   followed by a broader name/alias query when capacity remains. Promising observed
   post/article URLs can get a URL-targeted search for additional indexed evidence,
   followed by broad or observed-hashtag variants. Profiles and account settings
   do not receive URL-targeted follow-up. No generated URL
   or model-authored quotation enters the evidence registry.
4. Follow-up queries relax date operators; broad short-period searches receive a
   calendar-month hint. Publication evidence still controls period eligibility. Unknown dates
   remain unknown, and confirmed outside-period results stay out of normal views.
5. Combine retained, same-URL social search excerpts within the current scope and
   input-size bound before the existing complete assessment workflow. Preserve
   original excerpts, observation IDs, exact quote checks, and provenance. The
   combined record expires no later than its earliest included source.

Both native passes share the existing configured allowance: at most 12 planned
search actions; one reserved cancellation-boundary slot per pass. A two-pass run
uses at most 11 planned actions plus two boundary reservations, keeping the same
13-slot maximum as the previous single-pass run. Smaller configured limits also
apply. Selecting all nine sources leaves room for one or two follow-up actions,
depending on whether a separate broad reporting query is needed for a campaign.
Search details identifies unsearched routes; it does not imply every platform
received every query variant. No automatic retry after incomplete discovery,
cancellation or a scope edit. Internal search-provider request counts are not
exposed by the runtime; reservations and observed actions are recorded separately.

The explicit Brave alternative retains its existing bounded single-pass workflow
and benefits from expanded initial social queries. Adaptive second-pass discovery
is specific to Codex native web. There is no silent provider switch.

## Reading results

Open Articles and use Source & history filters to select a platform. Social posts
remain excluded from the default reporting-by-outlet totals. Search details shows
unique retained platform findings, assessed findings, excerpt/metadata availability,
and whether follow-up was searched. Retained totals can include compatible earlier
runs. Search snippets are not full-post access. Empty public results are not proof
that no posts exist. Browsing and filtering never trigger research.

Reviewed editorial sources and owner-set priorities remain the default order,
before pagination, even after filtering. Unknown outlets stay visible at standard
priority. Popular platform domains do not establish an individual author's
reputation. The app has no verified traffic dataset and does not invent traffic,
reach, follower counts or reliability scores. Owner preferences can prioritize
an exact outlet host; they are not independently verified audience measurements.

## Walkthrough

Edit a search, add known aliases/handles, select the desired platforms, and choose
Save & refresh. After completion, open Articles, choose a platform, and Inspect a
finding's source evidence. Open Search details for platform coverage gaps and
follow-up status. Save relevant evidence to the board and use the existing briefing
preview workflow. Publishing still requires the owner's exact confirmation.

See SOCIAL_SEARCH_VALIDATION.md for actual tests and live results.
