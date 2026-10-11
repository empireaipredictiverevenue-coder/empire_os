# EmpireOS — business-wide first-party sales activation, 11 October 2026

**Founder direction:** selling must operate across Empire AI, not merely receive repeat activation plans. This release uses the existing EmpireDB prospect store, self-serve checkout service, public gateway, owned website, existing first-party catalogue and CRM. **No new CRM, agent runtime, paid provider, mailer, database or scheduler.**

## Production truth before this change

- Public `https://empire-ai.co.uk/`, `/buy`, `/predictive-revenue`: HTTP 200. Public `/contact`, `/consultancy`, `/digital-avatar`, `/sales` did not lead to a functioning first-party enquiry page.
- Existing checkout service `empire-self-serve-checkout.service` active on loopback **127.0.0.1:8098**. Its `/v1/catalog` returned **0** products and four unavailable codes, while the canonical EmpireDB catalogue snapshot had **86** products, **35 active**, **26 active and terms-ready**, and exactly **4 verified eligible one-time fixed-price checkout products**.
- **Root cause proved, without guessing:** the working `empire-commercial-product-catalog.service` loads both `/etc/empire_os.env` and `/etc/empiredb.env`. The checkout unit loaded only the first. A bounded *read-only* proof with the canonical EmpireDB environment and existing `self_serve_catalog` returned all four eligible prices: Competitor Search Gap **$199**, Search Opportunity Map **$249**, Technical Search Audit **$299**, and US Solar Opportunity Map **$299**. No new pricing, product activation or schema change is needed.
- The public self-serve purchase handler could accept a buyer's terms and create an `accepted` fulfilment order **even when** the separate payment-proposal switch was OFF. Simply adding the missing DB env file without additional protection would silently widen binding-order authority. This release adds a second order gate that requires **both** explicit binding-order and payment-proposal approval. The current release config sets both **OFF**.

## Real sales intake across existing business lines

The safe, buyer-initiated **commercial enquiry** route uses the existing `ingest_prospect_atomic` EmpireDB RPC. No duplicate CRM, fabricated buyer or synthetic live lead is created.

| Lane | Buyer-facing first-party journey | Current scope |
| --- | --- | --- |
| Verified fixed-price intelligence | `/buy` and `/commercial` | Exactly four independently VERIFIED eligible one-time products, quote/enquiry now; binding orders & BSC payment still held |
| Predictive Revenue enterprise | existing `/predictive-revenue` | Five founder-approved enterprise product interests through the existing `/v1/checkout/predictive-revenue/interests` |
| Lead Exchange buyer seats | existing `/buy` | Four founder-approved, **non-binding** seat interests through existing `/v1/checkout/exchange/interests` |
| Consultancy | `/commercial` | Opportunity Assessment **£2,500**, Strategy Blueprint **£7,500**, Strategic Advisory **£3,000/month**, founder-led proposal only |
| Digital Avatar | `/commercial` | Copilot **$1,500/month + $1,500 implementation**, Workforce **$5,000/month + $5,000 implementation**, White-Label **$12,500/month + $15,000 implementation**. Display only with the already-recorded founder pricing approval. Capacity/cost/terms unverified, no checkout |

This is a **19-offer discovery and buyer-initiated interest surface**, **not 19 payment-enabled SKUs**. The existing 86-product catalogue remains separate. The website enquiry shows actual approved prices and explicit fulfilment disclaimers.

### Existing pipeline reused

A visitor selects an eligible offer, provides business identity, company domain, region, desired outcome and explicit **specific-response email consent**. Same-origin checks, original first-party hashed ephemeral ingress rate limiter, bounded request size and honeypot protect the gateway. The existing checkout service validates the exact offer approval, email/domain and consent before making one **idempotent** EmpireDB `ingest_prospect_atomic` call. It stores buyer-stated evidence with consent source and time, preserves the canonical prospect identity, sets `contacted_status=not_contacted` and `buy_signal_score=0`. No automatic follow-up, suppression bypass, email send, payment request, outreach, buyer activation or revenue recognition.

The existing first-party Founder CRM remains the sales/qualification owner. Receipt returned to the visitor contains a short opaque request reference, not a secret, login credential or customer record. Do **not** create artificial production leads for test purposes.

### Website and runtime reuse

- Extend the *existing* Next.js static export with `/commercial`; existing homepage, `/buy` and `/predictive-revenue` link to it. Existing public gateway redirects older `/contact`, `/consultancy`, `/digital-avatar` and `/sales` paths to the one safe form.
- Do not overwrite owner-specific `/roofing`, industry/AEO content, Lead Smart files, or other agent's site assets. Preserve the current release as rollback.
- The site shows verified one-time intelligence prices while disabling the binding checkout UI until **both** exact commercial controls are separately approved. Instead, buyers can use the founder-reviewed enquiry form. This is a truthful conversion path, not a misleading disabled payment form.
- Existing payment `EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED=OFF`. New `EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED=OFF`. Both must pass independently to enable binding orders. No activation of either switch is included in this release.

### Verification and live gates

The source release requires Python API/ingress/consent/reuse tests plus a fresh production static export, then a preflight of concurrent owner files. Production activation involves exactly the existing **checkout service** receiving its already-standard `/etc/empiredb.env` file and a restart, then exactly the existing **public gateway** code being reloaded and targeted static export files promoted. Explicit founder sales activation intent covers buyer-initiated nonbinding enquiries; separate authority remains required for BSC payment proposals, binding terms/order placement, external outreach, published product claims about unverified capabilities and live fulfilment.

Runtime readbacks must verify:
1. Checkout `/health`: `payment_proposal_authorized=false`, `binding_order_creation_authorized=false`.
2. Checkout and public `/v1/checkout/catalog`: **4** verified one-time products at their actual price.
3. Public `/commercial`: HTTP 200, safe CSP, form exists. Redirect aliases: 308 to `/commercial`.
4. Public `/v1/checkout/commercial/offers`: consent-bound enquiry catalogue of **10 approved/manual quote offers** when snapshot fresh (four verified intelligence, three consultancy, three Avatar).
5. Public `/v1/checkout/commercial/interests`: malformed or missing-consent request must be rejected with no DB mutation. **Do not submit an artificial valid buyer enquiry.**
6. Existing public /buy and /predictive-revenue remain HTTP 200; Lead Smart-owned pages unchanged.

**Reality check:** publishing a real enquiry funnel does not generate a buyer or cash by itself. The next independent step is genuine buyer conversations, scoped commercial proposals, approved payment-request capability and verified fulfilment—not rebuilding another sales platform.


## Live production activation evidence — 11 October 2026, evening UTC

**Code release:** \`0caf7b94\` on \`agent/data-cloud-wave4\`, previous production code saved at \`refs/heads/backup/pre-founder-led-sales-activation-20261011\`. Exactly 13 sales-related source/test/doc files merged cleanly, zero Git conflicts, **146 unrelated other-agent uncommitted/untracked files preserved**. No other department work or Lead Smart files modified.

**Backend:** One controlled restart of only \`empire-self-serve-checkout.service\`. The existing canonical EmpireDB reader environment file \`/etc/empiredb.env\` was injected through a narrow new systemd drop-in:
\`/etc/systemd/system/empire-self-serve-checkout.service.d/20-empiredb-reader.conf\`.
Both \`EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED=OFF\` and \`EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED=OFF\` are explicitly set. The checkout service is active/running, result success, \`NRestarts=0\`, its health returns \`binding_order_creation_authorized=false\`, \`payment_proposal_authorized=false\`, \`founder_led_commercial_interest_enabled=true\`, \`payment_execution=false\`.

**Backend verified readbacks:**
- \`GET http://127.0.0.1:8098/v1/catalog\` HTTP 200 and **four verified exact fixed-price products**: Competitor Search Gap $199, Search Opportunity Map $249, Technical Search Audit $299, US Solar Opportunity Map $299. Nothing unavailable in those four.
- \`GET /v1/commercial/offers\` HTTP 200, **10** founder-reviewed price-policy/enquiry paths: 4 fixed-price intelligence, 3 consultancy, 3 Digital Avatar. No binding commercial terms or auto-checkout from this endpoint.
- Existing \`/v1/predictive-revenue/products\` **5** and \`/v1/exchange/tiers\` **4** retained.
- A valid-shaped **negative only** local checkout POST returned **503** with \`binding_orders_not_authorized\`, before any order/DB write. A consent-denied negative local enquiry POST returned **422** \`specific_contact_consent_required\`, before any prospect/DB write. The same conditions were covered by live gateway unit/functional tests using stubs. **No synthetic positive/prospect or payable order was created in production**.

**Website:** The compiled Next.js static export was built in the isolated checkout with TypeScript validation. Exactly **35** explicitly allowlisted sales export assets/pages were inspected; **26** actually changed in \`apps/empire-public-site/out\` after hash checks, with 18 hashed assets checked. Every prior sales page was backed up in \`/var/tmp/empire_sales_site_backup_20261011/manifest.json\`; **zero** existing immutable asset collisions. Other pages (roofing, Lead Smart, industry, trust, assets) were untouched.

**Public Gateway:** One controlled restart of only \`empire-public-gateway.service\`. Health HTTP 200, active/running, result success, \`NRestarts=0\`. All real public \`https://empire-ai.co.uk\` readbacks:
- \`/\`, \`/buy\`, \`/predictive-revenue\`, \`/commercial\`, \`/trust\`, \`/industries\`, \`/roofing\` -> HTTP **200**.
- \`/contact\`, \`/consultancy\`, \`/digital-avatar\`, \`/sales\` -> HTTP **308** redirect to \`https://empire-ai.co.uk/commercial\`.
- \`/v1/checkout/catalog\`, \`/v1/checkout/commercial/offers\`, \`/v1/checkout/predictive-revenue/products\`, \`/v1/checkout/exchange/tiers\` -> HTTP **200**, with exact 4, 10, 5 and 4 product/interest options, **19 distinct buyer-facing entry-point offers** total (not 19 purchasable checkouts).
- Live backend and public JSON explicitly confirm \`binding_order_creation_authorized=false\`, \`payment_proposal_authorized=false\`, \`payment_authority=none\`, \`checkout_authorized=false\` for founder-led offers. The third active CRM service remained running and untouched.

**Regression evidence:** Prior to source merge, **203 passed** across checkout, public gateway, consent, canonical gateway and sales integration. Production checkout/public gateway scoped post-merge source regression **61 passed**. One pre-existing dependency deprecation warning, no test failures.

**Truth classification:** \`BUYER_INITIATED_INBOUND_SALES_ENQUIRY=LIVE_VERIFIED\`. \`FOUR_VERIFIED_ONE_TIME_PRODUCT_PRICES_VISIBLE=LIVE_VERIFIED\`. \`SALES_ENQUIRY_TO_CANONICAL_EMPIREDB=LIVE_CODE_AND_CONFIGURATION_READY_NO_SYNTHETIC_PRODUCTION_PROSPECT_INSERTED\`; the successful actual buyer-created prospect is still unobserved. \`BINDING_ORDER_AND_BSC_USDT_PAYMENT=SEPARATELY_HELD\`. \`REALIZED_REVENUE=NOT_INFERRED\`. The next real proof is a genuine customer enquiry and qualification, followed by exact, separately authorised product checkout/payment proposal/fulfilment verification.

**Founder objective preserved:** the *sales entry point* is active across the business. Do not replan or rebuild this route; only check meaningful new buyer events and the separate binding-order/payment gate. No repeat CRM, Lead Smart, or duplicate sales runtime.
