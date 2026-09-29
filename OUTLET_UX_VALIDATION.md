# Outlet context and simpler review - 29 September 2026

## Changes

- Removed the separate Correct action row. Inspect now offers Edit finding; the finding row offers Mark relevant only for matches not already relevant.
- Mark relevant is an owner-only, attributed correction for the current scope/revision. It preserves the original AI analysis, message evidence and publication certainty. Repeated identical owner confirmations do not create duplicate reviews.
- Source details starts with an outlet description, topic/audience significance, editorial signals, supporting links and a visible priority rationale. Detailed retrieval diagnostics remain paginated afterward.
- Ten initial profiles: Reuters, Associated Press, TechCrunch, Ars Technica, ABC News (US), ESPN, WIRED, The Verge, The Guardian and NBC News. References were reviewed through public publisher pages on 29 September 2026 and are linked in coverage_desk/outlet_profiles.json. Publisher claims are identified as such; this is not an independent accuracy audit. Unreviewed outlets receive a neutral description and standard priority.
- Established reporting is sorted ahead of standard-priority findings, before pagination. Recency and deterministic identity break ties. Owner Higher/Standard/Lower/default preferences support any exact website, including specialist or local outlets missing from the initial catalog. Preferences are private, attributed, snapshot-aware and expire with the source evidence. No automatic reputation inference from subdomains, aliases, ownership, search rank, syndication or sponsored placement.
- Existing counts, chart order, eligibility, saved work, privacy and publishing confirmation remain intact. No SQLite schema migration or source rewrites were necessary. No runtime/dependency/provider change.

## Tests

196 offline tests passed in 21.39 seconds. Networking and DNS are blocked; tests never load .env. Six initial regressions failed before implementation, reproducing the old controls, missing profiles, date-only ordering and absent review action. New tests cover owner review dispatch, unchanged dates/messages/usage, no teammate or wrong-workspace authority, stale-scope rejection, private notes excluded from shared artifacts, priority reset and parent-modal refresh, snapshot-stable ordering, exact-host/lookalike boundaries, sponsored-content exceptions and count preservation. A previous hardcoded-calendar test was made relative so it remains valid after September 28; provenance navigation now verifies its second page after the outlet introduction.

Live validation used the four existing owner searches and 511 retained unique findings. Twenty finding URLs matched a reviewed outlet profile. All unique-identity and outlet/article totals reconciled, and priority order held before pagination. Slack accepted the updated Relevant, Needs attention and All results Home payloads. Modal structures passed local Slack SDK schema validation. The owner preferences were restored afterward; no real findings were reclassified just to test the feature.

Application usage stayed unchanged at source 490 and AI 91, with historical caps preserved and inactive. No source retrieval, runtime AI jobs, private sharing, channel posts or deployment occurred during this validation. Public publisher-reference research used the development browsing tool, separate from application search. Run the same no-inference check with `.venv\Scripts\python -m scripts.validate_outlet_ux` when no owner research job is active.

## Remaining visual checks

Computer-use inventory returned no apps or browsers. Payload acceptance is not visual validation. In Slack, check light/dark/narrow layouts, Inspect > Source details and its next page, Mark relevant on a finding you actually want to reclassify, Edit finding and its return to Inspect, and Higher/Lower/default outlet priority. A relevant item may still need attention for an unknown date/type; marking relevance does not manufacture evidence. No real multi-user or publishing walkthrough was performed.
