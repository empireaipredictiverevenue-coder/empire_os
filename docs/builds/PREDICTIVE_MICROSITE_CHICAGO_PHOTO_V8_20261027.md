# Chicago Microsite V8 — Real photographic night background and owner handoff

Date: 27 October 2026
Branch: `agent/predictive-microsite-slopmonster-20261026`
Mode: PRIVATE, NOINDEX, OBSERVE. No production or payments.

## Work actually completed

The founder's approved design direction requires the real Chicago skyline / night-time city/water imagery, glowing blue glass cards and the approved canonical Empire AI orbital-A branding. V7 used an original vector skyline illustration that did not match the photography of the approved concept. **V8 fixes that actual visual gap in the existing factory renderer**, while preserving the five sourced Chicago roofing guidance cards and project checklist.

### Exact third-party image rights (separate from the original logo)
- Photographer: **Gael D**.
- Origin: https://unsplash.com/photos/a-river-running-through-a-city-at-night-IRMWK1Hv0_8 (Chicago skyline and river, uploaded July 29, 2024).
- Licence at source: **Unsplash License**, https://unsplash.com/license, allowing free use. No premium image, Getty image, scraped website mockup or re-generated logo is incorporated.
- Adaptation: one local WebP resize (1400px wide, libwebp quality 54), photographic dark/cobalt overlay applied at render time. Attribution to Gael D and both original photo + license links appear in the actual private preview footer.
- Original staged JPEG: `/home/ubuntu/empire_releases/predictive_microsite_photo_hero_v8_20261027/chicago_source.jpg`.
- Optimised WebP: `/home/ubuntu/empire_releases/predictive_microsite_photo_hero_v8_20261027/chicago_river_compact.webp`.
- Photo WebP SHA-256: `2c17ea093608a0fb16286c6b4c765574d3692fea0deafaca2ea34b56045e9a05`.
- Runtime requires `EMPIRE_MICROSITE_CHICAGO_HERO_PHOTO` pointing to this exact owner-staged asset. Reject missing, altered, oversized or symlinked input; it is **not published into the public Git repository or production site**.

### One canonical branding system
- Brand system contract: `/home/ubuntu/empire_releases/empire_brand_canonical_20261027/brand_contract.json` with hash `ead735b5e223a3b179a23965c1ff11dc67efb78b4cd4e71df9b60550872bc518`.
- Existing private orbital-A PNG from original brand owner remains separate and hash-verified; no AI-created logo or legacy brand fallback in this private rendered version.
- Photography does not grant authority for use of the separately governed brand image or publication.

### Exact V8 private page and QA
- `/home/ubuntu/empire_releases/predictive_microsite_photo_hero_v8_20261027/compact_preview/microsite_c4c5a13b626d293fe15c.preview.html`
- HTML SHA-256: `dc475bb34cad5c17e81dd4399326ec6a895b66661d1a3e59ade39e49814a3efd`.
- HTML 375,677 bytes, **within existing brand-owner 400KB offline QA cap**. First 300KB photo exceeded that cap, so image quality/size was reduced; original owner's limit and test were preserved.
- Browser-owner Chrome/Puppeteer receipt and actual 1440×900 desktop and 390×844 mobile screenshots:
  `/home/ubuntu/empire_releases/predictive_microsite_photo_hero_v8_20261027/compact_qa/`.
- QA: **BROWSER_QA_PASS**, one H1, one main, no horizontal overflow, CTA height 51.59px, zero forms, zero external network requests, `noindex,nofollow,noarchive`.
- First-party research source links: 5 official government references with no buyer/contractor offer, conversion, false revenue or paid claims.
- SlopMonster copy score remains **5/5**.
- Existing and new targeted regressions: **232 passed** (one existing AnyIO deprecation warning).

## Exact expected review / command
```bash
cd /home/ubuntu/empire_worktrees/predictive_microsite_factory_slopmonster_20261026
EMPIRE_AI_CANONICAL_BRAND_CONTRACT=/home/ubuntu/empire_releases/empire_brand_canonical_20261027/brand_contract.json \
EMPIRE_MICROSITE_PRIVATE_APPROVED_LOGO=/home/ubuntu/empire_worktrees/microsite_brand_owner_integration_rehearsal_20261027/empire_os/brand_assets/empire-ai-orbital-a-founder-board.png \
EMPIRE_MICROSITE_CHICAGO_HERO_PHOTO=/home/ubuntu/empire_releases/predictive_microsite_photo_hero_v8_20261027/chicago_river_compact.webp \
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /srv/empire_os/.venv/bin/python -B \
scripts/review_predictive_microsite_factory_20261026.py \
 --input tests/fixtures/chicago_city_roofing_official_research_pilot_20261027.json \
 --output-dir /home/ubuntu/empire_releases/predictive_microsite_photo_hero_v8_20261027/review_reproduction
```

## What is still NOT done
- The original SEO/content owner has not approved publishing or indexation; authentic exact keyword demand is unknown.
- The original brand/website owner must make an independent, exact-asset public distribution decision for canonical logo and the image attribution.
- The actual website publisher still verifies **five original campaigns** and needs an owner-approved extension to admit this one new candidate. Do not change that release gate in this marketing branch.
- No microsite has been released or measured. Website traffic, consented enquiries, CRM accepted leads and finance settlements remain **unverified/unknown**.
- No automated mass-geography microsite generation, buyer phone traffic, paid ads, additional agents, new database, task scheduler or original SEO worktree changes.

This is the real code/asset preview with a photographic hero, not an image-generated mockup or a live webpage.
