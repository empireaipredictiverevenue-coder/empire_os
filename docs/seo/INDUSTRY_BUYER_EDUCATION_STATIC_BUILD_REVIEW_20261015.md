# Empire AI — original buyer-facing SEO content integrated into existing site source

**Date:** 15 October 2026 · **Status:** CODE BUILT / STATIC EXPORT VERIFIED / NOT YET LIVE · **Owners:** SEO, Astra website owner and Founder commercial gate

## Why this helps actual organic-to-commercial acquisition

The current first-party industry pages are visually strong, but before this change they explain market signals and forecasts without answering the buyer-terms questions most relevant to qualified roofing/solar commercial search intent. This feature adds original, crawlable, factual B2B educational content while preserving the existing premium visual identity and *already consented* `/commercial` enquiry form. No alternate SEO engine, form, API, systemd timer, CDN rule, lead broker or click tracker is created.

### Exact source scope

- `apps/empire-public-site/src/lib/industry-buying-editorial.ts`: structured original education for **roofing** and **solar** only; jobs, source quality, ZIP/postcode/state coverage, buyer capacity, accepted call/lead/installation events, consent, disclosures and settlement. Explicitly distinguishes Google Search Console inbound visits from outbound payable CPC and recorded revenue. No invented buyers or payout rates.
- `apps/empire-public-site/src/components/IndustryBuyerEditorialSection.tsx`: matching original Empire AI dark/green/cyan design; accessible semantic `<section>`, one existing H1 per route, separate H2/H3 hierarchy, bulleted evidence, visible frequently asked questions and the existing `/commercial` CTA. No affiliate URL, phone links, cookie instrumentation, new form or script.
- `apps/empire-public-site/src/components/IndustryIntelligencePage.tsx`: seven-line additive integration. Existing homepage, industry card graphics, hero, product claims, footer, other six industries, analytics and form remain unchanged.
- `scripts/verify_owned_industry_editorial_build.py` and `tests/test_owned_industry_editorial_build.py`: fail-closed, bounded static-export checking of crawlable text, self-canonical, one H1, `/commercial` route, unrelated industries and `noindex` on the *separate consumer* `/roofing` page.

### Verified isolated build (not a public-site deployment)

- Next.js v16.3.5 `next build --webpack`: **compiled, typechecked and generated all 17 static routes successfully** from an isolated Git worktree. Turbopack rejected an external `node_modules` worktree symlink, a sandbox topology error rather than a source TypeScript error; Webpack successfully built without changing the site's production dependencies. The temporary link was removed after the build.
- Generated `out/industries/roofing.html` and `out/industries/solar.html`: original text is present in **server-rendered HTML** (not reliant on JS or hidden SEO stuffing), existing page title/H1 count 1, self-canonical `https://empire-ai.co.uk/industries/{slug}`, and links to the existing `/commercial` first-party founder consent form.
- `out/industries/hvac.html` and `out/industries/property.html`: no injected roofing/solar editorial content; original existing cards remain.
- `out/roofing.html`: **noindex remains on** for the buyer-gated consumer page. No third-party/affiliate click redirect, direct-dial CTA or automatic lead transfer.
- Verified with local static-export helper and **40 relevant Python tests passing** in isolation, in addition to Next.js build. Neither test is evidence of Google indexing or buyer approval.

### Release gates and next measurable outcomes

1. This commit is **source-code only**. The live FastAPI gateway serves already-built `apps/empire-public-site/out/` files; **do not copy the isolated `out/` directory or restart the gateway** without explicit website-owner/founder approval, verification of concurrent Astra visual work, legal/editorial review, rollout hash manifest and route smoke tests.
2. Before any public rebuild, confirm legal/content claims, site typography/a11y, current Astra 3D design and original content consistency. Do not silently activate `/roofing`, remove `noindex`, assert partner approval or introduce a B2C enquiry collection flow.
3. Measure actual page results in the existing Google Search Console `sc-domain:empire-ai.co.uk`. Use equal-period daily impressions/clicks from connected Search Intelligence, with query/page incompleteness acknowledged. Track commercial enquiries only from legitimate, consented first-party evidence and reconcile against confirmed founder CRM; do **not** label a GSC click as a PPC commission.
4. The first paid outcome still needs a signed US/UK buyer agreement with specific corridor, traffic-source approval, billable event, settlement rules and matching compliance. No PPC advertising spend or affiliate click publisher product activated.

**No new server, service, outbound messages, browser tracking, fees, payments or production website publication occurred in this change.**
