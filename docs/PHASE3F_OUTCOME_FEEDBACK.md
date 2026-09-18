# Phase 3F — Outcome Feedback and Revenue Truth

## Purpose
Close the commercial learning loop without allowing models, agents, public API
roles, or unverified external events to manufacture revenue.

## Canonical rules
1. `commercial_events` is append-only. Existing zero-value operational events
   remain compatible, but non-zero financial events require the dedicated
   `empire_revenue_recognizer` role.
2. `commercial_outcomes` is append-only and stores delivery, conversion,
   satisfaction and provenance evidence. Recording an outcome never creates
   revenue.
3. Actual revenue is derived only by `recognize_bsc_revenue()`; callers do not
   provide the revenue amount, cost or margin.
4. Direct BSC/USDT revenue requires an approved payment request plus independently
   verified payment evidence.
5. Escrow funding is not revenue. Escrow revenue requires a verified release.
6. The approved USD order price must equal the USDT settlement amount at the
   canonical commercial accounting basis (USD cents / USDT). A mismatch is held.
7. Acquisition cost + fulfilment cost are taken from the governed order; realized
   margin is derived, not supplied by an agent.
8. Revenue recognition is retry-safe through the commercial event idempotency key
   `revenue:<fulfilment_order_id>:v1`.

## Runtime roles
- `empire_outcome_recorder`: record evidence-backed non-financial outcomes only.
- `empire_revenue_recognizer`: inspect bounded recognition work and recognize
  evidence-backed revenue only.
- `empire_outcome_reader`: read bounded outcome projections and commercial
  figures only; it has no direct commercial table writes or revenue authority.
- Dedicated LOGIN identities are created passwordless and must be provisioned
  out-of-band.

## Learning surface
`get_commercial_outcome_feedback()` exposes a bounded canonical read model with:
- delivery/conversion outcome
- buyer satisfaction
- actual revenue/cost/gross profit
- previous-purchase and conversion labels
- prospect, buyer, opportunity and fulfilment linkage

`empire_os/outcome_feedback.py` maps this read model into features already used
by revenue intelligence and future Astra/Omega calibration.

## Commercial figures
`get_phase3f_commercial_scorecard(p_days)` is the canonical actuals scorecard.
It reports:
- actual revenue, actual cost and gross profit in USD cents
- gross margin rate and percentage
- recognized revenue order count and average recognized order value
- outcome count plus won/lost/booked/qualified/no-response counts
- conversion rate and conversion percentage
- average buyer satisfaction
- revenue, cost, profit and margin by niche/metro
- revenue, cost, profit and margin by buyer
- settlement identity: USDT on BSC

The scorecard contains recognized actuals only. Forecasts and model estimates stay
separate so predicted revenue can never be presented as earned revenue.

`scripts/phase3f_scorecard.py` reads the scorecard only through the dedicated
`empire_outcome_reader` role.

## Worker
`scripts/revenue_recognition_worker.py` defaults to OBSERVE. Even with
`--execute`, mutations occur only in `GUARDED_EXECUTE`, and mismatched economic
amounts remain held.

## Production gates
Before activation:
1. Apply the Phase 3F migration to canonical Supabase.
2. Provision dedicated outcome/revenue/figures-reader login passwords locally.
3. Create `.env.revenue_recognition` from the committed example.
4. Install the revenue-recognition service/timer with OBSERVE defaults.
5. Observe real evidence candidates before promoting recognition to
   `GUARDED_EXECUTE`.
6. Keep payment movement, payment approval and escrow lifecycle verification in
   their existing separated roles.

## Tested locally
- direct verified USDT recognition
- released escrow recognition
- funded escrow rejected as revenue
- exact amount mismatch hold
- forged service-role revenue rejection
- append-only commercial events and outcomes
- idempotent recognition
- canonical feedback projection
- hard-figures scorecard with revenue/cost/profit/margin/conversion/satisfaction
  and buyer/niche segmentation
- dedicated read-only scorecard identity
