# Empire AI — Page-only GSC commercial visibility
18 October 2026 | Isolated feature branch | Running production unchanged

## Why this closes an actual measurement gap
EmpireOS previously queried Google Search Console grouped by query and page,
or date only. Search Analytics may omit anonymised queries. Missing
query/page rows do NOT establish that a priority page has no impressions.
The new page-only dimension can check those pages without inventing query
volume, buyer intent or revenue.

## Verified current live evidence (18 October)
- Existing GSC property: sc-domain:empire-ai.co.uk (available).
- Window: 8–17 October 2026. Query/page reader returned 7 rows and 16
  impressions in those returned rows; zero matched the four priority pages.
  The 16 impressions are NOT full-property traffic.
- Existing site indexability probe: 21 sitemap URLs, 21 with indexability
  signals; 0 technical issues in that bounded check.
- All 4 priority URLs are in the sitemap and returned HTTP 200:
  /industries/roofing, /industries/solar, /industries/hvac,
  /predictive-revenue. This does NOT prove Google indexed them.
- Production page-only endpoint currently returns HTTP 404. No measured
  per-page GSC totals can truthfully be claimed yet.

## Existing Search Intelligence extension
1. search_console.py: page_observations method on existing approved adapter.
   Uses fixed dimensions of page, dataState final, bounded rowLimit, read-only
   Search Analytics request; disabled adapter rejects without network.
2. api.py: GET /v1/search/search-console/pages. Requires existing GSC
   activation, strict date parsing, maximum 31-day window; emits source,
   page dimension and explicit unverified buyer/indexation/revenue flags.
3. first_party_gsc_page_review.py: checks authentic GSC property and final
   response, strict first-party page URL provenance, numeric sanity,
   duplicate detection, source receipt hashes and four-page allowlist.
   www/apex aliases remain separate. Never silently total aliases.
4. review_live_gsc_page_performance.py: one-shot existing loopback reader
   with four-page summary. Fails closed on absent /pages route, and never
   falls back to query/page metrics.

Google API source documentation:
https://developers.google.com/webmaster-tools/v1/searchanalytics/query

## Reproduction after approved integration
Run inside /srv/empire_os:
  ./.venv/bin/python -m scripts.review_live_gsc_page_performance
     --start-date 2026-10-08 --end-date 2026-10-17

Until owner integration, the CLI deliberately fails as
GSC_PAGE_DIMENSION_NOT_YET_VERIFIED rather than return fake zeroes.

## Release gate
Search Intelligence owner reviews active canonical changes, tests adapter,
API and returned metric provenance, then uses existing service release
controls. Restart of existing service only with explicit owner approval
and rollback. Validate GET /pages without ever logging credentials.
Never add page-only totals to query/page totals, imply indexing or convert
observations into prospect records.

## Cross-agent website overlap: avoid double implementation
Another agent already committed c15a0e81 on
feature/website-entry-attribution-20261018. That branch adds the same
commercial form claimed-entry concept as our 9a3965d8 feature.
The other agent defaults direct/unknown referrer to /commercial; our
helper defaults to null, retaining uncertainty about previous page.
The backend supports absent claimed_entry_page. ASTRA should choose
one helper and reconcile semantics; never cherry-pick both implementations.
This page-only GSC release does not depend on either frontend helper.

## Commercial truth
No paid third-party API spend, no new SEO crawler, no service restart,
no database writes, no email sends, no site deployment, no genuine lead
created and no realised revenue verified. Feature remains isolated.

## 18 October 2026 — Founder-authorised integration status
The founder explicitly approved integrating the existing GSC page-only reader.
The reviewed API and Search Console adapter changes, corresponding tests and
read-only CLI were copied into the canonical /srv/empire_os checkout after
checking clean target files and retaining backup copies of the original
api.py and search_console.py under
/home/ubuntu/empire_search_page_reader_rollout_20261018/.

An integration import issue was caught by canonical tests: the original
feature-only reviewer referenced first_party_semantic_corpus.py, absent on
the canonical checkout. Its canonical version is now self-contained and
exports the four exact priority page routes and a local GscPageEvidenceError;
the live CLI and tests were adjusted accordingly. This avoids merging the
unfinished semantic model into production.

Canonical checks: 118 relevant Python tests passed. A TestClient request
against the actual production service ASGI application resolved the new
page-only route (HTTP 422 for intentionally malformed date input), confirming
route registration. The existing RUNNING systemd process still serves the
old imported code and answers 404 for the new page-only path. Its existing
health endpoint is HTTP 200. An unprivileged systemctl restart was attempted
but refused by systemd because it requires interactive administrator
authorisation; no alternative process-control bypass was attempted.

**Required one-time action in founder's trusted SSH terminal:**

    sudo systemctl restart empire-search-intelligence-api.service

After that, verify:

    systemctl is-active empire-search-intelligence-api.service
    curl -fsS http://127.0.0.1:8771/health
    cd /srv/empire_os
    ./.venv/bin/python -m scripts.review_live_gsc_page_performance --start-date 2026-10-08 --end-date 2026-10-17

If the restart fails, do not claim the endpoint is live. The original files
are backed up, and any rollback should be owner-performed with the snapshot,
checked exact source state and the standard controlled service restart.
No database writes, new permissions, customer submission, paid source,
credential logging, traffic purchase, outbound or publishing occur here.
