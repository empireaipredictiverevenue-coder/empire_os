# Empire AI — OpenSEO/DataForSEO £0 reader integration
Date: 18 October 2026
Owner: Search Intelligence (feature-only). Status: TESTED LOCALLY; NOT DEPLOYED.

## Why
Inspect OpenSEO's reusable patterns, not its hosted paid data. OpenSEO (MIT) self-hosting
uses bring-your-own DataForSEO credentials. DataForSEO sandbox gives dummy responses;
free signup credit is limited, and there is no authorised unlimited free paid-data feed.

Sources:
- https://github.com/every-app/open-seo
- https://docs.dataforseo.com/v3/appendix/sandbox/
- https://dataforseo.com/help-center/how-does-your-free-unlimited-trial-work
- https://docs.dataforseo.com/v3/serp/google/organic/live/advanced/
- https://index.commoncrawl.org/ (public URL capture index; NOT search ranks)

## Repo inspection (18 Oct)
Existing first-party: empire_os/search_intelligence/search_console.py and organic_revenue_baseline.py.
Existing SERP reader: empire_os/search_intelligence/serp.py (SearchFabricSerpAdapter).
Existing analysis: competitor_gap.py, backlinks.py, ai_visibility.py, rank_history.py.
Existing free-first Search Fabric: empire_os/search_fabric/search.py, including its own caching,
engine cooldowns, and bounded search. Do not spawn a second scraping department.
Existing Keyword Universe: empire_os/keyword_universe.py.

## What this branch adds
- empire_os/search_intelligence/dataforseo_reader.py — local-only JSON importer for
  DataForSEO Google organic advanced results, into EXISTING SerpSnapshot/SerpResultEvidence.
- scripts/review_dataforseo_import.py — read-only CLI, no credentials or network.
- tests/search_intelligence/test_dataforseo_reader.py — synthetic contract and integration tests.

Its two explicit modes are:
1. sandbox (default): parses provider response envelope metadata but marks all rank
   data DUMMY_NOT_EVIDENCE. Never passes ranks to competitor-gap scoring.
2. authorised_export: imports JSON provided by an authorised user/API workflow,
   requires explicit timezone-aware observed_at, fingerprints full response and preserves
   source/task/locale/device/organic rank/absolute rank and reported request cost.
   Labels IMPORTED_UNVERIFIED, because a JSON document alone cannot prove actual API origin.

The parser does NOT authenticate to DataForSEO, incur charges, bypass access controls,
scrape the OpenSEO hosted site, claim Google ranking proof from Bing results, write
EmpireDB, or publish content. The code intentionally refuses to infer missing positions.

## CLI usage
Run FROM the isolated worktree root, using the same Python as existing EmpireOS:

    /srv/empire_os/.venv/bin/python -m scripts.review_dataforseo_import /path/to/authorised.json --mode sandbox

An already authorised real API export may be examined as:

    /srv/empire_os/.venv/bin/python -m scripts.review_dataforseo_import /path/to/authorised.json --mode authorised_export --observed-at 2026-10-18T12:00:00+00:00

The timestamp must represent actual observation time, not execution time or a guess.
No credentials should appear in JSON exports. CLI emits a compact evidence summary,
never the entire source payload.

## Follow-up that does not overlap other agents
1. Add a bounded, explicitly budgeted DataForSEO API transport only if authorised and
   actual provider credentials/credit are already available. Require request receipts.
2. Merge/export to existing EmpireDB Evidence Fabric after owner approves schema contract.
3. For genuinely £0 fresh evidence, continue using the existing GSC and Search Fabric,
   and coordinate with the Common Crawl work owner. Common Crawl captures are evidence
   of public URL discovery, not keyword volume, Google position, or backlinks by default.
4. Compare SEO opportunities against downstream buyer/payer fit, territory, real accepted
   event and realised revenue. Do not publish inferred revenue or fabricate rankings.
5. Keep all paid calls disabled by default and do not automate against OpenSEO's hosted site.

## Production gates
ZERO paid API calls. ZERO new timers/services. ZERO changes to production database.
ZERO public website changes. Feature branch only. Merge/deploy after owner integration review.
