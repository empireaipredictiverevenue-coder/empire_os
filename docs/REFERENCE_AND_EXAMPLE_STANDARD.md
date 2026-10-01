# Empire AI — Reference & Example Standard

Date: 2026-10-01
Status: CANONICAL OPERATING RULE / FOUNDER APPROVED

## Rule

Every meaningful Empire AI / EmpireOS change must be saved with enough context,
examples and verification evidence that it can be reused without reconstructing
the original chat.

For each material item preserve:

1. Purpose.
2. Decision/change.
3. Canonical owner.
4. Evidence/input.
5. Authority boundaries.
6. Correct-use example.
7. Failure/negative example when relevant.
8. Verification evidence.
9. Reuse path.
10. Date/status.

Do not rely on chat history as the only durable record.

## Example — commercial doctrine

Correct:
- save the partnership-first motion;
- save a contractor example;
- save a private-capital example;
- save a no-fit/negative-economics example;
- save opt-out behaviour;
- link it from Conversation Ops and Predictive Revenue architecture.

Incorrect:
- write “be partnership-first” in chat and leave no canonical reference.

## Example — production fix

Correct:
- record root cause;
- owning production component;
- before/after behaviour;
- focused regression;
- live verification;
- authority unchanged.

Incorrect:
- patch a script and call the system fixed without saving the invariant.

## Example — founder approval

If two contacts are approved:
- save exact contacts/scope;
- prerequisite suppression checks;
- sender identity;
- provider result;
- what was not authorized.

A bounded two-contact approval must never become broad campaign authority.

## Daily close-out

DO WORK -> VERIFY -> SAVE REFERENCE -> ADD EXAMPLE -> LINK FROM OWNER -> CLOSE

If a material change is not saved and reproducible, it is not fully closed.


## Mandatory engineering execution pattern

Every EmpireOS engineering task follows the canonical sequence:

`DIAGRAM -> ARCHITECTURE CONTRACT / DELTA -> WORKER ASSIGNMENT -> IMPLEMENT -> INDEPENDENT VERIFY -> LIVE VERIFY -> CHECKLIST DONE`

For defects, degraded runtime, incidents and recovery:

`OBSERVE -> DIAGNOSE -> CLASSIFY -> PLAN -> ACT -> VERIFY -> RECORD -> RESUME`

This applies even when the apparent fix is small.

### Example — route regression

Wrong:
- see a failing route test;
- edit the service or test immediately;
- stop when the focused test turns green.

Correct:
1. DIAGRAM the request path:
   Founder Console -> Founder Read API -> included router -> target endpoint.
2. ARCHITECTURE DELTA:
   classify whether the defect is production behavior, framework compatibility,
   or stale verification logic.
3. WORKER ASSIGNMENT:
   identify the single owning file/test domain.
4. IMPLEMENT:
   change only the owner necessary to restore the documented behavior.
5. INDEPENDENT VERIFY:
   focused test + adjacent route/API regressions.
6. LIVE VERIFY:
   hit the deployed read-only endpoint and inspect current Founder surface.
7. CHECKLIST DONE:
   record root cause, commit, tests, live evidence and remaining blockers.

### Example — self-heal degradation

Wrong:
- restart inactive units until the dashboard looks green.

Correct:
1. OBSERVE exact degraded checks and timer inventory.
2. DIAGNOSE whether units are intentionally inactive, stale, disabled, failed,
   founder-gated or actually unhealthy.
3. CLASSIFY each unit by authority policy.
4. PLAN the smallest bounded repair.
5. ACT only within already-approved reversible authority.
6. VERIFY service/timer state and produced snapshot.
7. RECORD evidence and root cause.
8. RESUME normal scheduling only after verification.

## No-skipped-gates rule

A passing unit test is not DONE.
A passing build is not DONE.
A successful commit is not DONE.
A running service is not DONE.

DONE means the applicable chain is complete, including live runtime and canonical
data / Founder surface verification where relevant.
