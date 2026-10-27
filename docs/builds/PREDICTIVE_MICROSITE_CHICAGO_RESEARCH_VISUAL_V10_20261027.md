# Chicago Microsite V10 — Research Section Visual Density Revision

**Date:** 27 October 2026
**Branch:** `agent/predictive-microsite-slopmonster-20261026`
**Status:** PRIVATE DESIGN REVIEW — `HOLD_EVIDENCE`, not deployed.

## Founder feedback addressed
Founder: *"the second section looks empoty comapred to the top section"*. V9's Chicago photographic hero had stronger scene depth, lighting and density than the plain-navy research section. **V10 directly fixes that in the original first-party HTML generator** rather than designing a separate mockup or creating a parallel website.

### Code delta
- Reuses the exact hash-pinned **Chicago skyline photo already embedded in the page**, as a faint backdrop beneath the source notes. The asset is embedded **once**, referenced through existing CSS variable `--chicago-city-image`; zero extra web requests or image license changes.
- Adds layered, restrained cyan and cobalt ambient lighting, a lit section eyebrow, a readable on-image research header, tighter transitions and stronger photograph-card borders and shadows.
- Adds a three-cell source-confidence strip tied to actual content: **dynamic number of reference notes**, two existing research pathways, and **research-only/no-sales-claims** wording. Never infer buyer capacity or keyword market volume.
- Preserves existing photographic roofing and Chicago permit pathways with correct source and Houston illustrative-worksite attribution.
- Keeps official government-source links, evidence and five-step checklist unchanged. No new factual/commercial claims, CSS libraries, scripts, forms, maps, trackers, timers, routes or new agents.
- Responsive CSS scales the new research background / evidence strip to mobile and native 4K.

### Actual QA receipts and original requirements
- Exact final stage: `/home/ubuntu/empire_releases/predictive_microsite_research_depth_v10_FINAL_20261027`
- Original owner's private standalone preview: `microsite_c4c5a13b626d293fe15c.preview.html`.
- SHA-256: `3ee2f8d08d12d306ab3842b3cb5b041d34fb340f2f6a8d8a898821b2200293a0`, **399,801 bytes** under original QA tool's strict 400,000 byte ceiling (CSS compacted without changing the test or cap).
- Original owner Chromium/Puppeteer **BROWSER_QA_PASS**: 1440×900 desktop and 390×844 mobile, no horizontal overflow, one H1/main, no forms, noindex, original owner logo hash checks, 51.59px CTA height, zero external web requests. Screenshots and receipt under `browser_qa/`.
- Native **3840×2160** V10 photo-source render also passed using both 4K master photo assets. Evidence receipt and screenshots were generated in the earlier V10 visual validation stage before the final dynamic-count/wording cleanup; no structural CSS change since this check.
- SlopMonster: 5/5.
- Original factory + new V10 regressions: **239 passed**, one unrelated existing AnyIO deprecation warning.
- Original five deployed research campaigns untouched. Production `/srv/empire_os` branch untouched.

### Still held for original owners
Original SEO content/publication decision, brand-logo public distribution, existing website owner's distinct release and readback approval. The design may be ready for founder *visual* review; **publication, indexing, buyer acceptance, revenue and real traffic are not verified**. Keep the original issue #138 and single website release owner. Do not claim live site URL.
