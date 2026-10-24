# Free buyer-specific sample — stage definitions before HubSpot automations

Empire AI | Predictive Revenue Diagnostic | 24 October 2026

**Context:** an anonymised B2B company publicly requested HubSpot RevOps help with disagreement on MQL vs SQL, inconsistent pipeline stage meaning and unreliable forecasts / source attribution. This is a pre-access, public-brief evidence sample only, NOT an assessment of their actual CRM.

## Five fields to make the first two weeks measurable

| Signal / event | Proposed decision-grade definition | Evidence/protection required |
|---|---|---|
| MQL | A distinct business entity with a stated target segment match and an attributable qualifying event (not email open alone) | Persist source event, timestamp, observed entity/domain and explicit scoring criteria; duplicate keys held for review |
| SQL | Sales accepted a qualifying business need and an accountable owner, with time-stamped acceptance | Required criteria: buyer problem, owner, explicit acceptance; MQL and SQL timestamps immutable where possible |
| Opportunity | Buyer-confirmed potential commercial outcome with a real next step, pipeline stage and current estimated value if supplied | Define stage entry/exit; separate seller estimate from buyer-confirmed amount; no automatic stage promotion by activity-only signals |
| Won | A signed deal with authoritative date and commercial record, separate from cash receipt | Reconcile CRM event to signed terms and downstream finance/booking source. Do not equate closed-won with realised revenue |
| Realised revenue / retention | Settled/recognised amount and renewals after fulfilment | Finance-issued receipt, service delivery evidence, duplicate settlement protection, attributable entity and time window |

## The first 14 days — scoped diagnostic plan

**Days 1–3:** agree the current stage owners and definitions, audit the list of essential HubSpot objects/properties/workflows in a read-only or least-privilege session once permission is granted, and record a protected baseline. No batch cleanup, import, mass sequencing or destructive changes.

**Days 4–7:** define one lifecycle state dictionary, MQL/SQL acceptance rules, ownership handoff and distinct inbound/outbound/organic attribution. Validate with *real* anonymised aggregate counts and identify where reports disagree. Record every assumption and data gap.

**Days 8–10:** produce a reproducible source → qualification → opportunity → booking → recognised revenue funnel and variance report; reconcile a small buyer-approved sample against CRM and finance receipts.

**Days 11–14:** review highest-value workflow changes with the customer's approved HubSpot implementation owner, obtain change control/rollback signoff, and deliver a short prioritised remediation backlog plus an executive scorecard. Production HubSpot workflows or email sequences are **not** deployed by the audit itself.

## Specific questions worth answering before full implementation

- What exact action moves a lead from MQL to SQL, and who can reject the handoff?
- Is revenue source assigned to the original qualifying touch, the latest assisted touch or both as separate fields?
- Does the forecast include unsigned deals, contracted ARR, settled cash, or several distinct series?
- What counts as a stale deal? Is it age since last meaningful buyer progression, not only time since last activity?
- Which currently operating automation and reporting views would fail if a duplicate property were removed?

**What this sample does not claim:** a private audit, an observed conversion uplift, HubSpot credentials/certification, external customer testimonials or proof of this buyer's revenue leak. Any requested evidence of prior client HubSpot projects must be independently verified, not generated from an EmpireOS internal build. First access is negotiated only after a real client discussion and written scope.

Product reference: https://empire-ai.co.uk/predictive-revenue. Public lead source for comparison: https://www.upwork.com/freelance-jobs/apply/HubSpot-RevOps-Consultant-Needed-Revenue-Operations-Setup-for-B2B-Sales-Team_~022113313008957668345/ . No application or outbound sent.