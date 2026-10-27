# EmpireOS Predictive Microsite Factory + SlopMonster V3

**Date:** 27 October 2026
**Branch:** `agent/predictive-microsite-slopmonster-20261026`
**Current scope:** privately staged, draft-only. No production site, SEO owner, database, buyer or outbound write.

## Completed code

- `empire_os/microsite_commercial_intelligence_v3.py` overlays independent commercial observations onto the original candidate factory. It reuses **the original** `lead_smart_coverage_reader.load_snapshot` and `lookup_zip` for observed Lead Smart ZIP coverage. It never converts a targeting row into guaranteed payout or a verified buyer route.
- The same module implements an optional exact-bound read from the **original** `PostgresPredictiveRegistryReader`, with its already-declared `empire_predictive_registry_reader` role. It requires the dedicated `EMPIRE_PREDICTIVE_REGISTRY_DSN` provided to an explicitly opted-in run. No new DB, tables, roles or credentials.
- The forecast overlay uses `DirectionalForecast` and `ForecastRegistryRecord` validation, including the original registry payload digest, exact forecast key, metric, dimensional key, market ID, territory area, area kind and keyword. Only named research metrics are supported. Freshness is bounded to 48 hours. A forecast remains a **research signal**, never a buyer payment or projected gross profit receipt.
- `scripts/review_predictive_microsite_factory_20261026.py` now supports `--observe-original-buyer-coverage` and `--read-original-forecast-registry`. Both are off by default. An explicit buyer ZIP signal or predictive forecast binding in the proposal is also required. Output: `commercial_research_review.json` along with private HTML, original GSC evidence and SlopMonster copy/design briefs.
- `empire_os/predictive_microsite_factory.py` renders the exact **existing site-owned Empire AI SVG logo** into offline previews as base64 (original brand asset read-only), records its SHA-256, and adds a responsive hero/evidence summary panel. All previews remain `noindex,nofollow,noarchive`, with no public forms, outbound activity, scripts or deployment.
- `tests/test_microsite_commercial_intelligence_v3_20261027.py` covers the original targeting semantics, expired sources, unsupported buyers, forecast tampering, wrong territory/keyword, malformed/double records, invalid metrics, CLI/private production read and refusal to use absent registry credentials.

## Live evidence review

Source: `/srv/empire_os/runtime/revenue/lead_smart/coverage/latest.json` — an **existing** source snapshot (not changed).

Observed on **2026-10-27 at 10:12 UTC**: 27,310 ZIP rows. Original `lookup_zip` reports covered targeting candidates for ZIPs `60601`, `60602` and `75001`; buyer route eligibility is false in each, and payout is not guaranteed. These are public territory research targets, not commercially accepting contractors, confirmed traffic destinations or realised lead revenue.

V3 sample stage:
`/home/ubuntu/empire_releases/predictive_microsite_factory_slopmonster_v3_20261027_stage`

Private candidate: `60601` roofing research preview, with actual source lookup. It is **HOLD_EVIDENCE** because GSC keyword demand is unknown, ZIP-to-metro match hasn't been independently linked, and a buyer route for the exact page hasn't been approved. It has a verified source digest, original-brand logo SHA-256 `45ae573d68a6d5ae87adc08f19f115f0a9e47c7106512ce73f9dd3e283d5dfee`, responsive layout metadata, SlopMonster 5/5, no form and no publication.

GSC: original 2026-10-26 first-party query/page receipt has only two query/page rows with **zero exact topic matches** among the four researched themes; the factory does not label these as ZIP-level demand.

Predictive Cloud V3: existing registry reader code is connected as an optional API in the factory; the worktree shell has **no `EMPIRE_PREDICTIVE_REGISTRY_DSN`**. No live forecast was read, no commercially verified forecast was attached, and the honest result is `FORECAST_NOT_BOUND`. Synthetic, digest-bound forecast integration tests passed; these are tests, not real forecast records.

Local model: prior one-shot existing `qwen2.5-coder:1.5b` rewrite timed out. It remains an optional reviewer, not an approved autonomous source of claims.

## Reproduce the safe ZIP research stage

```bash
cd /home/ubuntu/empire_worktrees/predictive_microsite_factory_slopmonster_20261026
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  scripts/review_predictive_microsite_factory_20261026.py \
  --input /home/ubuntu/empire_releases/predictive_microsite_factory_slopmonster_v3_20261027_stage/zip_research_input.json \
  --output-dir /home/ubuntu/empire_releases/predictive_microsite_factory_slopmonster_v3_20261027_stage \
  --gsc-receipt /home/ubuntu/empire_releases/seo_weekly_gsc_two_page_20261022/weekly_keyword_intent_2026-10-26.json \
  --observe-original-buyer-coverage
```

No live credentials are required for this command. The existing forecast reader is disabled unless `--read-original-forecast-registry` is explicitly requested **and** the dedicated read-only DSN is available to that process. Never print the DSN.

## Verification and next owner actions

- **93 focused regression tests passed** (one existing anyio/Starlette deprecation warning), and staged HTML SHA-256 matched the candidate manifest. No production changes.
- SEO/site owner to attach accurate indexed query/topic and locally substantiated geographic value, confirm market membership from genuine ZIP/postcode reference data and choose original useful asset vs duplicative page. Avoid site-spinning doorway networks or similar pages differing only by geography.
- Commercial owner to verify exact buyer territory, terms, available route and non-misleading CTA/consent. Neither a Lead Smart targeting coverage row nor a buyer's prior approval of another page authorizes this preview.
- Predictive owner to issue timestamped, calibration-reviewable, right-scoped forecast records to the existing registry and make the dedicated read-only role available. Do not create synthetic forecasts to obtain a green state.
- Website owner to run real browser screenshot, accessibility, CLS/INP/LCP and mobile QA on the **revised** logo/hero version. Prior screenshots were of V2; V3 screenshots are not completed on the server, where Chromium/Playwright are not installed.
- A governed original-site release may only follow independent authorisation from the site and SEO owners, without concurrent edits to their existing worktrees.

**No real buyer acceptance, paid lead, settlement, revenue, domain creation or public publication is claimed.**
