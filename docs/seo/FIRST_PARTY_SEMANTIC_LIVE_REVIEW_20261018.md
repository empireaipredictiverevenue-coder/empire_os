# Empire AI — Real First-Party Semantic SEO Review
18 October 2026 · isolated worktree · OBSERVE · £0

## Live sources (read-only)
- Existing Search Intelligence service: `http://127.0.0.1:8771/v1/search/search-console/status` and `/search-console/observations`.
- Source returned `available=true`, `source=google_search_console`, `site_url=sc-domain:empire-ai.co.uk`.
- GSC requested window **3–15 October 2026** (query+page dimension, limited 1000 rows).
- Four actual public URLs fetched independently with HTTP GET. No production writes.

## Verified run results
- **9** returned query/page observations; **23** impressions IN THESE ROWS ONLY.
  Neither is a sitewide count or proof of target-sector demand. Query-level
  privacy filtering may omit results.
- **0/9** query/page observations matched current priority commercial routes.
  All 9 remained explicitly unmapped rather than fabricated into commercial
  rankings or buyer-intent signals.
- **4/4** owned public priority pages returned HTTP 200 and usable
  title/H1/HTTPS canonical metadata:
  - `https://empire-ai.co.uk/industries/roofing`
  - `https://empire-ai.co.uk/industries/solar`
  - `https://empire-ai.co.uk/industries/hvac`
  - `https://empire-ai.co.uk/predictive-revenue`
- **4** page-title keyword seeds created as UNMEASURED CANDIDATES, not observed
  search queries. Four independent topical groups and four potential
  page-metadata matches resulted. No page-body semantic coverage claim.
- **0** verified conversion/buyer revenue events from this GSC review.
  This means *not measured by this review*, not that all Empire revenue is zero.
- No requests to DataForSEO, no API charges, no deployments, no indexing or content changes.

## Engineering contribution
- `empire_os/search_intelligence/first_party_semantic_corpus.py` validates
  GSC first-party property and query/page schema and parses live page
  metadata. Source receipts are SHA-256; observed Google clicks/impressions
  remain query/page-scoped; unknown metrics are not invented.
- The initial live run surfaced real GSC `www.` URL aliases. Parser now
  accepts owned HTTP/HTTPS + www/apex variants for GSC *only*, preserving
  source URL in the query/page evidence receipt. Page canonical gates still
  require verified HTTPS apex. This does not assert the redirects are live.
- `scripts/review_live_first_party_semantic.py` is a bounded read-only CLI
  integrating the existing GSC API and exactly four known public site URLs.
  Produces reports to stdout; no persistent production data import.
- `tests/search_intelligence/test_first_party_semantic_corpus.py` includes
  first-party, stale URL alias, canonical, tenant-like domain, metrics and
  commercial-claim negative controls.

## Reproduce from isolated feature worktree
```sh
cd /home/ubuntu/empire_worktrees/seo_zero_cost_reader_20261018
/srv/empire_os/.venv/bin/python -m scripts.review_live_first_party_semantic \
    --start-date 2026-10-03 --end-date 2026-10-15
```

## Next meaningful revenue gap
GSC has not yet disclosed query/page measurements for the four commercial
pages in this time window. Continue first-party indexability, canonical-host,
internal-link and commercial CTA review, then revisit GSC after fresh indexing
and normal reporting lag. Prioritise existing original sector pages before
creating new URLs. Any user-intent/click/revenue claim needs its own source
evidence. Do not infer that a Google Search Console click is an accepted lead
or PPC payout.

## Embedding truth
Current active local model advertises `qwen2.5-coder:1.5b` and is *not*
validated as a retrieval embedding model. No dedicated embedding model was
discovered in the inspected production model paths. Hybrid semantic retrieval
still supports caller-supplied, same-model evidence-stamped vectors, but this
live review correctly operated with the **lexical fallback**.
Do not label these four topic clusters as embedding-based semantic measurements.

## Safety
Feature code only, worktree owner isolated. Existing Search Intelligence,
EmpireDB, production website, DataForSEO account, timers, payments, outbound,
MCP and ASTRA work unaffected. No scheduled execution. Approval required for
production deployment and future services.
