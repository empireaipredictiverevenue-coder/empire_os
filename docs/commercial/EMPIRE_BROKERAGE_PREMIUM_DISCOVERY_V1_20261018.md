# Empire AI Data Brokerage — premium agency and enterprise enquiry service

**18 October 2026 | Founder build continuation | FEATURE-ONLY, NOT PUBLICLY DEPLOYED**

## Why this increment exists

The founder ran the production read-only
`scripts.review_data_brokerage_sales_activation_20261018 --read-only --show-packages`.
Three existing products were verified as **internal sales packages only**:
$199 roofing competitor report, a proposed $1,250/month agency research pilot,
and a proposed $4,000/month enterprise territory intelligence pilot.
The original public `/commercial` form already includes the approved
`competitor_search_gap` $199 **founder-led enquiry**, but not the two
high-ticket draft packages. The website, offers service, CRM and gateway
already exist; there is no reason to build replacements.

Another EmpireOS agent currently has uncommitted changes in
`empire_os/first_party_sales_interest.py` and
`empire_os/self_serve_checkout_api.py`. ASTRA owns the flagship and public
`apps/empire-public-site/src/app/commercial/page.tsx`. **None of those shared
files were overwritten or restarted in this increment.**

## New working feature code

`empire_os/data_brokerage_premium_enquiry.py` provides:

- `brokerage_agency_discovery`: requests a conversation about **agency
  white-label source-backed market research**.
- `brokerage_enterprise_discovery`: requests a discussion about **multi-site
  territory evidence and expansion decision support**.

Both are **unpriced**; $1,250 and $4,000 remain private negotiation hypotheses,
not publicly approved offer prices. No guaranteed number of monthly reports
or fixed deliverable capacity is represented as a commitment.

The library defines a typed, bounded, exact-code-only request contract and an
optional FastAPI `APIRouter` factory. The router **is not imported/mounted by
any production ASGI app**, so this release creates no public GET/POST route.
In isolated FastAPI tests the router:

1. Requires matching first-party `Origin` and `Sec-Fetch-Site`, JSON
   media type, a caller-provided working gateway rate limiter, and ≤12 kB
   body size.
2. Requires a named real organisation, validated email/company domain,
   sector, market, explicit problem statement, unique idempotency key, empty
   anti-bot honeypot, and **explicit response-only consent**.
3. Rejects unapproved product codes (including direct submission of the
   two price-hypothesis codes), extra client-supplied financial flags,
   malformed contact data and absent/false consent **before** any DB call.
4. Reuses the **existing** canonical
   `POST /rest/v1/rpc/ingest_prospect_atomic` contract. The emitted niche
   is `commercial_sales:data_brokerage_premium_discovery`; contact remains
   `not_contacted`, buy_signal_score=0, canonical company-domain identity
   plus an email hash, and a deterministic, offer-specific ingest key.
5. Returns a receipt only if the canonical RPC confirms a prospect ID
   and its accepted `created`, `existing_ingest` or `existing_identity`
   disposition. It does **not** verify the buyer's purchase intent or
   automatically create a contract, delivery entitlement or payment.
6. Never enables follow-up email, unsolicited marketing consent, public
   pricing, raw third-party source licensing, binding terms, forecast
   revenue or external data delivery. Unexpected DB errors are redacted
   to a safe 503 in the isolated API.

Unit/API tests use an injected in-memory RPC; no real buyer, test order,
revenue event, checkout, email or EmpireDB write was made in these tests.

## Read-only live preflight

`scripts.review_data_brokerage_premium_enquiry_20261018 --read-only` checks
the existing verified private Sales portfolio, original sample and
**GET-only** public catalogue coverage before it reports:

`PREMIUM_DISCOVERY_FEATURE_TESTED_RELEASE_HELD`.

The expected state at this checkpoint is one existing public report enquiry,
two internal premium unpriced discovery ideas, no live premium route, no
website mutation and no end-to-end buyer-to-Founder-CRM proof.

## ASTRA / commercial frontend release handoff (separate approval)

When ASTRA resumes the **existing** `/commercial` page, obtain founder
approval for a **unpriced discovery** option in the existing "Intelligence
Products" family or a companion commercial discovery section. It should
show only grounded capabilities, never draft internal monthly prices or
unverified ROI. The existing frontend assumes that all catalogue offers
have numeric `approved_price_cents`; displaying `None` directly is unsafe
and must have an explicitly designed "Request a scope" state.

Separately review mounting this exact router behind existing
`/v1/checkout` same-origin gateway protection, original host/session
rate-limiter and documented traffic/error observability. Do not expose
an unauthenticated internal service or omit the gateway limiter.
During integration preserve the other agent's organic campaign tracking
changes to the canonical first-party interest module. Maintain the
existing approved $199 enquiry unchanged.

Required public-release gates:
- Founder approval of exact unpriced copy and integration scope.
- ASTRA visual/mobile QA and consent wording.
- Secure original first-party gateway mount; bounded CSRF/origin,
  payload size, rate limits, ingestion idempotency and abuse testing.
- Existing canonical atomic CRM RPC contract and single-tenant
  first-party identity/consent source verified.
- Real buyer's self-initiated consentful submission to confirm exactly
  **one** intended CRM record and a private founder review item, without
  a synthetic production prospect.

No new CRM tables, mail providers, background processes or marketplace
accounts are required.

## Operator command

```bash
cd /srv/empire_os
./.venv/bin/python -B -m scripts.review_data_brokerage_premium_enquiry_20261018 --read-only
```

The private API simulation is proven by the tests, not by submitting
a real production form. Distinguish **build feature ready** from
**public release ready**, **actual buyer intent** and **earned revenue**.
