# Empire AI Predictive Revenue — Measurement Instruments + Storm Product

**20 October 2026 | Predictive Decision Control isolated feature worktree**
**Source HEAD before this change:** `d8c28de0`
**Status:** Built as read-only adapter and evidence scorecard, not deployed or used to send, spend, retrain or recognise profit.

## Why Storm belongs in the original Predictive Revenue architecture

The Empire AI Storm product is an existing sensor/decision product. Its observed events and evidence can help Research, Market Knowledge, Spatial Intelligence, Economic Twins, Forecasting and Commercial Strategy study whether severe weather changes plausible maintenance/roofing/HVAC/plumbing demand and economics. Storm sensing is **not** evidence of actual building damage or signed purchasing interest.

The future legitimate feedback loop is:

1. An original permitted storm/weather observation with origin, timestamp, truth class and area
2. Original geospatial/property or business exposure, including licensing and evidence-rights verification
3. Canonical location match to an eligible service/product market, not text matching alone
4. Original contractor's ability to provide service, real materials/labour costs, buyer terms and capacity
5. Pre-outcome, independently registered original conversion / price / gross-profit forecast
6. Controlled, authorised intervention or offer (if approved by the original commercial owner)
7. Authenticated completed appointment/sale, payment, refund, service outcome and actual attributable gross profit
8. Measured forecast error, counterfactual/control comparison and Economic Memory update

Steps 1–3 are currently **incomplete** as an authenticated production chain; steps 4–8 are not established by the cached Storm snapshot.

## Existing Storm code reused without changes

- `storm_intelligence_runtime.py` generates `runtime/storm_opportunity/latest.json` under `empire.storm_opportunity_snapshot.v1` with `runtime_schema_version=empire.storm_intelligence_runtime.v1`.
- `storm_product_integration.py` owns event, affected subject, buyer/product match and readiness gates.
- `storm_opportunity_bridge.py` owns opportunity research handoff to Radar (without commercial activation).
- `storm_revenue_multiplier.py` models priority boosts, **not proven sales**.
- Spatial/Physical Intelligence and Digital Twin modules remain separately owned.
- No existing Storm services, extractors, scheduler, model or dashboard were changed.

## New additive instruments

### `empire_os/predictive_storm_measurement.py`

`review_storm_measurement(source,as_of)` / `review_storm_measurement_runtime(repo_root,as_of)`

Checks the original source schema, OBSERVE authority, age/future timestamps (24-hour freshness for these decision diagnostics), source health, candidate count against source rows, event/subject/assessment counter bounds, revenue and outreach denial flags, and individual candidate noncommercial authority. Stale source returns `STORM_SOURCE_STALE_HOLD` and **null current metrics**, retaining only source age/last date. Any altered booking/revenue/buyer authority returns HOLD.

When a valid fresh source exists, it reports safe **aggregate owner observations**: event count, source-validated event count, supported subject count, buyer/product matches considered, opportunity candidate count and blocked assessments. This is a measurement of pipeline processing and evidentiary completeness, **not the estimated number of storm-damaged buildings, sales, contractors, new customers or gross profit**.

The SHA256 revision is a fingerprint of the entire original JSON payload. A hash identifies source revision/differences; it does not itself prove origin authenticity, property identity, licensing, forecast issuance, causal effect or paid conversion. Individual tenant, property, buyer, event and source candidate payloads are not returned.

### `empire_os/predictive_measurement_instruments.py`

`build_predictive_measurement_instruments(territory,lineage,outcomes,economic_truth,producer,storm,as_of)`

Reuses existing read-only owner reviews to create a structured scorecard. It labels every metric by source owner, scope, available/missing status, source revision if verified by the source parser, separate observation window and why it cannot be treated as verified sales. **Storm metrics never borrow the seven-day Revenue GPS market cohort or 90-day reply lineage.**

The scorecard includes 27 metrics across territory research, reply lineage, Storm events, predictive outcome-source readiness, global Economic Memory/Revenue Pulse and missing original forecasting/economic ground truth. Missing or stale values are `null`, not false numerical zeros. A reported *zero* is used only for a known measured count from a fresh source. This is distinct from calibrated forecast accuracy and monetary truth.

The open-source instrument registry is an **implementation plan**, not automatically installed software:
- Reuse existing `telemetry.py` and `otel_telemetry.py` before adding an OpenTelemetry SDK/exporter.
- Attach optional OpenLineage as a source/processing job provenance instrument only with owner consent and safe dataset scopes.
- Later attach optional MLflow experiment/model version evidence and Evidently drift/forecast monitoring only after real tenant-bound original forecast/outcome pairs exist.
- Use existing Quant Brain Brier, calibration board and original-conversion registry before a new metrics stack.
- Any controlled experiment needs consented cohort and negative outcomes; the existing Customer Value preflight remains the original contract.

### Read-only operator

`scripts/review_predictive_measurement_instruments_20261020.py --read-only`

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_measurement_instruments_20261020 \
  --read-only
```

The operator reads only existing **allowlisted aggregate source snapshots**:
- Market GPS restricted territory research
- Restricted reply provenance
- Predictive product/buyer capacity-readiness
- Global Finance Revenue Pulse and Economic Memory
- Storm Opportunity runtime
- Two existing GPS producer source-code files, strictly for static read-only compatibility checks

It never reads raw storm events, private property records, customer names, buyer contact messages, payment records, confidential source bodies or external network APIs.

## Live checkpoint — 20 October 2026, approximately 08:58 UTC

| Item | Original read-only result | Interpretation |
|---|---:|---|
| Storm runtime saved at | 5 Oct 2026, 11:20 UTC | **Stale**, approximately 358 hours old |
| Historically observed Storm events in old snapshot | 3 | Old producer observation, **not** current weather |
| Historically valid Storm events in old snapshot | 3 | Source-level validity, not original weather provider attestation |
| Historically supported subjects | 0 | No verified exposed property/business in source |
| Historically considered matches | 0 | No buyer/product match in source |
| Historically emitted Storm opportunities | 0 | Not evidence of no current storm demand |
| Historically blocked assessments | 3 | Evidence required before promotion |
| Measurement scorecard fields | 27 | 14 available aggregate fields during this checkpoint |
| GPS research markets | 11 | Source research coverage, **not** authenticated demand |
| Original Quant source outcomes | 0 | Particular existing intelligence snapshot |
| Registered matched pilot GP forecasts | Not authenticated | No model calibration |
| Storm current event/opportunity metrics | **null** | Correctly held because Storm source is stale |

The Storm reader does **not** automatically refresh observations; the Storm source owner must restore the authorised collection/validation cycle first. A healthy saved historical run does not imply the service is currently running.

## Next source owner handoffs — real instruments, not a second Storm product

1. **Storm Weather/Source owner:** renew authorised original forecast/observed weather events with source provider identities, revision time, retrieval times and licensing, ideally signed provenance. Validate the feed's operating status and stale-data alert. Do not infer hail damage from a weather alert.
2. **Spatial/Physical owner:** attach canonical geographic geometry and permitted parcels/assets to source storm events, with exposure confidence and counterexample/negative observations. Link via original IDs to territory/ZIP/state and avoid ambiguous strings.
3. **Service/Contractor and materials owner:** independently verify service delivery radius, current capacity, labour cost, travel constraints and materials from original records for eligible roofing/HVAC/plumbing markets; candidate providers do not imply buying authority.
4. **Buyer/Commerce/Finance owner:** accepted prices/terms, lawful customer need, real paid transaction, fulfilment and refunds. Include true cost attribution and regional gross/operating profit before profit scenario calibration.
5. **Scientific Quant/Experimental owner:** register a genuine original pre-outcome storm-conditioned hypothesis, version and bounded horizon. Track precision/recall of exposure and estimated demand with correct denominators, plus conversion/GP forecast accuracy and control groups. No retraining from unlabeled alerts.
6. **Decision Control/Playbooks owner:** feed authenticated scenario changes into existing `predictive_market_economic_twin`, `predictive_profitability_playbooks`, cash/risk controls and original Strategic Scenarios. A hypothetical storm-driven price or call campaign is not activated without owner and founder authority.

**No production integration, provider licence, external scheduling, API billing, CRM/customer activation, actual weather refresh, model training, outbound messages, payments, database changes or price adjustment is granted by this feature.**

The original north-star remains:

**Predicted Gross Profit → Realized Gross Profit → Prediction Error → Better Allocation.**
