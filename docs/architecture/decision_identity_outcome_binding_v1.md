# Decision Identity → Verified Outcome Binding V1

Empire separates recommendation, execution and commercial outcome truth.

A decision identity records which decision/prediction/model/provider was
involved. It grants no execution authority.

## Causal requirements

Decision-level commercial attribution requires all of the following:

1. a valid stable decision identity;
2. a non-shadow decision;
3. explicit selection/authority evidence;
4. independently recorded execution evidence;
5. execution evidence matching the completed department work item;
6. an explicit `causal_outcome_refs` link from that work item;
7. a matching verified, non-synthetic Cortex commercial outcome.

Missing any one of these conditions prevents decision-level causal credit.

## Shadow invariant

Hybrid Compute V4 remains shadow-only. Its recommendations may receive stable
decision IDs for later comparison, but:

- `execution_performed = false`
- `causal_eligible = false`
- `selection_authority_ref = null`
- `execution_authority = none`

A shadow identity cannot be converted into an executed identity.

## Prediction linkage

`prediction_ref` is carried through the decision identity when available, so a
future verified outcome can be traced:

`prediction_ref → decision_ref → execution_ref → outcome_ref`

This is evidence attribution only. It does not mutate model weights, activate
providers, send outbound, bind commercial terms, recognize revenue, move funds
or change production routing.
