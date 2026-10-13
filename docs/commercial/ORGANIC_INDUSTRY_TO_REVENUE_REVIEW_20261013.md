# Empire AI — organic industry-to-revenue conversion handoff

**13 October 2026 · code-ready, site-publication NOT authorised**

## Direct production evidence (read-only)
- `https://empire-ai.co.uk/robots.txt` and `/sitemap.xml` returned HTTP 200; sitemap exposed 20 canonical candidate pages. The homepage, `/commercial`, `/buy`, the roofing and HVAC industry pages, and a published research campaign article returned HTTP 200 when checked.
- The existing US `/roofing` route is correctly held at `X-Robots-Tag: noindex, nofollow`; the new UK `/uk/roofing` editorial source remains HTTP 404 on the live gateway and must stay separate.
- The `/industries/roofing`, `/industries/hvac`, and published `/research/campaign_3438b6c3b110f941407ce1dd` pages contained **zero direct links to /buy or /commercial** in live retrieved HTML. Industry pages offered `mailto:founder@empire-ai.co.uk`, but that email address was not independently proven to be a functioning owned sales route.
- The existing `/commercial` enquiry form uses `/v1/checkout/commercial/interests` to collect buyer-initiated, consented nonbinding requests. At the readback, checkout health said `founder_led_commercial_interest_enabled=true`, `binding_order_creation_authorized=false`, `payment_proposal_authorized=false` and `payment_execution=false`.
- **Correction to the initial unconfigured-shell probe:** the first terminal-only check misleadingly reported `enabled=false, configured=false, available=false` because it did not inherit the protected Search Intelligence service environment. The already-running `127.0.0.1:8771/v1/search/search-console/status` API was independently verified on 13 October and reports `enabled=true, configured=true, available=true, reason=ready` for `sc-domain:empire-ai.co.uk`. The authenticated read-only Google API returned **40 site-wide impressions and 1 organic click for 1–11 October**; this neither identifies the click's page nor proves any attributable enquiries or sales. No new connection, activation, credential or paid service was created.

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


## Verified canonical / historical-page observations (13 October)
- Public requests to all four homepage variants — `http://www.empire-ai.co.uk/`, `https://www.empire-ai.co.uk/`, `http://empire-ai.co.uk/` and `https://empire-ai.co.uk/` — returned HTTP 200 **without an HTTP redirect**. Their HTML canonical links correctly name `https://empire-ai.co.uk`. This is a concrete duplication/URL-consolidation improvement opportunity, not evidence that Google Search Console itself is disabled.
- Five legacy AEO routes visible in privacy-limited Google query/page reports (`/aeo/antenna-install/EUG/`, `/aeo/antenna-install/FAR/`, `/aeo/leak-detection/DAL/`, `/aeo/bathroom-remodel/POR`, `/aeo/kitchen-remodel/LON/`) currently return **HTTP 404**. Historical impressions are not evidence that the current live pages exist or are qualified product landing pages.
- Before any Cloudflare/Tunnel HTTP 301/308 redirect or legacy URL remediation, inventory the exact approved hostnames, routes, potential webhook/agent/affiliates and canonical headers; preserve query parameters and limit changes to browser-facing public routes. **No DNS, redirect rule, service restart, Search Console setting, sitemap publication or AEO release mutation was authorised by this read-only finding.**
- An independent October 12 report already recorded the **37 impressions/1 click** baseline through October 10 at `runtime/business_completion/ORGANIC_REVENUE_BASELINE_REPORT_2026-10-12.md`. Don't repeat claims that Google access was never set up. The small follow-up extends the reporting window by one day, not a new activation.

## 13 October evening conversion-release verification (production unchanged)
A fresh **six-route live HTTP comparison** checked `/industries/roofing`, `/industries/hvac`, `/industries/solar`, `/industries/property`, `/industries/private-equity` and `/industries/legal-mass-tort` on `https://empire-ai.co.uk`. All returned **HTTP 200**, and each live HTML response contained exactly **0 `href="/buy"` links**, **0 `href="/commercial"` links**, and **2 `mailto:founder@empire-ai.co.uk` occurrences**. This is **actual live conversion leakage**, not a missing feature request.

The current main-branch shared component **already contains** `/commercial` in the hero and lower CTA and `/buy` after research examples, originating in existing commit **`fa13da52`**. Do NOT reimplement or cherry-pick the same code again. The live public HTML is lagging behind committed source. A new scoped read-only regression of `tests/test_public_industry_commercial_navigation.py`, `tests/test_public_commercial_sales.py` and `tests/test_first_party_sales_interest.py` yielded **33 passed, 1 skipped**, one external dependency deprecation warning. This does not prove production rendering has been updated.

**Smallest next release:** hand source commit `fa13da52`, current static export and these exact six route comparison facts to the already-designated flagship website release owner ASTRA. Use its active release/rollback process to build once in its isolated worktree, verify the six generated pages and branded-design compatibility, and publish only after exact public site activation approval. Do not overwrite the ongoing redesign, manually alter hashed assets, change Cloudflare/DNS, restart unrelated services, touch Lead Smart or affiliate call routes, or claim SEO clicks/purchases from successful HTTP status.

**Acceptance after authorised publication:** all six live canonical industry pages return HTTP 200 and visibly link to the existing functional `/commercial` nonbinding enquiry and `/buy` offer journeys; deprecated unknown `founder@` mailto routes gone; site consent/negative-path tests remain green; keep payment, signatures, checkout, indexing and consumer call activation unchanged. Observe only genuine conversion receipts in existing EmpireDB and track buyer-to-sale outcomes. Until then, classify **SOURCE_READY / LIVE_CONVERSION_LINKS_MISSING**.

## LIVE six-industry conversion CTA release — 13 October 2026, 21:49 UTC

**Status: SIX_INDUSTRY_CTA_ROUTES_LIVE_VERIFIED (not full website completion).** Founder requested continuation immediately after the specific six-page controlled-publication proposal. Exact scope: existing `/industries/{roofing,hvac,solar,property,private-equity,legal-mass-tort}` static exports **only**, plus 21 new content-hashed supporting Next.js CSS/JS assets. Existing source fix `fa13da52` on main branch; independently built preview `/home/ubuntu/empire_agents/industry_conversion_20261013/apps/empire-public-site/out`, prior isolated branch `afb2be0f`. No new source patch, broad build or website redesign.

**Preflight, owner-boundaries and immutable assets:**
- Existing gateway uses `apps/empire-public-site/out/industries/{slug}.html` via FastAPI `FileResponse`. No reload/restart needed; active unit remained `MainPID=1158663`, `NRestarts=0` at readback.
- All six live pre-release pages returned HTTP 200 yet had zero `href="/commercial"` and zero `href="/buy"` links, retaining two obsolete `mailto:founder@empire-ai.co.uk` anchor routes.
- Candidate preserved each slug's exact self-canonical URL and headline; all six had **two `/commercial` links, one `/buy` link and zero obsolete mailto/telephone anchors**. Source was already committed with validated no-binding-payment language.
- Namespaced `_next/static` asset comparison: 21 immutable *new* files (156,380 bytes), zero existing name/hash collisions. Candidate HTML's referenced scripts/styles were checked against the candidate export.
- In the isolated candidate, real rendered export and tests `test_public_industry_commercial_navigation.py`, `test_public_commercial_sales.py`, `test_first_party_sales_interest.py`: **34 PASS**. Production-tree source regression before release: **33 PASS / 1 SKIPPED**, one dependency deprecation warning.
- All seven guarded non-industry files (`index.html`, `buy.html`, `commercial.html`, `predictive-revenue.html`, `roofing.html`, `industries.html`, `trust.html`) had verified identical before/after SHA-256. No owner-specific Lead Smart route or legal policy was promoted.

**Actual scoped publication and independent external readback:**
- One-shot hash/allowlist checked release operator `/var/tmp/empire_industry_cta_publish_20261013.py --apply` executed successfully with `mode=SIX_PAGE_PROMOTED` on **2026-10-13T21:49:08Z**. Exactly six target HTML files atomically replaced and 21 collision-free static assets added. Production and candidate hashes matched after write. The operation did not modify source, global gateway configuration, other site pages, SEO index controls, buyer call routes, contracts, DB, payments, DNS or paid advertising.
- **External live HTTP 200 and exact SHA-256 equality with the promoted candidate for all six distinct public URLs:** `/industries/roofing`, `/industries/hvac`, `/industries/solar`, `/industries/property`, `/industries/private-equity`, `/industries/legal-mass-tort`. Each live response independently contained two `href="/commercial"` and one `href="/buy"` anchors.
- All **21/21 newly published static CSS/JS asset URLs returned public HTTP 200**; `/`, `/commercial`, `/buy`, `/predictive-revenue`, `/roofing` also remained HTTP 200.
- No purchase, prospect insertion, buyer conversation, fulfilment or recognised revenue is inferred from these readbacks. The wider ASTRA 3D flagship redesign and reviewed legal, CTA, SEO, checkout and sales programmes retain their own gates.

**Rollback evidence:** mode-0700 backup directory `/var/tmp/empire_industry_cta_release_20261013`, mode-0600 manifest `manifest.json`, exact six original HTML files stored under `before/industries/`; all six original hashes independently verified. Restore **only** after comparing each currently live file with the candidate `after_sha256` receipt; if ASTRA or another owner has published a newer revision, stop rather than overwriting it. New immutable content-hashed assets may be left inert on rollback. Preserve this backup until flagship replacement is verified.

**Next actionable measurement:** Watch the existing aggregate organic impressions and real consented `/commercial` intake receipts, then qualify an actual buyer. This release fixes navigation, not distribution/traffic or the £100k/month revenue target itself.
