# Chicago ASTRA V16 — Source-backed final HTML export review

**Date:** 27 October 2026
**Owner:** original ASTRA website implementation and source/SEO reviewer
**Branch:** `review/chicago-original-gateway-owner-20261027`
**State:** PRIVATE PAGE-EXPORT REVIEW, not a new publishing system, public deployment or owner's signed approval.

## Actual defects found and corrected

The original V10 standalone preview was aesthetically approved for further development, but programmatic inspection of the exact HTML revealed three release-quality problems:

1. Its `<title>` contained nested `<span class="hero-title-...">` presentation markup. The HTML title must be **plain text**. The staged export uses `Chicago reroofing: permits, licensing and scope checks | Empire AI Research`.
2. Its meta description was cut off at a character limit and ended abruptly `no contractor`. The staged export now has a complete 135-character factual description: `Chicago reroofing research: check permit eligibility, contractor licensing, and project scope against official city and state guidance.`
3. Styled segments inside `<h1>` ran `Chicago reroofing:permits` together without a space. The export preserves the styled two-span hero but adds an actual inter-span space.

**All three substitutions are exact-match and permitted only for a hash-verified original V10 source page.** This is an original-site-owner export *delta*, not a new Marketing Factory master source, second campaign ID, or change to existing release evidence. The original draft remains immutable and can be reconstructed.

## Source/deliverable evidence

- Original source preview candidate ID: `microsite_c4c5a13b626d293fe15c`.
- Original source preview SHA-256: `3ee2f8d08d12d306ab3842b3cb5b041d34fb340f2f6a8d8a898821b2200293a0` (399,801 bytes).
- **Corrected owner-review export HTML SHA-256:** `93c9f75a56b93cf4fde40656d177d734bf2814afd39ffe84bfd4d71555b15275` (399,699 bytes). Both source and exported hashes are separately captured to allow the original controlled website release receipt to link the approved source to the site-export bytes.
- Private stage: `/home/ubuntu/empire_releases/chicago_original_owner_metadata_review_20261027/`.
- Export: `chicago_owner_review_export.html`; receipt `owner_export_receipt.json`.
- Desktop/mobile source-owner Chromium QA of corrected HTML: **BROWSER_QA_PASS**, 1440×900 and 390×844, original logo loaded, single H1/main, 51.59px CTA, no forms/overflow, no external requests; receipt and screenshots in `browser_qa/`.
- Original full-source photographic 3840×2160 QA of corrected copy: **NATIVE_4K_QA_PASS**, zero network requests, five evidence notes, five steps, two photographic heroes; expanded master-photo QA hash `cffb292ff59e07f561c3838754f42b788cbdf00b413fa4c47f5ae89bd2aa89b9`, receipts/screenshots in `native4k_qa/`. The public candidate does **not** acquire automatic permission to ship these privately held master images.

## Source/rights findings for SEO and branding owner

- All five original first-party source links were successfully fetched from EmpireOS with HTTP 200 on 27 October 2026: City of Chicago Express Permit eligibility; City permit application instructions; Chicago permit-application public status help; Illinois IDFPR licence lookup; US Census ZCTA guidance.
- The City of Chicago eligibility page explicitly covers reroofing repairs up to 25% of roof area, roof recover over one existing covering, nonstructural replacement, and professional drawing/evaluation exceptions. Its Chicago-government page and the separate Chicago permit-history help were also independently checked with external web evidence on this date.
- The two individual Unsplash photo-source URLs and Unsplash licensing URL returned HTTP 401 from the **EmpireOS server's direct client**, but the standard Unsplash license is accessible from a separate web browser and broadly permits commercial and noncommercial use. Do **not** misstate this as a universal photo-source 404 or as independent title/ownership verification; original brand/media owner still needs to verify provenance and original image reuse permissions.
- The roofing worksite visual is explicitly labelled *illustrative Houston, TX* and must not be presented as a Chicago contractor/client.
- Canonical orbital-A raster is owner-custodied, not an unrestricted publicly redistributable artwork. Original native vector rights remain unverified.

## Site-owner follow-through

The existing draft PR #148 adds a strictly owner-approved one-asset route fallback to the five original releases, and V15 removes the first-deployment/readback circularity. It must stay a **draft** until original SEO/source, brand/photo rights, and ASTRA site-owner sign-offs exist.

After independent original-owner approval, stage the site export with the exact SHA above and issue an owner-custodied *staged HTML* receipt, not a fabricated `site_owner_live_readback_verified` flag. Only after first authorised publication can the V15 original HTTP verifier check the actual public Chicago page and all five incumbent pages.

No production files, paid ads, phone routing, lead forms or revenue records were changed.
