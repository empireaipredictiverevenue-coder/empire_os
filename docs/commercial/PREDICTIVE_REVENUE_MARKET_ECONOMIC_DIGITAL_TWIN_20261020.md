# EMPIRE AI — PREDICTIVE REVENUE MARKET ECONOMIC DIGITAL TWIN

**20 October 2026 · Existing Predictive feature branch · isolated, read-only**

## Mission preserved

Predictive Revenue is a combined world/market/customer intelligence, scenario, digital twin, economic decision, playbook and outcome-calibration system. The economic north star remains **Predicted Gross Profit → Realized Gross Profit → Prediction Error → Better Allocation**. This increment builds on `e53734ed` and `54116597`. No separate economic truth database, scraper, timer, worker, purchasing agent, graph or autonomous finance authority has been created.

## Added

### 1. Market conditions → realistic profitability scenarios

`empire_os/predictive_market_economic_twin.py`

`review_market_economic_twin(pilot,economic_plan,market,drivers,as_of=...)` combines the original:

- `digital_twin.MarketBaseline`, `MarketScenario` and `simulate_market_scenario` for **demand, capacity and selling-price** scenario changes;
- `predictive_profitability_playbooks.review_profitability_playbook` for **fully recalculated revenue, refunds, CAC, delivery COGS, gross profit, operating profit, downside risk, cash exposure, break-even and playbook triggers**.

The market baseline and every driver are exact typed, explicitly `HYPOTHETICAL_UNCALIBRATED` inputs. The original signed-forecast status remains false. An original MarketBaseline historically calls its input “observed”; this adapter never claims the values are actually observed: it only constructs the dataclass inside a separately controlled hypothetical adapter.

**Scope:** source-bound market key, geography (e.g. town/county/state or metro code) and business niche, source timestamp and hypothetical research reference. Cross-domain personally identifying information and unverified contact data are not accepted. The baseline's `served = min(demand, capacity)` must equal **the original economic cohort of qualified attempts**, otherwise the adapter rejects the join. Units and prices must match the existing economic plan. A capacity loss caps serviceable demand before any modeled conversion or accepted revenue calculation.

**Driver types:** `weather_storm`, `material_cost`, `competitor_response`, `search_ai_change`, `labor_capacity`, `seasonal_demand`, `regulatory_change`, `consumer_preference`, `channel_distribution`, `supply_chain`.

**Shocks** may change the market demand/capacity/price multipliers, conversion multiplier, acquisition and fulfilment cost multipliers and refund-rate delta. Unbounded/negative/invalid assumptions, conversion above probability 1 and refund outside [0,1] are rejected. Monetary and volume constraints are bounded. An explicit driver shock recomputes the **whole** downside/base/upside economic book rather than adding unrelated single-factor deltas. The result never attributes a weather phenomenon to actual damage, a competitor price to an accepted purchase, projected served volume to paid orders, or a scenario GP to accounted earnings.

**Playbook implications:** weather-driven demand increases can still be uneconomic if capacity is insufficient; labour/material inflation can turn a high-conversion corridor loss-making; competitor discounting raises the break-even conversion requirement; longer payout terms raise cash exposure. All outputs are hypotheses requiring independent owner evidence.

### 2. Real source availability / freshness

`empire_os/predictive_market_economic_source_readiness.py`

Only reads three existing aggregate snapshots, with source-specific schema, freshness and authority verification:

- `runtime/market_sweeps/revenue_gps_latest.json`
- `runtime/competitive_intelligence/competitor_intelligence_feed_latest.json`
- `runtime/storm_opportunity/latest.json`

**Latest observed checkpoint (20 October 2026):**

| Original source | Observed | Interpretation |
| --- | --- | --- |
| Revenue GPS | 20 Oct 07:20 UTC, fresh | 11 markets in source, competitive evidence in 2 markets. **Commercial demand markets 0**. No inferred buyer intent or revenue. |
| Competitor Intelligence feed | 22 Sep | **Stale**; historical 14 company references are not current competitor prices, paid demand or permission to contact. |
| Storm Opportunity | 5 Oct | **Stale**; zero candidates in observed snapshot. Not verified local property damage or paid storm demand. |

A field named `verified_product_economics` in the Revenue GPS source is **not observed customer revenue or cost**: its original embedded contract identifies `economics_kind=founder_policy_scenario`, `actual_cost_observed=false`, `actual_revenue=false` and `prediction=false`. The readiness adapter checks these before classifying that source as safe research. It does NOT copy its example price into new market simulations.

Because the source timestamps and geographic cohorts are not jointly verified, the output **always** has `original_source_revision_bound_to_pilot=false`, `simulated_economic_twin_calibrated=false`, `product_market_price_authenticated=false` and no authority to apply a shock or train the forecasting model.

**Run:**

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_market_economic_twin_20261020 --read-only

PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -B \
  -m pytest -q tests/test_predictive_market_economic_twin.py \
  tests/test_predictive_market_economic_source_readiness.py \
  tests/test_predictive_profitability_playbooks.py
```

### 3. Regression protections

The new tests cover capacity-limited demand surges, labour shortages, competitor price cuts, material-cost inflation, zero-demand losses, market and cohort identity, non-positive prices, overflow/nonfinite and uncalibrated shocks, impossible conversions, duplicate drivers, fresh versus stale source owners, false “verified” purchase data, and avoidance of raw personal information and owner file changes.

## Next implementation dependencies — existing owners

1. **Spatial/Physical Intelligence and Weather:** bind actual storm/temperature observations to correct source timestamp, geometry, property/service applicability and legal source rights, instead of inferred damage from weather patterns.
2. **Competitor/Market Intelligence / DataForSEO:** refresh source price/competition evidence, geography and source epochs; track public comparisons as market signals, not verified accepted buyer prices.
3. **Buyer/CRM/Commerce:** accepted unit/price/territory/capacity/rights, authenticated bookings/purchases and refunds. Prefer direct customer-purchase proofs to publisher and marketplace claims.
4. **Materials & Service Delivery:** qualified capacity actually deliverable per time window, transport, labour, equipment, permits, materials and real per-unit variable costs; existing supply/territory graph owns those records.
5. **Quant / Original Prediction Registry:** original cohort-bound forecast and risk constraints registered and read back before outcomes.
6. **Finance / Economic Memory:** join original forecast with verified payment, fulfilment, refund and cost attribution. Model errors and payouts can then calibrate opportunity-level economics rather than globally scoped Pulse aggregates.
7. **Decision Control / Portfolio / Playbooks:** owner-reviewed handoff of scenario recommendations to the existing execution bus. Never activate spending, price changes or customer contact without its existing approvals.

## Release boundaries

This is **feature code + tests + a read-only source inventory**, not a deployed commercial product or automated weather/pricing feed. No new production services, timers, original data modification, CRM/finance writes, model training, authentic revenue claim, investor promise, external outreach, marketing spend or purchasing authority.

The economic twin is a **reversible research/simulation layer** until authenticated geographic and commercial evidence is connected and original Quant probabilities calibrated.
