# Buyer Capacity Learning Architecture Delta

Date: 2026-10-01
Status: IMPLEMENTATION IN PROGRESS

## Diagram

Verified buyer capacity policy
+ observed delivery/outcome windows
-> Buyer Capacity Learning assessment
-> capacity recommendation for operator review
-> existing buyer-capacity policy remains authoritative

No learning result writes daily_cap or activates a buyer.

## Canonical boundary

Existing truth owners:
- buyer_capacity_intake.py: explicit buyer-stated capacity evidence;
- buyer_capacity_readiness.py: current verified readiness;
- buyer_allocation.py: allocation-time capacity enforcement.

New recommendation owner:
- buyer_capacity_learning.py

## Observation contract

Each observation is one buyer/product/market/window and contains:
- offered units;
- accepted units;
- capacity-rejected units;
- quality-rejected units;
- unresolved units;
- observed_at;
- unique observation key;
- evidence refs.

Quality rejection is not capacity exhaustion.
Unresolved demand is not rejection.
Duplicate windows do not increase sample size.

## Learning policy

The learner is OBSERVE-only.

A recommendation requires:
- a verified current capacity limit and capacity evidence ref;
- consistent buyer/product/market identity;
- at least 3 unique outcome windows;
- at least 10 resolved units in aggregate.

Outputs:
- INSUFFICIENT_EVIDENCE;
- MAINTAIN_VERIFIED_LIMIT;
- REVIEW_DOWNWARD.

The learner never recommends above the current verified capacity.

If capacity rejections are observed, it may recommend operator review downward.
The bounded candidate ceiling is no greater than both:
- current verified capacity; and
- highest accepted units observed in any completed window.

If no capacity rejection is observed with sufficient evidence, maintain the
verified limit. This is not evidence that the buyer could accept more.

## Positive example

Verified capacity is 10/day. Across four windows the buyer accepts 7, 8, 8, 7
and explicitly capacity-rejects additional units. Candidate review ceiling is
8, but the buyer record remains unchanged.

## Negative examples

- Quality rejects do not lower capacity.
- Two windows are insufficient evidence.
- Duplicate window observations count once.
- Strong acceptance never raises a verified 10/day cap to 12/day.
- Missing capacity evidence produces no recommendation.

## Verification

- sparse sample fails closed;
- duplicate observations dedupe;
- quality rejection != capacity rejection;
- downward recommendation never exceeds verified capacity;
- no automatic policy mutation;
- readiness/allocation tests remain green.

## Authority

No buyer mutation, allocation execution, outbound, terms, payment, settlement,
revenue recognition, migration, deployment or authority expansion.

## 2026-10-01 verification

Implemented:
- evidence-first buyer/product/market outcome windows;
- duplicate-window dedupe;
- quality rejection separated from capacity rejection;
- minimum sample and resolved-unit evidence thresholds;
- maintain/review-downward recommendations only;
- verified buyer capacity remains authoritative.

Verification:
- learning + buyer readiness + buyer capacity snapshot + allocation + Revenue
  Exchange readiness suites: 50 passed;
- diff check passed;
- no live buyer-capacity-learning outcome stream or projection is currently
  present in runtime, so adaptive production learning is not claimed.

Status:
ENGINEERING COMPLETE / DETERMINISTIC VERIFICATION PASSED /
LIVE OUTCOME LEARNING PENDING REAL EVIDENCE.
