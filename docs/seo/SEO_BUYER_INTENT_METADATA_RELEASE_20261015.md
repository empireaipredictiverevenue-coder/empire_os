# Empire AI — roofing and solar organic search-result metadata release

**Owner:** existing EmpireOS SEO Director · **Date:** 15 October 2026 · **Scope:** precisely two existing B2B industry pages, their search descriptions and matching Open Graph metadata · **No PPC routing or paid traffic**

## Verified original buyer-page intent

The full, original roofing and solar content had already been publicly published and independently SHA-verified on 15 October 2026. However, their search-facing titles still used generic category labels (`ROOFING & RESTORATION | Empire AI` and `SOLAR & ENERGY | Empire AI`), while their descriptions did not reflect the published buyer-qualification material. This change aligns the metadata with existing visible first-party content, without claiming search rankings, accepted live call inventory or a signed advertiser payout.

| Page | New HTML title | New meta and Open Graph description |
| --- | --- | --- |
| `/industries/roofing` | Roofing Demand & Call Qualification \| Empire AI | Explore roofing demand, eligible service areas, first-party enquiry quality and how buyers define payable calls. Evidence-first commercial intelligence. |
| `/industries/solar` | Solar Demand & Referral Qualification \| Empire AI | Understand solar demand, installer coverage, qualified enquiries and the difference between organic clicks, accepted leads and paid referrals. |

Both pages retain their original one-H1 dark/cyan/green 3D design, buyer explanations, correct HTTPS apex self-canonical and link to the existing first-party `/commercial` form. Open Graph title/description now align with corresponding visible pages. Other industry `generateMetadata` fallbacks retain their previous title, description and Open Graph values.

Google Search Central recommends unique, descriptive title links and relevant page-specific meta descriptions; neither guarantees Google will display those exact strings, improve rankings or yield clicks. Sources:
- https://developers.google.com/search/docs/appearance/title-link
- https://developers.google.com/search/docs/appearance/snippet

## Engineering / governance

Only `apps/empire-public-site/src/app/industries/[slug]/page.tsx` changes website source. Original Search Console/SEO publishing code is reused; `seo_publication_impact_review.py` and its one-shot observer now accept an **optional, precisely scoped** third receipt for roofing and solar metadata only. If a later live HTML hash changes but no matching evidence receipt exists, the report rejects it rather than silently calling the page verified.

Isolated Next.js Webpack build of **all 17 static routes succeeded** with TypeScript checks enabled. Verified generated HTML: both titles, descriptions and Open Graph values match expected content; other industry and Commercial/Predictive Revenue metadata remains unchanged. The build generated eight additional immutable static assets with no file-name SHA collision. Unit and integration tests cover the two original page texts, single H1, canonical, existing business CTA, consumer `/roofing` noindex and scorecard third-receipt acceptance/denial.

**Publication procedure:** Use the existing reviewed, atomic static-release operator with a strict two-page wrapper, prior HTTPS release receipt hash checks, private dated rollback backup, eight noncolliding versioned assets, exact live gateway and public HTTPS response hashes. Do not modify/restart the public gateway or change Cloudflare, DNS, checkout, OAuth, live call routing, tenant/database, CRM contacts or paid media. Retain original archived evidence.

**Measurement truth:** Current Search Console 15 Sep–13 Oct baseline of 83 impressions and one organic click predates this change; not a post-release uplift. The existing SEO Research Council should monitor processing-lag-adjusted future Google Search Console observations and canonical first-party commercial enquiry receipts. No paid publisher CPC or pay-per-call event can be inferred from search data.
