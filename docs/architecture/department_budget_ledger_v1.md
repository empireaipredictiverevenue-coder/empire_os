# Department Budget Ledger v1 — Architecture Contract

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Astra Executive / Department Operating System

## Purpose
Complete the existing durable department work queue with a bounded, auditable
resource-budget ledger. The ledger governs agent/model resource usage only. It
never grants company cash-spend, outbound, payment, commercial-terms, allocation,
deployment or revenue-recognition authority.

## Canonical flow

```text
Astra Executive plan
  -> DepartmentWorkQueue claim + atomic lease
  -> DepartmentBudgetLedger.reserve(work attempt)
       -> no resource request: ALLOWED / no reservation required
       -> explicit resource request + missing cap: BLOCKED
       -> request exceeds remaining cap: BLOCKED
       -> within configured cap: RESERVATION RECORDED
  -> existing DepartmentWorker adapter / Execution Plane
  -> terminal queue state
  -> budget snapshot classifies reservation as consumed
  -> Astra evaluator includes budget status
  -> monthly Founder/operating review
```

## Budget scope
Supported governed resource dimensions:
- `model_tokens`
- `external_cost_cents`
- work-attempt counts (observed operational load only; not a spend authority)

A work item may request budget only through:
`intelligence_request.budget.requested_model_tokens`
`intelligence_request.budget.requested_external_cost_cents`

Optional policy source:
`config/department_budgets.json`

Policy values are never invented. If a requested dimension has no configured cap,
that request is blocked as `*_budget_unconfigured`. Missing budget is not zero and
not unlimited.

## Atomicity / idempotency
Reservations are append-only JSONL under:
`runtime/departments/budget/reservations.jsonl`

A file lock protects read-check-append. Reservation identity is deterministic from
`work_id + attempt`, so retries are separate resource attempts but duplicate writes
for the same attempt are idempotent.

## Accounting semantics
- A reservation for a RUNNING attempt is reserved usage.
- Once its work item is DONE/BLOCKED/FAILED/REVIEW, the reserved amount is treated
  as consumed conservatively.
- If terminal result contains observed `resource_usage`, accounting uses the greater
  of observed usage and the reserved amount so under-declaration cannot create
  artificial headroom.
- Unknown actual usage remains explicit; requested reservation is the accounting
  floor.
- Company totals count each reservation once. A cross-department reservation is
  charged to every participating department for departmental headroom.

## Policy schema

```json
{
  "schema_version": "empire.department-budget-policy.v1",
  "period": "monthly",
  "company": {
    "model_tokens": null,
    "external_cost_cents": null
  },
  "departments": {
    "engineering": {
      "model_tokens": 1000000,
      "external_cost_cents": 0
    }
  }
}
```

`null` means UNCONFIGURED, not unlimited.

Budget policy changes remain a Founder/governance decision. This implementation
only reads policy and enforces it.

## Snapshot
Materialize:
`runtime/departments/budget/latest.json`

Expose per-company and per-department:
- configured limits;
- reserved usage;
- consumed usage;
- remaining headroom when known;
- work attempts;
- state: `UNCONFIGURED | WITHIN_BUDGET | EXHAUSTED`;
- budget-policy reference;
- cash-spend authority=false;
- execution_authority=none.

## Worker integration
Budget preflight happens after queue claim and authority safety check, before any
adapter/model/provider work. A denied request becomes a normal BLOCKED department
work item with evidence; it is not retried blindly.

Existing work items with no explicit token/external-cost request continue exactly
as today.

## Review cadence
The existing 2-minute department evaluator refreshes the budget snapshot. Monthly
period keys (`YYYY-MM`) provide the operating review boundary without deleting
historical reservations.

## Verification
- no-budget internal work remains allowed;
- explicit token/cost request blocks when cap is unconfigured;
- configured caps reserve atomically and deny over-budget requests;
- duplicate reserve for same work attempt is idempotent;
- terminal attempts become consumed in the snapshot;
- cross-department accounting is deterministic;
- no cash-spend/payment/outbound/revenue authority is introduced;
- evaluator exposes the live budget snapshot;
- current production runtime materializes truthful UNCONFIGURED/observed state.
