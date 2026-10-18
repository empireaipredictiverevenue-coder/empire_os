# Empire AI — premium Data Brokerage gateway-to-CRM integration

**18 October 2026 | Safe integration candidate | NOT public/released**

## Confirmed source-of-truth checkpoint

The founder's existing live command:

```bash
./.venv/bin/python -B -m scripts.review_data_brokerage_premium_enquiry_20261018 --read-only
```

returned `PREMIUM_DISCOVERY_FEATURE_TESTED_RELEASE_HELD`. This means
exactly **two unpriced, privately staged discovery types** exist,
the existing public commercial catalog exposes **10 options** and still
contains the approved nonbinding **$199 Competitor Search Gap** enquiry;
it does not mean there is a real premium buyer or an activated checkout.

The new live read-only preflight:

```bash
./.venv/bin/python -B -m scripts.review_data_brokerage_premium_gateway_20261018 --read-only
```

returned `TWO_HOP_PREMIUM_GATEWAY_ADAPTER_READY_RELEASE_HELD`,
`production_route_published=false`, `crm_records_created=0`,
`database_writes=false`, `payment_activated=false`.
The original public and checkout apps do not have either premium route
mounted. Existing client-facing and shared source files were untouched.

## Feature-only gateway integration completed

- `empire_os/data_brokerage_premium_gateway_adapter.py` defines one
  candidate public endpoint:
  `/v1/checkout/brokerage/premium-discovery` (GET and POST).
- It is deliberately **not imported by** `empire_os/public_gateway.py`.
  Its factory requires three independent Boolean release facts, each
  explicitly true: founder permission, private checkout route
  installation verification, and ASTRA commercial-page review.
- Its GET would return only two **unpriced** discovery topics and
  qualitative buyer problems, with `Cache-Control: no-store`. The
  private $1,250 and $4,000 hypothesis amounts, original SKU names,
  checkout controls and apparent source rights are never published.
- Its POST requires the exact production site origin, a first-party
  fetch-site context, JSON, ≤12,000 bytes, a working caller-provided
  gateway per-peer enquiry limiter, exact discovery offer code, strict
  Boolean consent, empty honeypot, and no client-supplied financial,
  contact-import or contract-power fields.
- It forwards a bounded JSON body **only** to the fixed internal
  loopback endpoint `http://127.0.0.1:8098/v1/brokerage/premium-discovery`.
  It sends no visitor cookies, authorization header, PII-bearing
  telemetry or arbitrary URL; HTTP redirects are disabled. The private
  checkout route's independent validator revalidates consent,
  idempotency, domain/email and accepted field contents.
- On success, the public gateway exposes **only** a validated, typed
  `commercial_enquiry_recorded` receipt, a 20-character hex reference,
  matching requested product code and exact `FOUNDER_PRIVATE_SCOPE_REVIEW`
  next step. It cannot output an unvalidated backend response,
  subscription receipt, raw prospect row or third-party source record.
  Backend exceptions and DB details are redacted to generic 503
  errors. Invalid buyer requests return a bounded 422.
- All positive HTTP integration tests use an **isolated two-app ASGI
  composition** and a fake in-memory canonical RPC. They prove the
  original existing prospect payload shape and two-hop consent/receipt,
  but **not** a real production CRM insert, buyer intent or payment.

The original private handler remains:
`empire_os/data_brokerage_premium_enquiry.py` (factory
`make_private_discovery_router`). Neither the new public adapter nor
the private router is mounted by normal production startup. This
increment does **not** add another service, new database, payment
provider, subscriber management system, file export or frontend.

## Exact owner responsibilities before any release

**Existing checkout API owner**
1. Obtain founder approval and an explicit staged release ticket.
2. Review the canonical `/v1/brokerage/premium-discovery` private
   router factory and mount it inside the existing
   `empire_os/self_serve_checkout_api.py` using an appropriate
   rate limiter and loopback-only service identity. No blanket
   security-header bypass and no public access to raw CRM RPC.
3. Verify private function import, isolated live service health,
   existing checkout routes and no DB/permission changes. Do **not**
   activate BSC payments, new orders or automatic outbound.

**Existing gateway owner**
4. Review the new candidate `make_reviewed_public_premium_gateway_router`
   with actual `FIRST_PARTY_INTAKE_LIMITER.allow`, the fixed
   `forward_to_private_checkout` function, and separately checked
   release facts. If any fact is absent, do not mount.
5. Only after the private route and controls are independently
   verified, mount into the **existing** `empire_os/public_gateway.py`
   through its normal additive API release path. Verify
   exact origin, rate limits, same-origin consent, body size, safe
   private errors, and 404 on all unknown premium URL patterns.
   Maintain existing gateway traffic budgets and no-store headers.

**ASTRA website owner**
6. Integrate the unpriced discovery options into the current
   `apps/empire-public-site/src/app/commercial/page.tsx`, without
   modifying other agents' unfinished flagship visuals. Its
   existing cards expect `approved_price_cents:number`; do
   not feed `None` into price formatting or fake a $0 offer.
   Add a distinctly labelled *Request an intelligence scope* choice.
7. Submit the existing first-party form's strict
   `brokerage_agency_discovery` or
   `brokerage_enterprise_discovery` codes to the reviewed endpoint
   only when the public adapter is actually released. Same
   consent, idempotency key generation, retries and honeypot policy.
   Show the confirmed CRM reference only after success.
8. Run real mobile and desktop QA, confirm accessibility/copy,
   verify network origin restriction, rollback and GET-only preview.

**Founder Sales / CRM owner**
9. Only a **genuine buyer-initiated** enquiry may establish a real
   production CRM record. Reconcile its hashed identity, company,
   consent and scope from the existing canonical ingestion into the
   founder's private review. Do not manufacture a form submission
   simply to make the canary green.
10. Obtain real contract and capacity evidence before describing
    $1,250/month or $4,000/month as accepted/approved prices;
    verify independent receipt, scope fulfilment and settlement
    before recognising brokerage revenue.

## Distinguishing states

| State | Meaning |
|---|---|
| `TWO_HOP_PREMIUM_GATEWAY_ADAPTER_READY_RELEASE_HELD` | Gateway+private integration candidate implemented and safely tested |
| Both premium routes mounted after reviewed release | Only technical discovery-form availability |
| Verified buyer-initiated CRM record | One real enquiry; NOT a signed subscription |
| Negotiated buyer terms and capacity | Commercial agreement evidence; NOT revenue |
| Independent settled receipt and delivered service | Evidence to review for recognised/realised revenue |

Production truth takes precedence over feature completeness.
Until the separate release review is actually executed,
**the new premium public endpoint remains absent.**
