# First-party selected-product handoff: /buy → /commercial

**20 October 2026 · additive public website owner review · not yet applied to public runtime**

## Concrete conversion defect confirmed

The production source for `/buy` lists `competitor_search_gap` as an approved initial product. When binding checkout is not permitted, the page displays **Request your intelligence proposal** but links to `/commercial` with no selected product. The `/commercial` form fetches ten governed live commercial offers and previously selected `offers[0]` by default—`consultancy_opportunity_assessment`—even when the buyer had chosen **Competitor Search Gap** ($199 catalogue entry). This resets buying intent and can result in the wrong enquiry product being sent to the first-party intake.

This is a **confirmed product-selection loss**, not evidence that any named visitor abandoned a purchase. The authorised read-only canonical acquisition aggregate currently returns 0 commercial and 0 Predictive Revenue acquisition rows; it cannot measure visitor demand, drop-off or other channels.

## Minimal source change

Only two public-site files in our isolated feature branch:

1. `apps/empire-public-site/src/app/buy/page.tsx`: when checkout is not authorised, proposal CTA preserves the product selected from the *live filtered catalogue*, e.g. `/commercial?product=competitor_search_gap#commercial-enquiry`. If no product was available, links to the form without a selected code.
2. `apps/empire-public-site/src/app/commercial/page.tsx`: after loading the **authoritative live offer list**, it reads the optional `product` query parameter, selects only a matching product from that governed list, and otherwise defaults to the first live approved offer.

The URL carries **only a product code**, not a price, terms, recipient, contact data, consent, checkout authorisation, wallet or order ID. The original consent checkbox and existing POST to `/v1/checkout/commercial/interests` remain unchanged. There is no outbound or finance code in this change.

## Release candidate proven

An isolated candidate was built **from the current production public-site source**, with exactly the two-file patch applied:

`/home/ubuntu/empire_staging/agency_selected_product_enquiry_20261020`

- Next.js 16.3.5 `next build --webpack` **passed** with TypeScript and 19 static pages generated
- New static build ID `Smie5rfylWcX9bNRgphA0`
- Both `out/buy.html` and `out/commercial.html` produced
- 37 compiled JavaScript chunks inspected; confirmed selected-product URL, form anchor, `URLSearchParams` handling and `FOUNDER_LED_ENQUIRY_AVAILABLE` contract are present
- Source-level regression tests cover preserved selection, unsupported-code fallback, approved offer source, price-not-from-URL, unchanged consent, and unchanged governed form POST
- **No production static files, server or gateway have been changed.** This staged build is not permission to switch a working live website owner's release during concurrent flagship work.

## Exact website-owner promotion checks

The existing flagship Website/SEO owner should review this *minimal* diff, and combine it with its current flagship source and design changes before a release. Do not broad-sync this feature branch into `/srv/empire_os`, override the live Next.js/static gateway without reading current owner rules, or publish customer proof assets without original source licences.

On the owner's own temporary preview build:

1. Load `/buy`, select **Competitor Search Gap**, click **Request a Proposal**. Expected URL carries `?product=competitor_search_gap#commercial-enquiry`.
2. The form's **Solution** selector must show `Competitor Search Gap`, not the default consultancy option. Price and label must remain from the existing live catalogue GET.
3. An unsupported, expired or invented code, including `?product=some_free_order`, must safely fall back to the first currently approved product; it must not create a product, price, order or valid consent.
4. Changing the selector or missing consent still prevents unapproved contact. Do not perform a live POST with fabricated buyer data.
5. Re-run read-only checks on `/buy`, `/commercial`, `/predictive-revenue`, public API catalogue responses and private CRM anonymous-access denial.
6. Record original `out` build ID and active proxy/static service target; promote only through existing public website owner's release protocol with a revert target. Do not replace the separate privately deployed Founder Console.

**After owner-approved public release**, compare actual first-party intake counts over time and use existing Analytics-owner instrumentation to determine whether real consenting prospects are arriving. Zero currently observed acquisition rows are an opportunity to start acquiring buyers, not evidence of absent market demand.

## 20 October refinement — active checkout state and real-browser proof

The original small fix covered only the nonbinding, checkout-disabled proposal CTA. On 20 October, a fresh read-only GET of the **live** `/v1/checkout/catalog` showed `binding_order_creation_authorized=true` for the catalogue, so the public `/buy` page was currently rendering the enabled checkout form instead of that CTA. This is a *checkout creation policy*, not proof of an accepted payment or delivery.

An additional **secondary Request a Proposal Instead** link is now available **inside the checkout-enabled view**. It preserves the currently selected approved catalogue product using the same constrained query parameter and allows visitors to ask for a founder-led proposal **without a BSC wallet or payment**. The existing create-payment-request form and its acceptance logic are unchanged; the new link is an anchor, not a form submit button. In both states the query parameter can only preselect one of the currently returned approved offer codes.

Fresh isolated Next.js 16.3.5 static build: TypeScript passed, 19 static pages generated. Real Chromium/Puppeteer smoke from the compiled export tested selecting **Search Opportunity Map**, switching to **Competitor Search Gap**, carrying `?product=competitor_search_gap` to the commercial page, correctly selecting **Competitor Search Gap**, and falling back to the first approved offer for an unknown code. It replayed only public catalogue GETs and blocked all POST requests. **Zero buyer records, orders, messages or payments were created.** The preview's unsupported premium-discovery URL returned 404 because the local smoke GET proxy intentionally only forwarded three approved catalogue endpoints; this does not imply the real premium-discovery endpoint is down.

The browser-smoke script is `scripts/smoke_agency_selected_product_browser_20261020.cjs`; it serves only the **isolated staged static export** on loopback and requires the existing approved browser installation on EmpireOS. It is for website-owner review, not a production service.

**Release owner:** only the two public-site source modules need merging into the actual latest website-owner branch. This refinement intentionally provides a genuine first-party **non-wallet** conversion alternative while preserving any currently authorised checkout, instead of disabling commerce. Actual consented enquiry receipt → correct CRM tenant remains unverified until a real buyer completes the form.
