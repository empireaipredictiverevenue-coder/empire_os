# Empire AI — Roofing and solar search metadata live proof

**15 October 2026 · First-party SEO Director owner review · Production source commit `bd17b45f` · NO paid clicks / checkout / outbound**

## Publicly verified release

The original site source was compiled into all **17 static Next.js routes** in an isolated worktree. Its roofing and solar metadata now accurately describes the real, previously published first-party buyer education. New titles, descriptions and Open Graph snippets are visible **in public HTTPS HTML**, not merely source code.

| Public URL | Search title after release | Release SHA-256 prefix | Live verification |
| --- | --- | --- | --- |
| https://empire-ai.co.uk/industries/roofing | Roofing Demand & Call Qualification \| Empire AI | `9be963f83bf7b8fe` | HTTP 200; exact HTML SHA, self-canonical and original first-party commercial link |
| https://empire-ai.co.uk/industries/solar | Solar Demand & Referral Qualification \| Empire AI | `12e04a48ac5e8056` | HTTP 200; exact HTML SHA, self-canonical and original first-party commercial link |

A narrow two-page one-shot deploy reused the existing previously tested static release operator (pinned SHA-256 `eaeb63082df49e55f1df3eb9f633667a1b034003e0b0dcc89587b4edeb8eca76`), with strict production/review commits, previous page SHA checks, no asset collision and fail-closed semantics. **Eight new immutable assets** returned HTTP 200 and matched their live bytes to local SHA-256. Private rollback backups include exact original HTML and release manifest; the receipt is:

`/srv/empire_os/runtime/public_website/seo_buyer_metadata_two_pages_20261015_release_v1/release_receipt.json`

This scope did not touch or restart `empire-public-gateway.service`; did not modify Cloudflare, the canonical-host redirect, contact intake, checkout, the live consumer `/roofing` route or any payment/click/outbound systems. All eight protected HTML files matched pre-release hashes: homepage, `/buy`, `/commercial`, `/predictive-revenue`, industry HVAC/property/legal and consumer `/roofing`. The latter still serves `noindex`.

## Independent measurement revalidation

The existing first-party SEO Director post-release reviewer was updated to accept a **third, exact two-page metadata-release receipt**, overlaying the original industry HTML hashes only if the receipt validates. Re-review against the publicly served pages returned:

- `buyer_intent_search_metadata_release_verified = true`
- `seo_pages_verified_public = 4` (two industry pages and both previously released commercial pages)
- `status = PRE_PUBLICATION_SEARCH_BASELINE_ONLY`
- Google Search Console 15 Sep–13 Oct sitewide **83 impressions and 1 organic click**; the observed query/page subset is incomplete and predates today's pages
- `buyer_capacity_status = NO_VERIFIED_COMMERCIAL_CAPACITY`
- `publisher_pay_per_click_live = false`
- `www_host_redirect_review_needed = true`
- **354 production regression tests passed** after the public release, with one existing unrelated Starlette/AnyIO deprecation warning

**Google Search Central sources:** https://developers.google.com/search/docs/appearance/title-link and https://developers.google.com/search/docs/appearance/snippet . Search title and meta changes do **not guarantee ranking, indexation, displayed title text, CTR, conversions or collected revenue**. The current observations cannot attribute any post-publication gain.

## Remaining work for the already enabled Friday SEO Research Council

Prioritise measurement of the four existing pages after GSC processing lag, including sitewide vs anonymised query/page counts, and identify original link-worthy research to earn organic references without creating mass doorway pages. Avoid republishing the same buyer explanations. The `www` to non-www permanent-redirect change still needs the **existing gateway owner's** explicit integration: another agent's uncommitted legal-route changes in `empire_os/public_gateway.py` were preserved, so the canonical policy remains review-only and unmounted. A signed downstream buyer agreement with eligible territories, traffic source, billable event, consumer consent and settlement evidence is separately required before any PPC / PPL / pay-per-call monetisation.

**No additional server, API service, model spend, timer, ads or buyer contact actions were created.**
