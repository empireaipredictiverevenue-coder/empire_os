# Empire Digital Avatar — Close Authority Delta V1

Date: 2026-10-02
Status: POLICY FOUNDATION / OBSERVE-ONLY

## Purpose

Define the deterministic commercial boundary between an avatar being able to
prepare a close and being authorised to bind the business.

The policy answers:
- is the product delegated?
- is the price evidenced?
- is the discount within limit?
- is the term set explicitly approved?
- is duration/currency allowed?
- is the proposal evidence-backed?
- must the human take over?

Passing policy never overrides the runtime authority gate.

## Rules

The avatar cannot invent a product, price, term, discount or payment condition.
Unknown commercial inputs fail closed.
A proposal outside delegated policy requires human/founder takeover.
A proposal inside policy is only `policy_eligible`; V1 still cannot execute it.

Irreversible acceptance, payment requests, funds movement and recognized revenue
remain governed by their existing EmpireOS authority paths.

## Integration

Meeting strategy -> commercial proposal candidate -> authority assessment
-> private guidance:
- WITHIN POLICY: prepare bounded response/close for human review;
- OUTSIDE POLICY: tell owner exactly which boundary was hit;
- OBSERVE runtime: execution remains false in both cases.
