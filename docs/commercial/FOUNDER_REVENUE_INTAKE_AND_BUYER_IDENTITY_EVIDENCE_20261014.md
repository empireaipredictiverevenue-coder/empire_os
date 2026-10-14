# EmpireOS — Public Sales Enquiry and Buyer Identity Verification

Date: 14 October 2026 | Mode: OBSERVE | No live customer submission | No production activation

## Decision 1: website intake surface exists; end-to-end customer-to-CRM proof remains unverified

Live local public gateway GET-only observation:

- GET /commercial -> HTTP 200 HTML; all 8 deployed first-party static JS chunks reachable; compiled script contains /v1/checkout/commercial/interests.
- GET /predictive-revenue -> HTTP 200 HTML; all 7 deployed JS chunks reachable; compiled script contains /v1/checkout/predictive-revenue/interests.
- GET /v1/checkout/commercial/offers -> HTTP 200, 10 catalogue options, explicitly nonbinding, outbound/payment authority none.
- GET /v1/checkout/predictive-revenue/products -> HTTP 200, 5 catalogue products, execution authority none and actual revenue false.
- Internal checkout catalogues respond, too. The gateway and form wiring are therefore deployed and visibly reachable.
- Read-only Founder CRM visibility probe reports zero tenant-visible commercial and predictive sales prospects. This is NOT proof the enquiry path is broken: zero can mean that no real buyer submitted a qualifying form. No fake customer POST is permitted merely to inflate counts.

Bounded code/test action:

- Added scripts/probe_first_party_sales_http_readonly.py: requests ONLY GET from loopback with the fixed public Host, reads actual HTML plus same-origin Next.js scripts, validates the deployed form-route strings and authority-disabled catalogues, and returns one sanitized status. It never sends a form POST, creates a prospect or touches customer data.
- Added tests/test_probe_first_party_sales_http_readonly.py: HTTP failures, missing compiled actions, external script exclusion, hard payload caps, malformed catalogues, false activation permissions, GET-only method and nonclaims of CRM or payment proof.
- Expected success state PUBLIC_ENQUIRY_SURFACE_VERIFIED_CRM_DELIVERY_UNPROVEN. This is not a launch pass for a real sales transaction or CRM handoff.

Outstanding independent proof: using the existing aggregate-only privileged scripts/probe_canonical_sales_intake_aggregate_readonly.py and tenant-restricted scripts/probe_founder_sales_visibility_readonly.py, reconcile a **genuine**, user-initiated consented enquiry's immutable source acquisition/tenant entity binding and Founder CRM projection. The aggregate source count may remain zero until actual demand. Do not manufacture a fake buyer to move it to 1, and do not loosen tenant security.

## Decision 2: known buyer identity contamination held before contact research

First-party independent identity evidence observed 14 October:

- https://seanreganlaw.com/ identifies Sean Regan Law (New Orleans personal injury firm).
- https://lawful.com/about identifies Lawful, a lawyer directory/legal discovery platform whose team includes Paul Mazzola and Mac Lara. These people must not be attributed to Sean Regan Law.

Existing buyer deferred-enrichment source had one exact pairing: company label 'Sean Regan Law | Personal Injury & Car Accident Lawyer' with website lawful.com and Lawful management as its supposed decision-makers. The old review planner classified it as named-person evidence recovery. This was a false person-company chain and could contaminate a founder review.

Bounded correction in existing empire_os/buyer_recovery_action_desk.py:

- Only the exact observed company-label + lawful.com website pair is marked IDENTITY_CONFLICT_HOLD.
- Its unrelated person and route evidence are removed from the **review projection**, and the record is parked until verified first-party company/website reconciliation. The original source JSON is untouched; no alternate email/domain is automatically bound.
- A legitimate distinct Lawful company entry remains eligible for *research* under its normal evidence gates, not for sending. The quarantined record is deprioritized below usable review rows.
- The live read-only planner now reports 2,136 total inventory rows, 2,120 unresolved, 131 high priority, 25 bounded review packets, **1 verified company-identity mismatch held**, zero sends and zero DB writes. The mismatched Sean Regan/Lawful row is no longer in the top 25.

No new agent, recurring timer, external service, form deployment, prospect mutation, sender authorization, domain edits, payment or public traffic changes. The Founder Dashboard and existing buyers/partner work continue unchanged. All unmatched names and contact evidence require independent review.

## Production priority

Warm partner conversations (LeadsDoWork acceptance, MyJobQuote manager) have more near-term contracting momentum than cold anonymous buyer research, but neither partner has a verified signed rate and permitted overlapping lead category/source. Exclusive category scope stays held as documented in docs/commercial/UK_HOMEOWNER_PARTNER_SCOPE_FIRST_REVENUE_REVIEW_20261014.md.

Next revenue gate is a permitted real enquiry/affiliate event, trustworthy source attribution, explicit partner acceptance and payment evidence — not prospect counts alone.
