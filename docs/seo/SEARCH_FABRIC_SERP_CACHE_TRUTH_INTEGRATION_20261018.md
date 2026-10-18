# Empire AI Search Fabric — read-only SERP cache truth integrated with SEO
18 October 2026 | Existing Search Intelligence and marketing_growth

## Why this closes a real reporting gap
Search Fabric was present but the live Search Intelligence summary
correctly said INTEGRATION_PRESENT_OBSERVATION_UNVERIFIED. Earlier
specific buyer-intent Bing/DuckDuckGo searches returned no independently
usable SERP rows. Yet the owned Search Fabric cache contains a bounded
inventory of other old and recent lexical-filtered SERP envelopes.

The new feature reads that EXISTING cache, *without executing any search
or changing Search Fabric*. Its output is cache provenance and freshness
only, never independent Google keyword rank/demand evidence.

## Exact existing interfaces
- Existing cache store: /srv/empire_os/runtime/search/cache
- Existing writer and 24-hour TTL: empire_os/search_fabric/search.py
- New bounded read-only inventory:
  empire_os/search_intelligence/serp_cache_inventory.py
- One-shot operator:
  scripts/review_search_fabric_cache_inventory_20261018.py
- Existing unified SEO department operator extended:
  scripts/review_seo_department_integrated_20261018.py
- Tests:
  tests/search_intelligence/test_serp_cache_inventory_20261018.py,
  tests/test_search_department_integrated_20261018.py

Run:
  cd /srv/empire_os
  ./.venv/bin/python -m scripts.review_search_fabric_cache_inventory_20261018 --review-only
  ./.venv/bin/python -m scripts.review_seo_department_integrated_20261018 --review-only

## Observed local evidence
One read-only scan identified:
- 1,764 cache files (bounded under 2,500);
- 1,760 valid, hashed filename-linked cached envelopes;
- 4 invalid / unsupported envelopes;
- 87 quality-gated cached envelopes with timestamps within the
  configured 24-hour TTL;
- 1,673 older or future-timestamped envelopes classified as stale;
- fresh cache candidates: duckduckgo_html 53, bing_rss 18,
  bing_html 15, brave_web 1.

Cache recency is NOT publisher freshness or a Google Search SERP
observation. The reader does NOT recompute keyword rank, run source
providers, scrape search pages, inspect buyer data, send search queries,
buy API credits or access credentials. It never outputs raw query terms,
titles, snippets, result URLs, personally identifiable customer fields
or raw ranking positions.

The departmental output has separate fields for source cache freshness
and verified rankings, which remain FALSE. The pre-existing ranking gap
remains open until specific independently observed keyword, locale,
engine, position and timestamp evidence is available.

## Safety and engineering
The scan rejects symlinks, oversized files, unknown engines, cache-key
mismatch, missing lexical quality gate, malformed positions, invalid
timestamps and file-count overflow. It is bounded to 2,500 files,
64 KiB per file and 32 MiB cumulative file reads. Invalid envelopes
are counted but not promoted as evidence. A missing/unsafe root fails
closed, not as zero SERP demand.

No Search Intelligence service restart, systemd timer, second rank
tracker, API route, database table, network provider, paid feature,
outbound message, public site change or CRM mutation was introduced.

## Remaining SERP milestone
A source owner should validate a small set of real target buyer
queries with locale and engine attribution using an approved provider
and the existing Search Fabric. Record live positions and verification
quality; do not bypass upstream restrictions, reuse outdated cached
rankings as new, or conflate Bing/DDG ranks with Google positions.
