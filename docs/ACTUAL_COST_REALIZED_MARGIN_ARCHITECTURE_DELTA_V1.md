# Actual Cost -> Realized Margin Architecture Delta V1

## Problem

The current revenue-recognition function calculates event cost from
fulfilment_orders.acquisition_cost_cents plus fulfilment_cost_cents. Those
values are written during commercial-terms approval and can represent verified
expected/budget economics. They are not proof that the costs were actually
incurred.

Calling a margin derived only from those terms-time values "realized margin"
violates the Empire production-truth rule.

## Truth contract

Expected terms-time economics remain unchanged and auditable.

Before a new revenue_recognized commercial event can be created, the fulfilment
order must have both:
- one verified acquisition_cost evidence row bound to that fulfilment order;
- one verified fulfilment_cost evidence row bound to that fulfilment order.

Both actual-cost rows must use source_type provider_invoice or internal_actual.
An actual zero cost is valid but must still be explicitly evidenced with an
amount_cents=0 row. Missing evidence is UNKNOWN, never assumed zero.

The revenue event cost_cents is the sum of those two observed actual amounts.
The event margin_cents is recognized price minus observed actual cost. The
fulfilment order actual_margin_cents may then be set to that realized value.

The revenue-event payload must retain both actual cost evidence IDs,
source types and source references so the realized margin is auditable.

## Payment and revenue boundary

Verified BSC USDT settlement evidence remains mandatory and unchanged.
Approved commercial terms hash and paid amount must continue to match the
fulfilment order.

Actual-cost hardening does not grant payment authority or revenue-recognition
authority. Only the existing empire_revenue_recognizer capability may call the
recognition RPC.

If payment is verified but actual costs are not yet evidenced, the recognition
call fails closed with a bounded missing-actual-cost error. The order remains
eligible for later retry after cost evidence arrives.

## Idempotency

An already-created canonical revenue event remains authoritative. Retrying an
already recognized order returns the existing event and does not require new
cost evidence or mutate history.

## Migration

Migration 029 replaces only the existing recognize_bsc_revenue(uuid,text)
implementation. It does not alter historical events and does not backfill
costs. The migration is HELD until explicit database activation approval.

## Acceptance

Executable PostgreSQL tests must prove:
- terms-time costs alone cannot produce a new realized-margin event;
- verified order-bound provider_invoice/internal_actual evidence is required;
- explicit zero actual cost is accepted;
- realized event cost/margin use actual evidence, not terms-time estimates;
- evidence IDs/provenance are embedded in the event;
- unbound, pending, or non-actual source evidence is rejected;
- idempotent existing recognized revenue remains unchanged;
- no extra runtime role receives recognition authority.
