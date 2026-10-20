# Empire AI — Predictive Revenue Original Forecast ↔ Outcome Measurement Handoff

**20 October 2026 | Owner: existing Predictive Decision Control feature branch**
**Status:** deterministic, read-only research gate; not deployed, not authenticated commercial measurement.

## Why

Predictive Revenue's prime economic loop is **Predicted Gross Profit → Realized Gross Profit → Prediction Error → Better Allocation**. Market research, Storm events, owner-reported purchase receipts, customer-value before/after observations, an expected-profit scenario and a mocked conversion-registry readback are **distinct forms of evidence**. Without the same original prospectively recorded pilot/tenant/product/horizon and an independently authenticated purchase, no model improvement or measured ROI can be claimed.

The prior Storm/measurement work introduced a live 27-field readiness scorecard across Market GPS, Storm, Quant and Economic Memory; it correctly refuses to use the 5 October stale Storm snapshot as current weather or demand. This next increment closes a different gap: precisely reviewing a **single proposed pilot experiment** across existing commercial and scientific owner packets.

## Added

`empire_os/predictive_profit_outcome_instrument.py`

`review_profit_outcome_instrument(pilot,scenario,commerce,customer_value,registry_readback,as_of=...)`

The pure adapter requires the unchanged original owner contracts:

- `empire.predictive.customer_value_pilot_preflight.v1`, prospective pilot design **not registered**
- `empire.predictive_revenue.profitability_playbooks.v1`, explicitly hypothetical downside/base/upside economics matching the original opportunity and design SHA256
- `empire.predictive.customer_value_commerce_evidence.v1`, owner-reported unverified purchases, refund claims and delivery costs
- `empire.predictive.customer_value_measurement_evidence.v1`, owner-reported unverified before/after treatment/control observations
- `empire.original_conversion_registry_readback_review.v1`, original Quant readback consistency **not authenticated** even if the supplied dictionary/hash appears to match

The new instrument counts only clearly labelled **claims**: paid event and reversal claims, owner-estimated net after reversals and variable costs, paired treatment/control receipt counts, and claimed between-arm difference. It retains the scenario's hypothetical weighted operating profit separately and never subtracts these owner claims from the profit model to manufacture a prediction-error result. A booking is not revenue, a mocked receipt is not genuine settlement, a matching SHA256 is not proof of a signed source or DB role, and a measured association is not a verified causal lift.

Important missing proof before actual accuracy / profitability can be measured:

1. Original pilot design independently registered before outcomes.
2. Authenticated and independently read-backed original prospective Quant prediction, not caller-supplied matched dictionaries.
3. Real source custody linking the original tenant, opportunity, pilot design SHA256, purchased unit, model, prediction reference and horizon. Current source-owner reports claim pilot-match booleans but don't expose a cryptographically verified independent binding; the Quant registry does not prove a pilot design link.
4. Proof prediction preceded the actual eligible outcome, not a merely plausible clock.
5. Signed/authenticated source commerce settlement, refunds, paid units, cost attribution and complete negative outcomes; real gross/operating profit must come from existing Finance/Commerce owners.
6. Consent and original experimental arm allocation, authentic baseline/control, complete follow-up and negative outcomes from Customer Success.
7. Independently joined original forecast and settled cohort outcome before any Brier/error/calibration or Economic Memory learning.

**Output is always** `model_calibration_authorized=false`, `measured_gross_profit_minor=null`, `measured_operating_profit_minor=null`, `matched_original_forecast_and_outcome_pairs=null`, `profit_prediction_error_minor=null`, `conversion_brier_score=null`, `economic_memory_outcome_written=false` and no database/outbound/spend authority.

## Source ownership / integration

No changes to original `original_conversion_registry.py`, Quant, Commerce, Customer Success, Storm, Market GPS, Finance, Economic Memory, database roles, timers, services or external apps.

This is a **reusable measurement handoff for a single experiment**, not a new daemon or artificially populated dashboard. The current runtime has no authenticated experiment receipts/forecast to supply; samples and tests are synthetic. Existing `scripts.review_predictive_measurement_instruments_20261020 --read-only` remains the live aggregate instrument, while this function is designed to accept the original owners' future source packets when they exist and are permitted.

The commercial system should first create a real independently attributable pilot forecast with the proper source-owner custody; then the existing owner can bring a complete separate outcome packet to the same measurement gate. Until then the source proof gates remain open, rather than showing fabricated zero sales or perfect model accuracy.

## Verification

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_predictive_profit_outcome_instrument.py \
  tests/test_predictive_customer_value_commerce_evidence.py \
  tests/test_predictive_customer_value_measurement_evidence.py \
  tests/test_original_conversion_registry.py \
  tests/test_predictive_profitability_playbooks.py
```

No external packages installed, no new service or cost and no production changes.
