# Empire AI Data Brokerage — public enquiry bridge and next conversion action

**18 October 2026 | Founder/Sales/ASTRA handoff | READ ONLY; no production website change**

## Actual founder proof at handoff

The founder ran:

```bash
cd /srv/empire_os
./.venv/bin/python -B -m scripts.review_data_brokerage_sales_activation_20261018 --read-only --show-packages
```

The report confirmed `THREE_BROKERAGE_DRAFT_PACKAGES_READY_REVENUE_HELD`:
- existing `roofing_competitor_report`, $199 USD once;
- existing `agency_white_label_search`, proposed $1,250 USD/month;
- existing `portfolio_geography_intelligence`, proposed $4,000 USD/month.

**None** had a customer acceptance, verified contact, contract, authorised
delivery capacity, public listing or settled payment. The last two prices
are hypotheses; do not present them as founder-approved public prices.

## Critical discovery on the existing real website and API

The site's **existing** `/commercial` enquiry form and
`/v1/checkout/commercial/interests` use the controlled
`empire_os.first_party_sales_interest` workflow. The read-only
`scripts.probe_first_party_sales_http_readonly` verified:

- Two public rendered page/app GET assets containing their expected
  enquiry endpoints.
- Both public offer/catalogue GET responses.
- **No POST**, buyer test, CRM row creation, payment or site mutation.
- Status `PUBLIC_ENQUIRY_SURFACE_VERIFIED_CRM_DELIVERY_UNPROVEN`.

The live public `GET https://empire-ai.co.uk/v1/checkout/commercial/offers`
returned **10** offers on 18 October, including an existing nonbinding
proposal enquiry for `competitor_search_gap`, **$199 USD once**,
with `binding_terms_ready=false`, `checkout_enabled=false` and
`fulfilment_automated=false`.

The two proposed high-ticket brokerage offer codes are **not** present
in that public catalogue. This is a meaningful commercial
distribution gap: without an enquiry-specific discovery entry,
visitors cannot select the agency or enterprise *package by its own
code* in the current existing `/commercial` form. Do not confuse
this with actual market demand or a broken checkout.

## Implemented now (no new backend endpoint)

`empire_os/data_brokerage_public_interest_bridge.py` makes a strict
read-only mapping between the original private sales evidence and
the public nonbinding offers. It proves the exact one-time $199
matching product, explicitly classifies the two premium offers as
private only, and rejects conflicting public prices, duplicate
product codes, public checkout/contract power, or a forged paid
subscription.

`scripts.review_data_brokerage_public_interest_20261018 --read-only`
executes an **allowlisted HTTPS GET** of the current public catalogue,
reuses the existing private brokerage source integrity verifier, and
prints only catalogue/product codes and safe state metadata.
It sends no prospect data, contacts or source rows, and submits no
form. Network failure or catalogue drift fails closed. The status
observed from the live run:

`ONE_PUBLIC_ENTRY_TWO_PRIVATE_RECURRING_DRAFTS`.

Example command:

```bash
cd /srv/empire_os
./.venv/bin/python -B -m scripts.review_data_brokerage_public_interest_20261018 --read-only
```

This is the public-discovery coverage fact; it does **not** verify that
a real buyer submitted an enquiry or that founder CRM received it.

## Correct next implementation handoff — ASTRA owns flagship UX

When founder authorises a **public site/API release**, extend the
existing `/commercial` experience, not a second website or CRM.
Proposed high-ticket *discovery-only* choices:

- **Agency Market Intelligence** — request a confidential pilot scope,
  not a publicly approved $1,250 recurring subscription.
- **Enterprise Territory Intelligence** — ask for a bounded discovery
  discussion, not a publicly approved $4,000 price or service capacity.

Either must use a separately reviewed first-party *enquiry-only*
product code, same-origin protection, captcha/rate limits if supported,
explicit response-only contact consent, idempotency and existing
`ingest_prospect_atomic` path. No generic client contact list
import and no SEO/CRM scoring from an enquiry submit alone. The
frontend currently assumes every catalogue offer has a numeric
`approved_price_cents`; it cannot safely render unpriced offers by
simply returning `null` without an ASTRA-reviewed UI change.

**Do not activate them merely because a new internal module exists.**
The core commercial catalogue and flagship website are owned by
other teams. Need agreed product wording, capacity, pricing
presentation, evidence and explicit release approval before changing
production browser-facing choices.

## What must happen for actual revenue

1. Retain `competitor_search_gap`'s existing live nonbinding enquiry
   route. Reuse the already-sent SPC thread, with no duplicate message.
2. Confirm **one actual interested agency/enterprise buyer** through
   existing CRM/partnership conversations, not a fabricated quote.
   A publisher/affiliate discussing performance leads is not
   automatically a buyer of intelligence subscriptions.
3. Capture consent, relevant problem, specific territories and a
   negotiated scope in the existing CRM; do not create a duplicate
   buyer or auto-send contact.
4. Perform source-specific commercial-use review, prove report
   delivery capacity, agree terms, independently verify payment and
   fulfilment before recognising revenue.
5. Independently run the existing restricted sales acquisition to
   founder-tenant CRM read-only reconciliation; **a live GET-only
   canary does not establish end-to-end genuine buyer intake**.

## No duplication / governance of this exact release

No new database, new endpoint, new frontend deployment, buyer/test
submission, billing account, payout, third-party licence, outbound
send, private file export or revenue record were created.
All existing agents' pending work and the flagship ASTRA source were
left alone.
