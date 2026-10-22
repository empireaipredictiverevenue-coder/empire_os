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
