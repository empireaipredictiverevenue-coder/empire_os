# Empire AI Predictive Revenue — Governed Economic Decisions

**20 October 2026 | Existing Predictive Decision Control feature branch | additive read-only**
**Continuing** `e53734ed` profitability, scenarios, break-even, risk, playbooks and portfolio optimization.

## Next operational capability

This feature closes a crucial classification gap between **company-wide accounting truth** and **individual product/campaign opportunity scenarios**. It does not rewrite Decision Control, Economic Memory, Revenue Pulse, CRM, Quant or the account digital twin owned by separate agents.

An unregistered, hypothetical scenario can generate useful research directions, but may NOT be promoted to a verified prediction, live profitability ranking or spend instruction merely because company-wide recognised revenue/gross profit exists.

## Implemented interfaces

### Economic thresholds in existing scenario book

`empire_os/predictive_profitability_playbooks.py` now includes:

- `required_conversion_rate_to_break_even_hypothetical` — the conversion fraction required to cover acquisition, per-conversion variable COGS, fixed pilot cost and overhead for the original assumed cohort, if unit contribution is positive. May be greater than 1, correctly showing assumed break-even as infeasible.
- `required_unit_price_minor_to_break_even_hypothetical` — minimum price, given original retention/refund/payment costs, qualified attempts and conversion assumptions. Returns `null` if the underlying denominator is zero/unsupported.
- `expected_contribution_per_attempt_minor_hypothetical` — after acquisition, distinct from gross profit.
- `original_pilot_design_sha256` — exact original prospective experiment revision for future custody handoff. It is an evidence binding *identifier*, not a signature or registry attestation.

These are deterministic what-if requirements, **not** recommended prices or calibrated conversion probabilities. The earlier model still protects one currency, one purchased unit, original fixed horizon, paid-cycle timing, refund/CAC costs, cash-cap stress and no automatic external actions.

### Global actual financial reporting separation

`empire_os/predictive_profitability_governed_decision.py` contains:

- `review_existing_global_economics_truth(pulse,memory,as_of)`
- `review_existing_global_economics_truth_runtime(repo_root,as_of)`
- `build_profitability_governed_decision(book,truth)`

The first two use **existing authoritative aggregate projection contracts only**:

1. `runtime/revenue_pulse/latest.json` — canonical recognised revenue/gross-profit scalar **for the global reporting scope**, with forecast excluded from actual truth.
2. `runtime/economic_memory/latest.json` — existing outcome-conditioned memory, calibration-evidence and decision-outcome attribution counts, not fabricated supervised labels.

They enforce original schema, authority `none`, no actual-money mutation, forecast exclusion, timestamp freshness, total-versus-rows consistency in Economic Memory, and conservative cross-source skew. They return no raw private customer names, emails, tenant IDs, episode lists, accounting documents or contact details. Any broken source yields a **HOLD with unknown numbers**, not a convenient zero.

**Important:** The Pulse's reported *global* realised GP is not an opportunity-level outcome. There is no original cohort/tenant/product/forecast/cost link in these two aggregate snapshots. Thus `single_opportunity_realized_gp_minor=null`, `original_forecast_prediction_error_minor=null`, and the confirmed payout or source-authenticated purchase flag remains false.

The governed decision packet pairs an explicitly **HYPOTHETICAL** source-bound profit book with the reviewed global economic snapshots. Its playbook triggers are mapped to existing action owners, all in research/proposal state, no dispatch or authority. It surfaces original what-if break-even conversion and price, downside loss and cash-cap problem, and a release hold requiring real source-authenticated payment + original prospectively registered forecast.

### Live operator

`scripts/review_predictive_profitability_decision_handoff_20261020.py --read-only` reviews the already published global Pulse and Economic Memory aggregates plus the existing customer-value Radar and Predictive outcome-readiness snapshots. It intentionally does **not** create imaginary priced product scenarios from missing buyer terms.

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_profitability_decision_handoff_20261020 --read-only
```

At the examined checkpoint: original Revenue Pulse **reported** 0 recognised revenue minor units, 0 realised GP minor units, Economic Memory 0 outcome-conditioned and 0 calibration records; original Predictive Intelligence 0 source outcomes and 0 probability-ready product models; 2 Community/Radar problem hypotheses. These are time- and source-specific observations, not a whole-enterprise financial audit.

## Decision system workflow and who owns what

1. **Business Development/Commerce:** first-party buyer accepted unit, price, territory, capacity; real purchase and refund/settlement receipts. Don't declare 1,057 inventory rows activated.
2. **Scientific Quant / prospective forecast registry:** freeze the exact hypothesis, forecast/scenario horizon, price/CAC assumptions and original forecast **before outcomes**, with independently verifiable readback. Feature code cannot register it.
3. **Finance/Economic Memory:** settle and attribute net money, fulfilment, variable delivery, refund, AI inference, support and overhead to the correct original product/tenant/period; calculate actual gross and operating profit with accounting policy. Global snapshot doesn't give these joins.
4. **Existing Predictive Decision Control and Strategy:** consume only individually source-validated scenario evidence and bounded owner playbooks, independently assess risk, permissions and action routing. This feature adds **no worker, timer or dispatch approval**.
5. **Digital twins / Market Knowledge Graph:** controlled what-if variables for city, weather, building history, competitor response, labour/material costs, storm intensity, supply, customer needs, seasonality and regulation. The twin state must use the original signed source revision; no new agent owns these datasets here.
6. **Outcome Calibration:** only once original prospective forecast and authentic paid outcome share the same original IDs/cohort and temporal custody. Negative outcomes and missing observations stay visible. Never train on marketing claims, a search trend, an illustrative price or overall company revenue.

## Known incomplete work and firm boundaries

- No **live** customer purchase/booking or cost authentication integrated into this worktree; no identity-linked forecast readback; no scenario probability calibration; no authorised campaign price or working-capital allocation.
- No company-wide Pulse amount may be used as a **per-opportunity** realized GP or model error.
- The governance packet is not a live founder task queue, source-backed budget or payout. Existing production decision-control owns delivery; that interface needs owner-reviewed merge integration.
- Today's source summaries are **OBSERVE**, not a claims of payment settlement, successful customer outcomes or deployment.

**Testing and release:** tests include source tampering/forecast-leakage, false accounting grants, stale/equivocal epochs, cross-scope attribution, break-even formulas and no dispatch. Feature branch only, clean commit requested, production and all other agents' files untouched.
