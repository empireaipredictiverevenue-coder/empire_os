# Empire AI — organic industry-to-revenue conversion handoff

**13 October 2026 · code-ready, site-publication NOT authorised**

## Direct production evidence (read-only)
- `https://empire-ai.co.uk/robots.txt` and `/sitemap.xml` returned HTTP 200; sitemap exposed 20 canonical candidate pages. The homepage, `/commercial`, `/buy`, the roofing and HVAC industry pages, and a published research campaign article returned HTTP 200 when checked.
- The existing US `/roofing` route is correctly held at `X-Robots-Tag: noindex, nofollow`; the new UK `/uk/roofing` editorial source remains HTTP 404 on the live gateway and must stay separate.
- The `/industries/roofing`, `/industries/hvac`, and published `/research/campaign_3438b6c3b110f941407ce1dd` pages contained **zero direct links to /buy or /commercial** in live retrieved HTML. Industry pages offered `mailto:founder@empire-ai.co.uk`, but that email address was not independently proven to be a functioning owned sales route.
- The existing `/commercial` enquiry form uses `/v1/checkout/commercial/interests` to collect buyer-initiated, consented nonbinding requests. At the readback, checkout health said `founder_led_commercial_interest_enabled=true`, `binding_order_creation_authorized=false`, `payment_proposal_authorized=false` and `payment_execution=false`.
- Existing first-party Google Search Console adapter returned `enabled=false, configured=false, available=false`. **No independently verified organic clicks, impressions, rankings or uplift** can be claimed from this inspection. No new connection or credential was made.

## Smallest shared-component change
Only `apps/empire-public-site/src/components/IndustryIntelligencePage.tsx` changes:
1. Replace two uncertain `mailto:` routes with the existing buyer-initiated `/commercial` form.
2. Place a `/buy` link immediately after the industry's data-product research examples.
3. Clearly distinguish **research applications** from currently listed and independently scoped sellable products; no promise of sector-specific deliverables, instant order, approved payment, revenue uplift or buyer capacity.

All six industry pages share this component: roofing, HVAC, solar, property, private equity and legal/mass tort. The independent UK MyJobQuote referral page, US Lead Smart page, marketing consent, checkout/payment providers and site navigation are unchanged.

## Independent release proof
- 36 scoped pytest checks passed for navigation, existing commercial enquiries and public gateway, one unrelated dependency deprecation warning.
- Full Next.js 16.3.5 Webpack **offline** production export compiled, type-checked and generated all 17 static pages in an isolated worktree using preinstalled dependencies; no npm installations, external images, font downloads or Vercel controls.
- Verified all six actual rendered `out/industries/*.html` files have exactly one `/buy` link, two `/commercial` links, no `mailto:` links and unchanged correct self-canonical.
- No production public site export, gateway route, CDN, DNS, service, timer, domain, email provider, outbound sends, traffic switch, payment or user data was modified. Source integration is not proof that search engines crawl, rank or bring traffic.

## Important immutable research campaign gate
Five already-public `/research/campaign_...` articles use `empire_os.owned_campaign_release.load_release` to SHA-256-bind the exact rendered HTML to verified release evidence. **Do not directly edit `owned_campaign_content.render_asset`** to add commercial links. That would invalidate the current manifests and can make all five URLs fail closed. If conversion paths on those articles are needed later, prepare a separate versioned campaign release with freshly reviewed copy, hashes and deployment evidence. Do not mutate a live release blindly.

## Remaining release and measurement gates
- Integrate only the audited shared-component source and regression test. Follow the existing website design owner's release process; the broader premium-site redesign is still separate and must not be overwritten.
- Independently build and review the final publication hash; use an approved site rollout and rollback. Do not publish the new UK affiliate route, increase indexing, enable consumer forms, or activate any phone/affiliate buyer route from this change.
- Once live with explicit publication authority, read back the public HTML for all six links and recheck that `/commercial` remains only a nonbinding enquiry.
- Add truthful consented first-party **aggregate** referral/impression-to-enquiry observation using existing approved instrumentation only when available. Do not interpret clicks as revenue. Count a sale only after genuine buyer agreement and independently verified settled revenue and fulfilment.

**Status:** Offline conversion improvement tested, prepared for controlled site release; no claim of additional visitors, enquiries, purchases or MRR.
