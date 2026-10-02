# Predictive Revenue JEV Signal-to-Output v1 — Architecture Contract

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Predictive Revenue / Data & Quant

JEV is the working label for EmpireOS's canonical signal-to-output composition
layer. This contract does not assume or require an expansion of the acronym.

## 1. Purpose

Convert one evidence-backed signal into one deterministic, typed commercial
recommendation packet without creating another scoring formula or granting any
consequential authority.

Canonical chain:

SIGNAL
→ PROVENANCE / FRESHNESS / TRUTH CLASS
→ OPPORTUNITY EVIDENCE NORMALIZER
→ QUANT BRAIN ECONOMICS
→ PREDICTIVE REVENUE ERV (WHEN EVIDENCE EXISTS)
→ NEXT-BEST-ACTION VALUE (WHEN ACTION EVIDENCE EXISTS)
→ TYPED OUTPUT
→ AUTHORITY GATE

JEV composes existing canonical owners. It does not replace them.

## 2. Canonical owners reused

- `empire_os.opportunity_evidence_normalizer`
  - normalized signal dimensions;
  - score evidence;
  - quant inputs;
  - verified-outcome probability semantics.
- `empire_os.quant_brain`
  - `expected_economics(...)`;
  - `risk_adjusted_score(...)`.
- `empire_os.predictive_revenue_formula`
  - `expected_revenue_value(...)`;
  - `next_best_action_value(...)`.
- Revenue Exchange / Marketplace / Auction / Buyer Matching
  - downstream consumers only;
  - JEV has no execution authority over them.
- Economic Memory / Revenue Truth
  - verified outcome sources only;
  - forecasts are never written as outcomes.

## 3. System diagram

```text
Observed / modeled signal
        |
        v
Signal envelope
(id/type/time/truth/evidence)
        |
        v
Opportunity Evidence Normalizer
        |
        +--> normalized scores + semantic class
        +--> quant inputs + evidence
        |
        v
Quant Brain
(expected revenue/cost/GP + risk-adjusted score)
        |
        +--> Predictive Revenue ERV when full ERV inputs exist
        +--> NBA ranking when evidenced actions exist
        |
        v
JEV typed recommendation packet
        |
        +--> OPPORTUNITY_CREATE
        +--> BUYER_MATCH_REVIEW
        +--> BID_PROPOSAL
        +--> PRICING_REVIEW
        +--> OUTREACH_REVIEW
        +--> CAMPAIGN_REVIEW
        +--> RESEARCH_REQUIRED
        +--> HOLD
        +--> NO_ACTION
        |
        v
Existing downstream authority gate
```

## 4. Input contract

### Signal envelope
Required:
- `signal_id`
- `signal_type`
- `observed_at`
- `truth_class`
- at least one `evidence_ref`

Supported truth classes in v1:
- `OBSERVED`
- `MODELED`
- `POLICY`
- `INFERRED`

Truth class is descriptive only. It is never converted into probability.

### Normalized opportunity packet
JEV consumes an existing Opportunity Evidence Normalizer row. It does not
re-normalize raw data.

Relevant fields:
- `opportunity_key`
- `opportunity_class`
- `normalized_signals`
- `score_evidence`
- `quant_inputs`
- `quant_input_evidence`
- `probability_modeled_from_verified_outcomes`
- `execution_authority`

### Optional Predictive Revenue ERV inputs
If supplied, JEV calls `expected_revenue_value(...)` directly.
Missing ERV evidence remains UNAVAILABLE.

### Optional action candidates
If supplied, JEV calls `next_best_action_value(...)` directly.
An action may additionally carry one of the allowed `output_type` values. JEV
uses that metadata only if that action becomes the canonical NBA recommendation.

## 5. Quantitative evidence rule

For a commercially actionable value packet, the normalized row must contain:
- `probability_success`
- `conditional_revenue_cents`
- `fixed_cost_cents`
- `success_cost_cents`
- `uncertainty`
- `time_to_revenue_days`
- `confidence`

and:
- `probability_modeled_from_verified_outcomes == true`.

Missing values stay UNKNOWN.
Signal strength or normalized demand scores are never substituted for probability.

## 6. Canonical calculations

JEV does not create a new mathematical scoring formula.

It calls:

```text
Quant Brain expected_economics(...)
```

to expose:
- expected revenue;
- expected cost;
- expected gross profit;
- failure downside.

It calls:

```text
Quant Brain risk_adjusted_score(...)
```

to expose the existing risk/time/confidence-adjusted recommendation score.

When complete ERV inputs are supplied it calls:

```text
Predictive Revenue expected_revenue_value(...)
```

and exposes the returned ERV separately.

When actions are supplied it calls:

```text
Predictive Revenue next_best_action_value(...)
```

and exposes the canonical recommended action separately.

These values are not averaged, multiplied, blended or replaced by a JEV-specific
score.

## 7. Output selection rule

Selection is deterministic.

1. If signal evidence is missing or stale:
   - `RESEARCH_REQUIRED`.
2. If required quant evidence is missing or probability is not backed by verified
   outcome modeling:
   - `RESEARCH_REQUIRED`.
3. If quant economics are complete but expected gross profit is <= 0:
   - `HOLD`.
4. If canonical NBA has a recommended action with an allowed explicit
   `output_type`:
   - use that output type.
5. Otherwise, if `distribution_path == approved_buyer_network`:
   - `BUYER_MATCH_REVIEW`.
6. Otherwise, for positive complete economics:
   - `OPPORTUNITY_CREATE`.

`NO_ACTION` is reserved for callers that explicitly provide a canonical NBA
recommendation with `output_type=NO_ACTION`; JEV does not silently classify a
lack of evidence as NO_ACTION.

## 8. Allowed output types

- `OPPORTUNITY_CREATE`
- `BUYER_MATCH_REVIEW`
- `BID_PROPOSAL`
- `PRICING_REVIEW`
- `OUTREACH_REVIEW`
- `CAMPAIGN_REVIEW`
- `RESEARCH_REQUIRED`
- `HOLD`
- `NO_ACTION`

## 9. Freshness

JEV accepts `as_of` and `max_signal_age_seconds`.

- future timestamps fail closed;
- invalid timestamps fail closed;
- age above the threshold adds `signal_stale` and forces
  `RESEARCH_REQUIRED`;
- freshness never changes commercial truth or revenue state.

## 10. Evidence lineage

The output packet preserves deduplicated refs from:
- signal envelope;
- score evidence;
- quant-input evidence;
- predictive-intelligence evidence;
- optional ERV caller evidence;
- optional action evidence.

No evidence ref means no actionable JEV output.

## 11. Output packet

Required fields:
- signal identity / type / truth class / age;
- opportunity key / class;
- output type;
- normalized signals;
- probability success or UNKNOWN;
- conditional revenue or UNKNOWN;
- expected revenue/cost/GP or UNKNOWN;
- risk-adjusted score or UNKNOWN;
- Predictive Revenue ERV packet or UNAVAILABLE;
- NBA packet or UNAVAILABLE;
- recommended action;
- blockers;
- evidence refs;
- freshness;
- `recommendation_only=true`;
- `actual_revenue=false`;
- `execution_authority=none`.

## 12. Truth boundaries

- Signal strength is not probability unless calibrated evidence supports it.
- Bid amount is not expected value.
- Forecast expected value is not actual revenue.
- Conditional revenue is not guaranteed revenue.
- Policy economics are not observed realized economics.
- Recommendation is not authority.
- JEV cannot allocate inventory.
- JEV cannot change pricing.
- JEV cannot send outreach.
- JEV cannot accept terms.
- JEV cannot move funds or settle payment.
- JEV cannot create fulfilment authority.
- JEV cannot recognize revenue.

## 13. Authority contract

Always:
- `mode=OBSERVE`
- `recommendation_only=true`
- `actual_revenue=false`
- `execution_authority=none`
- `allocation_execution=false`
- `pricing_mutation=false`
- `outbound_action=false`
- `terms_acceptance=false`
- `payment_action=false`
- `settlement_action=false`
- `fulfilment_execution=false`
- `revenue_recognition=false`

## 14. Files

Canonical module:
- `empire_os/predictive_revenue_jev.py`

Focused tests:
- `tests/test_predictive_revenue_jev.py`

## 15. Regression verification

Required:
- `tests/test_predictive_revenue_jev.py`
- `tests/test_predictive_revenue_formula.py`
- `tests/test_quant_brain.py`
- `tests/test_opportunity_evidence_normalizer.py`
- `tests/test_action_portfolio_optimization.py`
- `tests/test_revenue_exchange_optimization_bridge.py`
- `tests/test_opportunity_auction.py`

## 16. Completion condition

JEV v1 is complete only when:
- one evidence-backed signal compiles deterministically to a typed packet;
- complete verified quant evidence yields canonical Quant Brain economics;
- missing probability/economics stays UNKNOWN and returns RESEARCH_REQUIRED;
- stale evidence returns RESEARCH_REQUIRED;
- negative expected GP returns HOLD;
- an approved-buyer distribution path returns BUYER_MATCH_REVIEW when positive;
- an explicit evidenced NBA output type is preserved;
- evidence lineage is present;
- all consequential authority remains false/none;
- independent and live verification pass.
