# Empire AI — incoming data to specialist department review

**17 October 2026 | Founder request | Build within existing architecture, not another data bus or agent.**

## Observed gap

EmpireOS runs acquisition, NYC permit ingest, Buyer Scout, market/research loops,
Opportunity Radar, AI planning and the existing `empire-department-cycle.timer`.
However, Opportunity Radar did not directly pick up the 7,726 retained NYC permit
signals; its market radar mostly used aggregate market/community/TAM/competitor
snapshots. This meant official project data were retained without a dependable
new-batch, permit-specific department receipt.

Existing `runtime/acquisition/signal_inbox.json` is not a verified CRM contact
list or a ledger of paid opportunities. The 7,726 known permit signals are
historical/current retained observations from the official NYC building portal;
at a 17 October ~21:25 UTC audit **99 were observed/refreshed within the last
24h** and **23 were first recorded in the last 24h**. These are NOT 7,726 new
buyer leads. Source references and actual owner/permittee identity must be
validated before a product offer claims a commercial opportunity.

## Exact reused execution path

Existing source/acquisition writer -> existing durable signal inbox ->
`source_intelligence_handoff.py` (bounded, quality-first, PII-stripping,
source-change fingerprint) -> **existing** `DepartmentWorkQueue` with the existing
14 department identifiers -> `department_worker.py` safe review receipt ->
Founder dashboard's existing department-cycle status / private source snapshot.

Only `run_department_cycle` was extended: it invokes this router in its existing
heartbeat, before the current worker. It does not add a timer, service, database,
webhook, outbound email, paid model/provider, money movement or contact import.
The noncanonical/scratch caller is denied production routing by default.

## Specialist routes and interpretation

| Data lane | Existing department | Current source evidence and actionable research |
| --- | --- | --- |
| Permit | `market_intelligence` | Observe NEW vs refreshed official project data; distinguish total, resolved and unresolved records; review sector, verified business identity, project stage, site and credible first-party buyer need. |
| Property | `product` | Same underlying permit observations plus separate physical evidence; never count twice; verify property entity/owner identity and an actual project before modelling property opportunities. |
| Private Capital | `strategy` | Missing canonical sponsor/portfolio evidence. Reconcile the EmpireDB reader; current 0 signals, 0 memberships is a source gap, not absence of a real-world market. |
| Storm | `data_quant` | Old Oct 5 storm opportunity snapshot is stale/untrusted for current routing; verify official weather, geography and age. Storm exposure is not proof of property damage. |
| Warehouse/Industrial | `market_intelligence` | Existing parked Warehouse Sniper / industrial/idle-asset readers need source and location proof; source-integration task, no live industrial opportunities invented. |

Existing Buyer Scout, SEO/Marketing, Gmail reply pipelines and other Opportunity
Radar streams **retain their current owners** and are not duplicated. These
five source quality routes are a FIRST incremental bridge, not a claim that all
14 teams now receive every conceivable event.

## Deduplication and work safety

- At most **three new specialist review work items per department cycle**.
- At most **one queued review per lane per UTC hour**; meaningful source
  signatures must change to deliver another.
- Existing queue deterministic `plan_id=source_intelligence_review_v1`,
  scoped step identity, flock and atomic writes handle parallel invocations.
- The source signature includes trusted bounded source status, explicit
  aggregate quality counts, evidence refs and stable blockers. Routine
  heartbeat timestamps, raw owner data, emails, names and source age display
  must not trigger repeated jobs. NYC source triage separately counts all
  7,726 retained records, the 99 observed/refreshed within 24h and 23
  first recorded within 24h; job type codes are aggregate only (the initial
  new cohort included A2:9, A1:7, NB:3, SG:2 and A3:2).
- Each automatic ticket costs **0 model tokens and 0 external money**; the
  worker uses the existing budget/safety gates. As verified in the current
  runtime, the model-token allocation for specialist departments is not
  configured. A narrowly constrained local Qwen shadow selector has code and
  negative-response tests but **cannot run automatically until model tokens
  are explicitly budgeted through the existing ledger**. Do not bypass this
  by treating local tokens as having no resource cost.
  Source contract is checked against
  the *currently published* private packet; wrong team, fake or superseded
  fingerprints are blocked.
- Worker completion means **the first-pass internal source-analysis receipt
  was delivered**, not that a human department member, LLM, business buyer,
  policyholder, storm insurance claim, contractor enrolment or transaction was
  validated.
- A future bounded **semantic AI interpretation step** uses the already
  installed local llama.cpp adapter, only when the department budget ledger
  and source-provenance controls permit it. It selects an index from fixed
  research actions, never generates unreviewed source claims. Current
  automatic tickets explicitly set model usage to zero; the daily source
  screening is deterministic and `semantic_model_review_performed=false`
  unless a separately budgeted, validated local shadow run genuinely occurs.
- Each real buyer, customer, property, company or project identity must be
  independently bound to authorised original source before contact or
  distribution. Insurance claims and personal legal/patient details are not
  touched.

## Founder / production source truth

Generated private review:
`runtime/departments/source_intelligence_latest.json`

Stable source-change state:
`runtime/departments/source_intelligence_dispatch_state.json`

Existing aggregate:
`runtime/astra/department_cycle_latest.json`, field
`source_intelligence_handoffs`

All source/dispatch files are private 0600. The source packet includes no
personal owner records, just lane, owning team, bounded counts, status, evidence
reference, blockers, fingerprint and queue work receipt.

Production activation is simply source promotion to the existing canonical
`/srv/empire_os` and the next scheduled **oneshot** department-cycle timer.
No daemon restart. Verify post-activation review receipts and unchanged buyer,
payment and outbound states before claiming it live.

Tests:
`/srv/empire_os/.venv/bin/python -m pytest -q
tests/test_source_intelligence_department_handoff_20261017.py
tests/test_department_cycle.py tests/test_department_worker.py
tests/test_department_work_queue.py tests/test_permit_intelligence_runtime.py
tests/test_founder_vertical_intelligence_api.py tests/test_opportunity_loop.py`

## Next milestone beyond source routing

1. **Permit team:** pick 1–3 genuinely recent NYC permit IDs and construct
   original official-source project/owner/company evidence packets without
   personal contact data leakage. Resolve whether anything has commercial
   value to roofing, HVAC, construction or industrial data buyers.
2. **Property team:** use the same permits where canonical BIN/BBL/geography
   actually matches verified property observations; avoid 7,726 duplicate
   opportunities.
3. **Strategy:** replace retired private-capital adapter with verified
   EmpireDB source and original corporate evidence.
4. **R&D/Market:** source official bounded storm/warehouse geo evidence.
5. **Deeper AI:** given only qualified, provenance-backed shortlisted packets,
   run *existing local model/router* for hypotheses, cross-market patterns
   and useful research recommendations, with results checked against sources.
6. **Sales:** only forward genuine business/company opportunities with
   recipient/source provenance, established payer terms and suppression
   into CRM; do not auto-send. Verified order/payment/fulfilment outcomes
   flow to existing Economic Memory, not estimated revenue.

This is the start of a functioning continuous intelligence handoff, not a
replacement for the currently scheduled Opportunity Radar, Astra departments,
or canonical EmpireDB governance.
