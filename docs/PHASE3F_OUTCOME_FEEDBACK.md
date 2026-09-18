# Phase 3F — Outcome Feedback / Revenue Recognition

Status: implementation and isolated PostgreSQL verification in progress; production activation gated.

## Purpose
Phase 3F closes the commercial learning loop without allowing an AI, API client,
or operator-provided amount to become revenue by assertion.

There are two independent paths:

1. **Outcome feedback** — append-only delivery, conversion and buyer-satisfaction
   evidence. It is non-financial and returns `actual_revenue=false`.
2. **Revenue recognition** — derives revenue, cost and gross profit only from
   canonical fulfilment terms plus independently verified BSC settlement evidence.

## Revenue invariant
Recognized revenue is never supplied by the worker.

For a fulfilment order to produce `revenue_recognized`:
- approved commercial terms must exist on the order;
- the order must have a positive canonical USD price;
- the payment request must remain human-approved;
- direct settlement requires verified BSC USDT transfer evidence;
- escrow settlement requires a verified released escrow;
- request `amount_usdt * 100` must equal the approved `price_cents` exactly;
- commercial terms hashes must match;
- realized margin must remain positive.

Chain overpayment is not silently counted as additional revenue.

## Role separation
- `empire_outcome_recorder` records non-financial outcomes only.
- `empire_revenue_recognizer` lists evidence-backed recognition work and
  recognizes revenue only through the narrow database RPC.
- `service_role` can still append legacy zero-value GTM/qualification events,
  but database guards block it from forging financial commercial events.
- Existing payment/escrow verifier roles still verify chain evidence; they do
  not recognize revenue.

## Immutable history
`commercial_outcomes` is append-only.
`commercial_events` is now database-enforced append-only.
Financial event fields and `revenue_recognized` are reserved for the dedicated
revenue recognizer role.

## Omega / Astra feedback
`get_commercial_outcome_feedback()` projects canonical order outcome data:
- delivery outcome
- conversion outcome
- buyer satisfaction
- actual revenue
- actual cost
- gross profit
- previous purchase
- booked / converted targets

`empire_os/outcome_feedback.py` maps this projection into deterministic learning
features and aggregate business metrics for revenue intelligence and Astra.

## Runtime
`scripts/revenue_recognition_worker.py` runs in `OBSERVE` by default.

It can only execute recognition when:
- mode is `GUARDED_EXECUTE`;
- `--execute` is present;
- the queue reports exact amount matching;
- the dedicated revenue-recognizer DSN is configured.

The worker moves no funds. It recognizes already-verified settlement evidence.

## Production activation gate
Before enabling the runtime:
1. Apply the staged Phase 3E hardening migrations.
2. Apply `20260918123504_phase3f_outcome_feedback.sql`.
3. Apply `20260918124631_phase3f_runtime_identities.sql`.
4. Provision the dedicated outcome/revenue login passwords out of band.
5. Install the revenue recognition service/timer in OBSERVE.
6. Validate live provider/reply events and recognition queue behavior.
7. Promote only the specific workflow after explicit approval.
