# Founder Operational Truth — Architecture Delta

Date: 2026-10-01
Status: CANDIDATE / READ-ONLY

## Purpose

Give the founder one unambiguous surface showing each revenue lane as
LIVE, READY, GATED, BLOCKED, OBSERVE, or UNKNOWN.

The board explains the exact blocker/gate and next action. It does not
change authority or infer commercial outcomes.

## Canonical placement

Owner: Founder Console / Control Fabric read layer.
Inputs: existing canonical runtime snapshots only.
Output: read-only /v1/founder-operational-truth/status.
UI: top section of the existing Founder Console.

No new database, queue, service, business store, or execution engine.
## Truth contract

The reader uses:
- Revenue Pulse;
- Sell Now;
- Buyer Acquisition;
- Commercial Exchange;
- Owned Campaign V2 preflight;
- static governed A2A commercial activation contract.

Missing data stays UNKNOWN. Revenue stays zero unless verified revenue
evidence already says otherwise.

Lane states describe operational readiness, never revenue probability.

## Authority contract

Read-only. No sends, migrations, allocation, payment, settlement,
revenue recognition, service restart, deployment, or authority expansion.

Founder gates are surfaced, not bypassed.
## Failure behaviour

Missing or invalid snapshots degrade only the affected lane to UNKNOWN.
No retries and no side effects.

## Verification

Focused tests cover:
- blocked buyer conversation;
- 26 ready products / zero Sell Now;
- owned campaign DB founder gate;
- A2A commercial activation gate;
- missing snapshot behaviour;
- summary counts and authority invariants.

Adjacent checks:
- Founder Dashboard service route tests;
- TypeScript compile/build for Founder Console.

Promotion still requires independent verification and live Founder
surface verification.
