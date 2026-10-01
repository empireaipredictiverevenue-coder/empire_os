# Zero-Cash Operating Mode Architecture Delta

Date: 2026-10-01
Status: IMPLEMENTATION IN PROGRESS

## Diagram

Verified collected/available cash evidence
+ reservations/obligations
+ verified commercial product readiness
+ action incremental-cash requirement
-> Zero-Cash Operating Policy
-> recommendation-only commercial action shortlist

Forecast revenue never enters available cash.

## Purpose

Zero-Cash Mode means capital-efficient operation when no new discretionary cash
is available. It does not mean Empire has zero costs.

Preferred actions:
- sell already-built verified products;
- use owned/public evidence already available;
- use relationship-first partnership conversations;
- avoid paid acquisition until collected cash and budget authority exist.

## Boundary

Existing Capital Allocator remains for actions that require positive capital.

New owner:
- zero_cash_operating_policy.py

No capital arithmetic is changed in capital_allocator.py.

## Cash truth

Inputs may include:
- verified collected/available cash;
- reserved/obligated cash;
- evidence refs;
- explicit budget authority.

Recognized revenue, predicted revenue, proposed price, pipeline value and
expected revenue do not establish available cash.

Spendable cash:
max(verified available cash - verified reservations, 0).

Unknown cash remains unknown.

## Candidate contract

Each candidate supplies:
- action key;
- product code;
- binding_terms_ready;
- incremental_cash_requirement_cents;
- total_cost_cents when known;
- whether paid acquisition is required;
- whether owned/public evidence can support the action;
- evidence refs.

Unknown total cost is preserved separately. A zero incremental-cash action is
not described as zero-cost.

## Decisions

- ELIGIBLE_ZERO_INCREMENTAL_CASH
- ELIGIBLE_WITH_VERIFIED_CASH
- BLOCKED_BUDGET_AUTHORITY
- BLOCKED_INSUFFICIENT_CASH
- BLOCKED_PRODUCT_NOT_READY
- UNKNOWN_CASH_REQUIREMENT

Paid actions require both verified spendable cash and explicit budget authority.

## Positive example

Permit Intelligence is already verified and can be discussed/sold using owned
permit evidence with no new ad spend. Incremental cash requirement is zero.
The action may be recommended while fulfilment cost remains separately known or
unknown.

## Negative examples

- £0 available cash + high forecast revenue does not authorize PPC spend.
- Unknown acquisition cost is not CAC=0.
- Reserved cash cannot be reused for another action.
- Zero incremental acquisition spend does not imply zero fulfilment cost.
- Draft/unverified product is not eligible merely because it costs no cash to
  mention.

## Verification

- forecast revenue ignored as cash;
- reserved cash cannot be double-spent;
- unknown costs remain unknown;
- paid action requires cash and budget authority;
- zero incremental action can be recommended without claiming zero total cost;
- commercial catalog and capital allocator regressions remain green.

## Authority

Recommendation only. No spend, budget mutation, payment, settlement, outbound,
terms acceptance, fulfilment, revenue recognition, migration or deployment
authority.

## 2026-10-01 verification

Implemented:
- verified spendable-cash arithmetic;
- reservations separated from available cash;
- zero incremental cash distinguished from zero total cost;
- paid actions require both verified cash and explicit budget authority;
- forecasts, pipeline value and expected revenue never become cash;
- recommendation-only authority.

Verification:
- Zero-Cash + Capital Allocator + commercial catalog suites: 22 passed;
- no live spend, budget mutation or payment action executed;
- no live Zero-Cash decision is claimed until verified cash/reservation evidence
  is explicitly bound to the policy.

Status:
ENGINEERING COMPLETE / DETERMINISTIC VERIFICATION PASSED /
LIVE CASH-EVIDENCE DECISION PENDING CANONICAL INPUT.
