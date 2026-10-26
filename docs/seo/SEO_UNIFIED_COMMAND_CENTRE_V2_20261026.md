# EmpireOS SEO Command Centre V2 — original tool suite

**26 October 2026.** Build within the EXISTING private Founder Console and the EXISTING original Search Intelligence & SEO daily and weekly owners. No second analytics suite, crawler, browser bot, database, scheduler, paid traffic or publication authorization.

## Actual connected evidence

- First-party Google Search Console query/page history: latest original private `seo-visibility-YYYY-MM-DD.json` (read-only, 0600, original owner) with two separate sampled final periods. Includes real phrases, observed GSC average positions, sampled page exposures, valid page URLs, previous/current split and commercial thematic relevance. **GSC position does not mean an independently observed rank tracker position**.
- Original SEO action lifecycle: `seo-actions-YYYY-MM-DD.json` under original private daily index owner, with exact stable ID, owner, stage and source-linked resolution evidence. Source originally 32 actions and 8 resolutions. New workbench exposes an interactive filter for open/all/resolved jobs.
- 12 existing functional tool families inventoried in existing Founder UI: keyword explorer, rank history, competitor gap, on-page technical audit, cannibalisation candidates, backlinks, AEO/GEO, local grid, guarded content publishing, buyer attribution, MediaOS/YouTube and Jev/browser operator. **Only connected outputs have source-backed statistics**. Other modules remain distinct present-but-unverified capabilities, not invented metrics.
- Existing Founder SEO route `/founder/seo-operations`, no new endpoint or dashboard login. Added `seo-workbench.tsx` under the same original route and hardened original server-side reader in `page.tsx`.
- Editable controls **filter locally** only, do not mutate website, database or indexed pages. All links to source pages validate the exact `https://empire-ai.co.uk` or historical `https://www.empire-ai.co.uk` host and discard external URLs, credentials and query parameters.

## Production build and release custody

- Original running Founder private release: `/home/ubuntu/empire_releases/property_birmingham_private_stage_20261022_v3/web`, reviewed old build `S1a8PikANQu_TGMcw75JP`.
- Reviewed isolated candidate: `/home/ubuntu/empire_releases/seo_unified_tool_suite_candidate_20261026/web`, new Next.js Webpack production build `y_0Wp6TsIUjnSaJ_2thQ4`. Built from the exact original live release, changing only the existing SEO page and adding its SEO workbench component.
- Preflight and activation operator: `scripts/activate_founder_seo_tool_suite_v2_20261026.py`. Strict build + source SHA checks, unchanged owner SHA validation, original service WorkingDirectory check, two-file-only source promotion, original `.next` backup, health checks across 10 routes and automatic restore of old source+build if restart/health fails. Existing private Founder service restart only; the public website and Search API remain untouched.
- Candidate smoke: private preview on localhost:3109, with already owner-defined agency preview loopback guard. All checked Founder and department routes returned 200, V2 rendered real source values 7 keywords/21 sample impressions/8 resolutions.
- Release tests: `tests/test_activate_founder_seo_tool_suite_v2_20261026.py` (preflight owner drift, successful activation, rollback); plus original GSC and SEO lifecycle suites. 43 scoped tests passed.

### Operator activation, once exact source preflight still matches

```bash
cd /srv/empire_os

PYTHONPATH=. .venv/bin/python -B \
  -m scripts.activate_founder_seo_tool_suite_v2_20261026

sudo env PYTHONPATH=/srv/empire_os \
  /srv/empire_os/.venv/bin/python -B \
  -m scripts.activate_founder_seo_tool_suite_v2_20261026 --activate

curl -fsS http://127.0.0.1:3001/founder/seo-operations >/dev/null
```

Expected exact success: `ORIGINAL_FOUNDER_SEO_TOOL_SUITE_V2_LIVE_VERIFIED`. If any source changed during other workstreams, stop; reconcile original owner changes before a new reviewed build. Never bypass hashes/backup/restart tests.

## Next real platform investments

1. Genuine organic sessions or consented enquiries at source/page level in canonical Ops/CRM — sitewide counts aren't SEO conversion attribution.
2. Reliable permissioned independent SERP results through Search Fabric, preserving provider order, geography and quota; current Bing provider degraded, Brave billing-window held. Until verified, no competitor-rank estimates.
3. Verified live backlinks/referring domains rather than SEO authority scores generated from hypothetical sources.
4. Page change → live release receipt → GSC before/after → real CRM buyer acceptance and payment. Run through existing 5-minute Ops and daily/weekly SEO owner. No duplicate automations.
