# EmpireOS — Semrush/Ahrefs-style first-party keyword visibility V1

**26 October 2026.** Continue the ORIGINAL SEO/AEO/GEO department, not a new SaaS application, Search API, database or scheduler.

## Benchmark

Semrush/Ahrefs feature families being incrementally built inside EmpireOS: keyword universe and question clustering, current SERP/rank monitoring, competitors and content gaps, site audit, technical on-page improvements, backlinks/authority, local search, AEO/GEO AI visibility, original content/Media OS, page indexing, Google Search Console, client sites and real funnel-to-revenue. No paid ads, links, provider keys or mass publication.

## This release — real first-party visibility

- `empire_os/search_intelligence/seo_visibility_v1.py`: exact owned-domain **query+page** Google Search Console data from two disjoint **finalized 10-day windows**, reported as two different samples rather than full-site traffic. Keyword question and GSC page exposures with source-preserved URLs, clicks, impressions and GSC weighted average position.
- `scripts/review_original_gsc_visibility_v1_20261026.py`: two bounded loopback calls to the ORIGINAL Search Intelligence API `127.0.0.1:8771/v1/search/search-console/observations`. At most 250 query/page rows per window; a full/possibly truncated window is **held**. Fixed URL+schema + counts and metrics validation; no live competitor-provider calls.
- Run under the EXISTING daily Google Index SEO owner `scripts/review_daily_original_google_index_20261026.py --write-daily`; optional fail-soft reporter is invoked only on primary owner success. Original site/index lifecycle receipt remains unchanged on error.
- Write-only to original owner-private `/home/ubuntu/empire_releases/seo_daily_index_status_20261026/seo-visibility-YYYY-MM-DD.json` (0600, O_EXCL, file lock). Repeated daily attempts reuse the immutable receipt **without repeat API calls**.
- Current v1 does **not** claim exact SERP rank, monthly search volume, keyword difficulty, a current redirect problem, competitor traffic, actual organic sessions, visitors or revenue. GSC query/page data is sampled and may omit anonymized terms. Neither two-city query overlap nor www/apex historical split is automatically cannibalisation.
- Tested query sample for final windows 3–12 Oct vs 13–22 Oct had historical brand alias appearances, multiple antenna-install AEO city pages for a query, one actual long-tail B2B TAM question, no verified organic paying buyer. Each is an observation for **the existing original SEO owner** to evaluate.
- Existing `rank_history.py`, `cannibalisation.py`, `competitor_gap.py`, `backlinks.py`, `ai_visibility.py`, `local_visibility.py` and the existing Founder `/founder/seo-operations` page remain intact. Do not fabricate data to fill other feature families.
- Next UI owner task: surface latest private `seo-visibility-*.json` in **existing** Founder SEO Operations page, with source badges separating GSC average position from genuine independent daily SERP rankings. Use original Next.js stage/backup/release and do not overwrite another agent's running Founder build.

## Run

```bash
cd /srv/empire_os

# Read-only query comparisons; does not create an artifact:
PYTHONPATH=. .venv/bin/python -B -m scripts.review_original_gsc_visibility_v1_20261026

# Same existing daily owner: writes private immutable evidence only:
PYTHONPATH=. .venv/bin/python -B scripts/review_daily_original_google_index_20261026.py --write-daily
```

**Security:** no extra database, autonomous publication, outbound email, paid SERP scraping, browser proxy rotation, fabricated market rank, Google indexing submissions or financial movement. Future third-party rank monitoring must use genuine permissioned evidence with per-provider source-quality and cost controls.
