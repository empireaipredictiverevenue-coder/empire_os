# EmpireOS Search Fabric | Buyer-keyword source diagnosis — 16 October 2026

**Existing owner:** Search Intelligence / Search Fabric provider. **Decision:** EVIDENCE_HOLD, not a new infrastructure purchase. **Public work:** NONE. This report does not change the production source, outbound actions or Google indexing.

## Observed 16 October

The running local Search Intelligence endpoint `POST /v1/search/serp/snapshot` correctly refuses to invent positions. Three explicit `bing_html` keyword samples about UK AI readiness/cost/deliverables returned HTTP 200 response envelopes with `snapshot.available=false`, `engine=none`, `error=All engines failed`.

A single, separately bounded direct GET of Bing's UK-locale search page returned **HTTP 200**, ~94 KB of HTML and a title matching the search phrase, but the body contained **zero `li.b_algo`, zero `#b_results h2 a`, and zero H2 headings**. The current `_parse_bing_html` found zero organic rows; the current lexical evidence filter therefore had no rows to examine. This indicates that the served document was not an extractable organic SERP, **not** that any business page lacks demand or that the parser merely needs a new CSS selector.

Separate bounded existing-provider checks `bing_rss` and `duckduckgo_html` for the same phrase returned zero available results; a one-time direct Mojeek GET returned HTTP 403 and is treated as a provider restriction, **not** something to bypass or rotate around.

The existing Search Fabric cache was inspected read-only: **1,686 readable cached snapshots**, **2 unreadable**, including various old engines, but **zero records** with queries containing `readiness`, `ai assessment`, `ai audit`, `opportunity assessment`, `ai consultancy`, or `ai consulting`. The cache is no fallback evidence for this candidate. Some older snapshots exceed the configured 24-hour TTL and should not be treated as current rank positions.

Independent first-party Search Console records processed 17 September–13 October had **78 sitewide impressions and one click**, with **11 disclosed query/page pairs (25 sampled impressions, zero sampled clicks)**. Those pairs cover mostly branded Empire searches and irrelevant retired AEO topics; there are **zero independently observed AI-assessment buyer query rows** among the disclosed pairs. The query sample is partial, so this cannot prove zero total hidden demand.

## Correct owner action

1. Have the Search Fabric owner inspect the Bing response structurally and the existing parser/quality gate on the current branch; preserve upstream blocks and Terms, and fail closed rather than guessing ranks. Do not buy a new provider or add an always-on scraper.
2. Improve the difference between a **configured provider** and **a provider that produced verified organic observations** in owner-controlled health/reporting. Current `/v1/search/summary` marks the SERP source `available_via_search_fabric` without proving the last keyword search produced any results. Avoid a misleading green health indicator.
3. Research Desk may use its existing authorized first-party Google Search Console data and publisher webpages, but publisher discovery cannot substitute for measured Google SERP positions or search volumes.
4. If a compliant, owner-approved alternate source is connected in the future, verify with a small, timestamped UK locale sample and assert actual positional provenance, query relevance and no paid request surprise. Do not equate Bing position and Google position.
5. Keep Campaign GROWTH-001 at **RESEARCH_ONLY** until real buyer search signal or a separate, editor-led zero-spend distribution experiment is explicitly approved.

**Service status:** No production restarts, provider configuration changes, new credentials, account creation, fake positions, bypasses or public posts. ASTRA unfinished flagship remains untouched.

**Engineering files already present:** `empire_os/search_fabric/search.py`, `empire_os/search_intelligence/serp.py`, `tests/test_search_fabric_recovery.py`, `tests/search_intelligence/test_serp.py`. Extend the existing owner checks rather than building a second Search Fabric.
