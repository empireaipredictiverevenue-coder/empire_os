# Partnership Progression / Predictive Revenue Architecture Delta

Date: 2026-10-01
Status: IMPLEMENTATION BOUNDARY APPROVED BY EXISTING FOUNDER DOCTRINE

## Diagram

Observed account / conversation / commercial evidence
-> Partnership Progression
-> Account / Buyer Digital Twin
-> Next-Best-Action context
-> Predictive Revenue decision context

The locked Predictive Revenue equation remains unchanged.

## Canonical responsibility

New owner:
- `empire_os/partnership_progression.py`

Consumers:
- `empire_os/account_digital_twin.py`
- later, `empire_os/next_best_action.py`

Evidence sources may include:
- canonical buyer/account states;
- person-bound identity evidence;
- inbound conversation evidence;
- explicit conversation qualification signals;
- value-proof / pilot evidence;
- verified commercial outcomes;
- explicit opt-out, rejection, no-fit, timing and capacity evidence.

## Positive progression states

`DISCOVERED -> PERSON_BOUND -> PARTNERSHIP_CANDIDATE -> ENGAGED ->
NEEDS_DISCOVERED -> VALUE_PROVEN -> PILOT -> COMMERCIAL_PARTNER -> EXPANSION`

These are evidence states, not a score.

## Negative / non-progress states

- `STOP`: suppression, opt-out or explicit rejection where contact must cease.
- `NO_FIT`: verified capability/economic mismatch.
- `HOLD`: explicit timing or capacity constraint.
- `STALLED`: only explicit evidence that the relationship has stalled.
- `UNKNOWN`: insufficient evidence.

Silence alone is not STALLED.
Friendly wording alone is not ENGAGED.
Qualification score alone is not partnership intent.
Forecast revenue alone is not COMMERCIAL_PARTNER.

## Precedence

Safety / negative evidence has priority:
`STOP > NO_FIT > HOLD > STALLED > positive progression > UNKNOWN`.

A STOP state never authorizes further outreach.

## Evidence contract

Every non-UNKNOWN state requires at least one evidence reference.

Positive stages must be explicitly observed. The engine may select the highest
observed stage, but it does not manufacture missing intermediate stages.

## Output contract

The result contains:
- current state;
- state class (positive / negative / unknown);
- explicitly observed positive states;
- evidence references;
- blockers / reasons;
- no inferred buyer intent;
- no inferred commercial intent;
- no outreach authority;
- no payment authority;
- no execution authority.

## Positive example

A person-bound private-capital contact replies with explicit acquisition
criteria and the reply/transcript is recorded. PERSON_BOUND, ENGAGED and
NEEDS_DISCOVERED may be explicitly observed. The current state can be
NEEDS_DISCOVERED.

## Negative examples

### Capacity hold
A buyer explicitly says capacity is full this quarter. State is HOLD.
Do not infer NO_FIT and do not increase contact pressure.

### Poor economics
Verified expected value is below verified delivery cost. State may be NO_FIT.
Do not call it a partnership win because the buyer was friendly.

### Opt-out
An explicit opt-out produces STOP and suppression remains authoritative.

### Silence
No reply after outreach does not by itself produce STALLED. Without explicit
stall evidence the relationship state remains whatever was previously evidenced
or UNKNOWN.

## Verification

1. deterministic unit tests for every positive stage;
2. STOP / NO_FIT / HOLD / STALLED precedence tests;
3. no-evidence fail-closed test;
4. no inference from silence or generic score;
5. Account Digital Twin integration tests;
6. later NBA integration tests;
7. live OBSERVE snapshot with execution_authority=none.

## Authority

This architecture grants no live outbound, contract, allocation, payment,
settlement, fulfilment, revenue-recognition, migration or production-deploy
authority.
