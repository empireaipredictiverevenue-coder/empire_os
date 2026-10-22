# Empire GTM Intelligence — reintegration boundary (22 Oct 2026)

**Identity:** Reuse `empire_gtm_agent_v1` and the existing
`empire-gtm-pipeline.service` / buyer-review `OnSuccess` trigger.
No replacement agent, CRM, timer, execution bus or new data platform.

## Current verified local implementation

- `empire_os/gtm_agent.py`: original action-selection brain, decision only.
- `empire_os/gtm_agent_policy.py`: AUTO / APPROVED_ACTION /
  STANDING_AUTHORITY / FOUNDER_GATE action policy.
- `empire_os/gtm_pipeline_worker.py`: existing buyer-to-governed-outbound
  path (separate from the new read-only observer).
- `empire_os/gtm_integration_observer.py`: reads current commercial-loop
  status and canonical opportunity radar, invokes the original agent's decision
  function, emits internal research-review observations without new
  authorisation or any external execution.
- `scripts/run_gtm_pipeline_worker.py`: calls this observer on the existing
  GTM cadence. Observable output:
  `runtime/gtm_pipeline/integration_observer_latest.json`.

**This is an observational integration, not proof of an operational end-to-end
customer acquisition or payment lifecycle.** No source candidate becomes an
approved buyer or outbound contact merely by appearing in the observer.

## Capability ownership and next connections

| Source / product | GTM responsibility | Present integration proof | Remaining direct wiring |
| --- | --- | --- | --- |
| Market GPS and opportunity radar | Source-backed market research intake | New read-only GTM observation wired to existing GTM runner | Canonical qualification and product/buyer acceptance |
| Community intent and Storm opportunity | Public signal and demand research | Radar source mapping exists; only fresh available sources enter observation | Source rights and actual buyer corroboration |
| Buyer Scout / enrichment / Buyer Review | Identity, eligibility, buyer qualification | Existing GTM worker + Buyer Review OnSuccess | Refresh live dedupe, suppressions, contact- and tenant-authority coverage |
| JEV / research / enterprise discovery | Problem-to-offer discovery | Research systems exist; no direct GTM product event verified here | Explicit provenance-preserving intake adapter |
| Public website / SEO / AEO / GEO | Consent-based organic acquisition and attribution | Public content and search surfaces exist | Signed first-party enquiry receipt and canonical source attribution |
| MediaOS / YouTube | Evidence-based content acquisition support | MediaOS exists, no GTM job handoff verified | Approved distribution campaign IDs, source metrics, conversion attribution |
| Job matching / retrofit / funding | Qualify homeowner jobs, match actual contracted providers | Staging matching/intake work exists | Consent/tenant-scoped job-to-buyer and accepted-work contract |
| Brokerage / Data Exchange | B2B requirements discovery and rights-cleared offers | Unpriced premium enquiry gateway exists | Source-use rights, signed buyer scope, fulfilment/settlement linkage |
| Agency / WordPress MCP | Product/tenant-scoped acquisition | Authenticated MCP proof exists | Canonical tenant grants, signed scope, credential delivery |
| Unified Smart CRM | Authoritative prospect/buyer lifecycle *destination* | CRM pilot exists | Tenant-authenticated, idempotent handoffs; no second CRM |
| Predictive Revenue / Economic Memory | Attribution and verified results *destination* | Outcome/evidence observer work exists | Event-ID join across accepted offer, payout, settlement, realised margin |

## Non-negotiable operating rules

1. Research signals are **not** permission to send commercial outreach.
2. All downstream candidates require provenance, applicable data-use rights,
   source freshness, person/contact validity and tenant/suppression checks.
3. AUTO is for internal reversible tasks; existing policy controls govern
   external contacts, campaigns, binding contracts, money and recognition.
4. Do not open UK/US call routes, financial/payment rails, live data publication,
   outbound email or media publication through this bridge.
5. Never create a second scheduler for GTM: use the existing
   buyer-review -> GTM handoff and the fallback GTM timer.
6. Do not mark suggested revenue, predicted value or payment requests as
   recognised revenue or realised profit.
7. Maintain original offer/source/event IDs for reconciliation to EmpireDB.
8. Avoid editing owner-controlled application modules without their integration
   contracts. Unwired rows above remain **not proven**, not silently complete.

## Verification / release

Unit proof: `tests/test_gtm_integration_observer.py` plus existing GTM
agent, policy and worker tests. Local read-only probe 22 Oct:
11 radar candidates -> 11 **internal research review** observations,
0 outbound, 0 CRM writes, no payment or revenue recognition.
Current commercial loop blocker `buyer_conversation` -> original agent
decision `conversation.monitor`, no execution.

Production runtime directory is root-owned. The observer was not separately
activated as an independent service. Existing GTM service will use the adapter
on its next execution through its existing runner. Verify the resulting
artifact under the service's credentials before calling this deployed.

## Next integration: JEV + organic + first-party count-only (23 Oct)

**Implemented and unit-tested:** `empire_os/gtm_commercial_source_bridge.py`
is now called by the existing `gtm_integration_observer.py`, which is
already invoked by the existing GTM pipeline service. No extra daemon,
timer, outbound route, website modification, CRM writer or database query.

- **JEV:** Reads only the existing `runtime/jev_client_pain_discovery/aggregate_latest.json`.
  Requires current `CLIENT_PAIN_DISCOVERY_OWNER_REVIEW_ONLY` schema,
  safe rights/identity/authority flags and UTC timestamp. Exports theme-level
  counts and proposed product mapping, never the private evidence URLs or
  people. Live result: `NO_CONCRETE_JEV_PAIN_THEMES_IN_CURRENT_RECEIPT`.
- **Organic:** Reads an owner-generated private weekly GSC page report
  from `/home/ubuntu/empire_releases/seo_weekly_gsc_two_page_20261022`
  in a bounded, page-only, read-only manner. Strictly validates the
  canonical Google property, page set, dates, source state, evidence type
  and no execution. Current result: both pages
  `NO_PAGE_IN_RETURNED_GSC_ROWS`. This is **not a measured zero**;
  postrelease organic conversion attribution remains unknown.
- **Genuine enquiries:** Reserves a count-only intake from the existing
  founder-authorised canonical sales aggregate reader
  (`empire.founder.canonical_sales_source_aggregate.v1`).
  The authorised DB owner must independently produce and attest a fresh
  root-owned receipt at
  `runtime/gtm_pipeline/owner_sales_enquiry_counts_latest.json`;
  include `observed_at_utc` and the exact existing count/consent fields,
  without customer identifiers. **No attempt is made to call the privileged
  operator or to create the missing receipt.** Without that proof the state
  stays `HELD_NO_OWNER_VERIFIED_ENQUIRY_COUNTS`, NOT zero.
  Even nonzero count-only proof is NOT authenticated per-person consent
  for GTM auto-contact and NOT verified organic source attribution.
- Product source observations are stored within the already-running
  `integration_observer_latest.json` under `product_sources`. This is
  review/decision information, not an independent buyer candidate queue.

**Verified** with 82 focused GTM tests passing. Read-only local output:
JEV no concrete themes; GSC no returned page rows; first-party count unknown.
All reported outbound/CRM/payment/recognised-revenue actions remain false.

**Next source-owning implementations:** a canonical per-enquiry signed receipt
reader from the existing CRM/tenant owner; direct JEV evidence references
without PII; verified owner SEO session-to-intake attribution after lawful
measurement; then rights-cleared brokerage scope/enquiry and approved
commercial-product attribution. Never collapse Google impressions, public
discussion, visitor-declared URLs and accepted buyer interest into one
"qualified leads" number.

### Data Brokerage source observation (23 Oct)

The same existing GTM cycle also reads only the bounded, existing
`runtime/data_brokerage/internal_product_catalog_latest.json` metadata.
Original per-record raw data, third-party source rows and buyer identities
are not ingested. The current owner catalog verifies **four internal
research-product records**, **zero independently verified buyers**, no
distribution approval, no resale rights clearance, no live publishing and
no payments. GTM reports
`BROKERAGE_INTERNAL_RESEARCH_PRODUCTS_RIGHTS_AND_BUYERS_HELD`.
This does NOT mean brokerage products are live customer offers or that
the unpriced public enquiry has generated a buyer. The separately owned
first-party intake/rights/fulfilment systems remain unchanged.

**Test update:** 83 targeted GTM tests passed with the brokerage fail-closed
contract. No public listing, pricing, email, CRM promotion, database write,
fund transfer or revenue recognition was performed by this integration.
