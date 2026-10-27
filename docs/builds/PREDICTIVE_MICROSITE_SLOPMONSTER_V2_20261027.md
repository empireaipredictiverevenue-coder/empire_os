# Predictive Microsite Factory + SlopMonster V2 — Evidence, copy and visual QA

**Date:** 27 October 2026
**Worktree:** `/home/ubuntu/empire_worktrees/predictive_microsite_factory_slopmonster_20261026`
**Branch:** `agent/predictive-microsite-slopmonster-20261026`
**Scope:** Draft-only integration. Original SEO, website, ASTRA runtime, CRM and finance files untouched.

## What's actually implemented

1. **Original GSC receipt bridge:** `empire_os/microsite_first_party_gsc_bridge.py` validates the SEO-owned weekly receipt and matches *exact* observed query/page signals to factory candidates. Never maps a property ZIP from an owned-domain query, converts impressions into market volume, or asserts buyer capacity. Reads a caller-selected original report. Rejects malformed authoritative flags.
2. **SlopMonster copy revisions:** `empire_os/microsite_copy_revision.py` reviews revised headline/subhead/summary while keeping market, product, keyword, facts, sources, offer and identity immutable. Creates a diff and scores original vs proposed text. Flags high-risk claims, new numeric claims, URLs or embedded HTML. Successful reviews remain draft editorial proposals, not release approvals.
3. **Local optional model:** `empire_os/microsite_local_copy_adapter.py` can request draft JSON copy from *existing* local llama.cpp `127.0.0.1:11435` using model `qwen2.5-coder:1.5b`. Bounded response; no arbitrary endpoint or external AI requests. Response treated as untrusted input and passed through revision checks. Optional because model may be slow or unreliable.
4. **One CLI:** the original `scripts/review_predictive_microsite_factory_20261026.py` now accepts `--gsc-receipt` (original SEO owner folder only) and `--local-rewrite-first` (explicit one-off invocation). Generates private HTML previews, manifests, source evidence projections and optional copy review reports. No new services or DB.
5. **Portable browser QA:** `scripts/review_microsite_browser_20261027.py` can use installed Playwright/Chromium for offline 1440px desktop and 390px mobile screenshots, mobile overflow detection, one H1/main, and CTA touch height. It aborts network requests, requires preview noindex, outputs a receipt. On the production server, neither Chromium nor Playwright is installed, so it correctly returns `BROWSER_QA_UNAVAILABLE`. No auto-installation/root changes.
6. **Regression tests:** `tests/test_microsite_source_and_copy_v2_20261027.py` covers real receipt schema, forged GSC authority, exact matching, unverified geographic demand, protected copy fields and mock-model outputs.

## Current evidence and results

- Actual source used: `/home/ubuntu/empire_releases/seo_weekly_gsc_two_page_20261022/weekly_keyword_intent_2026-10-26.json`.
- The source reported **two first-party query/page rows**, **zero exact matches** across the four original research themes. No geographic search demand, lead count or money inferred.
- Stage root: `/home/ubuntu/empire_releases/predictive_microsite_factory_slopmonster_v2_20261027_stage/`. Two reviewed HTML previews, both `HOLD_EVIDENCE` due to absent keyword scoring evidence; matching receipt saved.
- Optional one-time existing local inference call timed out after the configured 18s. Result `HOLD_LOCAL_MODEL_UNAVAILABLE`. No generated copy accepted, no upstream/outbound calls, no code or DB writes.
- Desktop/mobile Chromium rendering **was executed on a separate controlled QA environment against the exact Chicago preview bytes** (SHA-256 `d7765ec292b7677e71518144a64acffdc6acfa17a441ebfe982b6ab877c71035`). At 1440×900 and 390×844: one H1, no horizontal overflow and a CTA height about 49.6px. Screenshots were saved in the testing environment, not on the EmpireOS server. This is not a full accessibility or performance audit.
- Focused source/copy/factory/keyword tests: **73 passed**, one existing anyio deprecation warning. Existing site files and SEO routes unchanged.

## Reproduce staging on EmpireOS

```bash
WT=/home/ubuntu/empire_worktrees/predictive_microsite_factory_slopmonster_20261026
cd "$WT"
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /srv/empire_os/.venv/bin/python -B -m pytest -q -p no:cacheprovider \
  tests/test_microsite_source_and_copy_v2_20261027.py \
  tests/test_predictive_microsite_factory_20261026.py \
  tests/test_keyword_universe.py tests/test_semantic_keyword_search.py \
  tests/test_advertising_landing_feedback.py

PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /srv/empire_os/.venv/bin/python -B \
  scripts/review_predictive_microsite_factory_20261026.py \
  --input tests/fixtures/predictive_microsite_factory_sample_20261026.json \
  --output-dir /home/ubuntu/empire_releases/predictive_microsite_factory_slopmonster_v2_20261027_stage \
  --gsc-receipt /home/ubuntu/empire_releases/seo_weekly_gsc_two_page_20261022/weekly_keyword_intent_2026-10-26.json
```

To additionally **request** one local-model rewrite, add `--local-rewrite-first`. It is optional and never publishes. Do not run in an automated schedule without measuring latency.

## Implementation-owner handoff

- Reuse actual Predictive Cloud issue/forecast identity and economic feedback when source rights and evidence contracts permit. Currently source bridge covers the original keyword universe and first-party GSC observations, **not** a verified working multi-site conversion loop.
- Install or supply a Playwright worker controlled by the current site owner, not a new root daemon. Ensure screenshots/structured receipts are reviewed and cross-checked against intended deployment assets.
- Review official Empire AI logo asset integration and next-generation visual design while respecting the flagship site's design lock. Current standalone HTML is a branded **draft**, not premium flagship acceptance.
- Test copy rewriting against a stronger approved model where appropriate; do not trust the 1.5B coder to autonomously assert real business facts.
- Connect only to original marketing/ASTRA/source owners; do not deploy into the active SEO workstream or publish geo doorway domains.
- Attach a real approved service/offer, accurate local inventory, sourced useful content, consent, measurement, unique domain/page strategy and owner approval before enabling public publishing or forms.
