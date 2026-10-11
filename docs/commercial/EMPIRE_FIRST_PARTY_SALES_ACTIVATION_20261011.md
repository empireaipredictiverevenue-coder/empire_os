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
