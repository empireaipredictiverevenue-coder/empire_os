# EMPIRE AI — FULL PREDICTIVE REVENUE ECONOMICS / SCENARIOS / PLAYBOOKS

**19 October 2026 | Existing Predictive Cloud / Predictive Revenue mission, not a rebuild**
**Owner:** `feature/predictive-decision-control-20261018`
**Status:** Additive, isolated, read-only, uncalibrated economics scenario and decision-playbook integration. No deployment or live business actions.

## Original mission — preserve the entire system

The exact commercial north star, already established in `docs/MASTER_BUSINESS_BLUEPRINT.md`, is:

> Predicted Gross Profit → Realized Gross Profit → Prediction Error → Better Allocation

**Predictive Revenue is the commercial engine within Predictive Cloud.** The 12-stage intelligence loop is: raw world -> sourced provenance -> temporal knowledge graph -> entity resolution -> signal fusion -> digital twins -> causal analysis -> pricing/revenue/risk predictions -> next best decisions -> governed GTM execution -> payment/fulfilment/outcomes -> Economic Memory and calibrated learning.

Do not reduce this architecture to lead scoring, a profit calculator, buyer research, social sentiment, a single model, or a new parallel worker.

### Full economic decision scope (16 connected disciplines)

1. **World / market signals**: search changes, buyer demand, market saturation, customer reviews/problems, competitors, materials and supply costs, economic indicators, job markets, permits, physical property history, weather, storms, climate geography and regulation. Original source freshness/licence/quality must be preserved.
2. **Provenance + temporal graph**: what was known when; company, buyer, customer, product, region, channel, pricing, supply and event relationships; resolvable original IDs, dedup, rights and historical lineage. Graph and vector retrieval are helpers, not independent truth or permission to call a company a buyer.
3. **Entity / role verification**: legitimate organisation, willingness/authority to purchase, allowed use, source-rights evidence, geographic fit, correct tenant binding; no treating a public webpage as a contract.
4. **Digital twins**: reversible scenarios over markets, companies, buyer seats, consumer needs, products, territories, campaigns, service delivery, renewal, supply chain and constraints. No simulated state mislabeled observed.
5. **Pain/problem → solution → commercial value**: job to be done, time saved, real money saved, reliability, user value, purchasing behaviour and alternative products/apps/services.
6. **Demand/conversion forecasting**: point-in-time signals, hypotheses, source-conditioned probabilities, uncertainty/intervals, buyer-specific intent, segment/corridor/channel/time; only calibrated after registered forecast and outcome pairs.
7. **Pricing and monetization**: accepted dollars/cents per lead/call/appointment/click, subscriptions/seats, app purchases, paid data/API, owned SEO/PPC traffic, performance partnerships, affiliate and other product sales; distinguish paid unit, conversion and return terms.
8. **Unit economics**: acquired customers and qualified attempts, CAC and traffic costs, selling price, payment fees, fulfilment, materials, infrastructure/AI compute, support, refund/chargeback, retention, cohort LTV, contribution margin, gross profit, operating overhead, break-even.
9. **Profitability and cash**: gross margin vs operating profit, overhead vs COGS, per-product and per-segment economics, delayed collections, maximum pre-payout cost exposure, cash runway/working capital, capital at risk, payout terms, cost per pipeline and realized profit.
10. **Strategic scenarios**: downside/base/upside, demand shortfall, price compression, competitor response, CAC inflation, material or labour inflation, refunds, retention/churn, call acceptance, seasonality, weather, regulation, supplier failure, channel changes and payment delays. Treat scenario weights as hypotheses unless calibrated.
11. **Risk and portfolio**: loss tails, worst case, source uncertainty, seller concentration, correlated channels/territories, capacity and exclusivity, explicit capital/spend limits and diversification; no unconstrained optimization.
12. **Value of information**: which extra data, experiment, buyer conversation, source, market report or enrichment is worth acquiring after accounting for cost and probability of changing a decision; no spending without separate approval.
13. **Action playbooks**: what to do if margin falls, demand spikes, buyer withdraws, refunds rise, capacity breaks, rival undercuts, market opens, regulation changes, storms shift demand, cash is trapped or a new product becomes popular. Actions must include trigger, evidence, policy, owner, prerequisites, stop condition and proposed outcome.
14. **Governed execution**: existing CRM, Business Development, marketing/SEO/AEO/GEO, partner channels, Lead Smart, content campaigns, Quant, Commerce and Finance owners perform approved actions; decision suggestion != authority to send/spend.
15. **Original outcome and actual profit truth**: immutable original prospect prediction before event, signed payment/settlement, delivery, acceptance, refund/cancellation, variable costs, overhead attribution and source-cohort reconciliation; revenue recognition is Accounting/Commerce owner's job.
16. **Feedback/calibration and customer products**: compare predicted/realized profit, Brier/log loss and calibration, cohort and forecast drift, learn from wins, losses and negative outcomes; package through existing dashboard, API, tenant-scoped agents, reports and scenario workbenches **only when original evidence exists**.

These are **the complete product disciplines**, not claims that every data feed or dashboard is already activated.

## THIS FEATURE — implemented and tested in isolated Predictive branch

**Source file:** `empire_os/predictive_profitability_playbooks.py`

### A. `review_profitability_playbook(pilot, plan, as_of)`

- Requires the **same original unregistered pilot** from `predictive_customer_value_pilot_preflight.py` and an exact design-revision hash; rejects tampered horizon/opportunity identity.
- Three explicit scenarios (`downside`, `base`, `upside`), weights sum to one, all `HYPOTHETICAL_UNCALIBRATED`. A weight is never represented as a calibrated conversion probability.
- Each scenario supplies the *same financial currency and purchased-unit class*: number of qualified attempts, conversion probability, price, refund fraction, expected paid cycles, their explicit day cadence (bounded by the original pilot horizon) and renewal retention, delivery COGS, payment fees, acquisition cost, fixed setup, overhead and collection lag. **All are user/source hypotheses and none is silently inferred.**
- Reuses **canonical** `quant_brain.expected_economics` and `quant_brain.risk_adjusted_score` to calculate expected sales, revenue, COGS, gross margin/GP, CAC, operating profit, break-even qualified attempts, renewal-adjusted customer value and downside penalty. Acquisition cost is separated from gross profit and deducted from operating profit; fixed setup/overhead are also deducted **once**. A booking is not automatically revenue.
- Computes both expected pre-payout cost exposure and conservative *all attempts converting before collections* stress exposure. The upper bound is hypothetical and pessimistic, not actual bank drawdown.
- Produces risk-weighted expected vs downside operating profit, with finite bounds and original currencies unchanged. Nothing is booked as actual GP, profit or finance advice.
- Outputs governed, deterministic playbooks for first buyer proof, original forecast registration, margin repair, downsides/stop-loss, cash cap, delayed payout, customer-value evaluation and competitor/price research.

### B. `build_profitability_scenario_portfolio(books, budget_minor, risk_aversion, capacity_by_group)`

- Reuses **existing** `predictive_cloud_scenario_optimization.build_predictive_cloud_scenario_problem` and its common Optimization IR. Does not introduce a second capital allocator.
- Requires compatible currency, horizon, scenario states/weights, unique opportunities and explicit cash and delivery-capacity constraints.
- The objective uses **already cost-netted operating profit**, and cash exposure is used only as a *budget constraint* so costs are not double-subtracted.
- Returns recommendation/optimization representation with `execution_authority=none`; not a selected live campaign or authorised capital allocation.
- No proof yet of correlation, coherent common-world macro scenarios, solver-validated live feasibility or real probability calibration.

### C. `review_profitability_sensitivities(...)`

- Recomputes an entire profit book after each explicit one-factor change: selling price, conversion, refunds, acquisition costs, fulfilment, payment fees, paid retention, overhead and collection lag.
- Never adds independent sensitivity deltas together or claims a parameter perturbation has been causally demonstrated.
- A mixed compound intervention requires a separately justified joint scenario, then re-evaluation.

### D. `review_profitability_research_value(...)`

- Reuses `quant_brain.value_of_information`: apparent decision improvement × hypothetical chance of changing the decision − research cost.
- Ranks which missing market facts/experiments could be worth learning, **without** activating spend or treating uncalibrated information-value numbers as actual ROI.

### E. Read-only founder/operator view

`scripts/review_predictive_profitability_playbooks_20261019.py --read-only`

Reads **only** existing:
- `runtime/predictive_intelligence/latest.json`
- `runtime/buyer_capacity_readiness/latest.json`
- `runtime/community_intent/latest.json`
- `runtime/opportunity_radar/latest.json`

via already approved source contracts. Reports 16 architecture disciplines, 10 owner playbook prerequisites, original source-aligned pain opportunity counts, and missing authenticated economics inputs. It does **not** invent a synthetic financial scenario when purchase prices, probabilities or cost attribution are missing. Raw customer records/private marketplace transaction details are not read.

## Latest read-only production outcome inventory

- 26 catalogued product entries; these are **not orders**
- 0 source outcome labels in Predictive Intelligence snapshot
- 0 probability-ready product models
- 0 verified buyer terms and 0 verified buyer capacity in the canonical capacity snapshot
- two linked Community/Radar customer problem hypotheses at observed checkpoint; these are **not prospective profit forecasts**
- original verified customer benefit/payment evidence and prospective registered original prediction remain unavailable to these feature read-only operators.

**Therefore no live profitable-campaign ranking or observed ROI can be truthfully issued yet.** Scenario examples in tests are synthetic and explicitly labelled hypothetical, never live market forecasts.

## Step-by-step integration into existing system (not separate projects)

1. **First commercial deal and source custody** — existing Business Development/Gmail/CRM/Commerce owners retrieve lawful original buyer/customer terms, accepted paid unit, territory, quota, returns, valid contact and payment/fulfilment events. The already-running commercial verifier remains authoritative.
2. **Original prediction issuance** — existing Scientific Quant/Original Registry registers forecast and financial hypotheses BEFORE payment/booking/outcome.
3. **Economic fact model** — Finance/Commerce/Service Delivery source owners agree cost taxonomy and receipts: acquisition (SEO/PPC/outbound), delivery COGS, variable cloud inference, labour/material, fees, refunds, FX and tax/overhead attribution. Implement tenant+market+product+period+currency, not guessed company-wide blended cost.
4. **Scenario policy and playbooks** — map controlled, versioned original evidence into accepted/uncertain assumptions, baseline/downside/upside; calibrate probabilities from original wins/losses before any real automatic decision. Scenario compiler and playbook proposals remain separate from dispatch authority.
5. **Digital twins and temporal knowledge graph** — connect existing authorised City/Territory/Buyer/Product/Market Twins, Graph/Source Intelligence, weather/material/permit and trend sources. Different agent owns Graph/CORTEX/Market data; reuse its trust graph and source revision, no duplicate private identities.
6. **Portfolio and controlled execution** — source-bounded candidate set, hard cash/capacity/service constraints, owner-approved strategy/campaign playbook, controlled sandbox rollout and founder-owned real spend gates. No unapproved marketing or calls.
7. **Realized Economic Memory and model learning** — evidence of settlement, delivery, recognized revenue and finance-attributed costs joins original prospective prediction; update calibration only when original outcomes and controls are verified, including refunds and losses.
8. **Founder/tenant products** — explainable GP probability distributions, what-if simulator, downside and margin dashboards, source timeline, playbook recommendations, alerts, product/app and market opportunity comparisons; integration owned by existing dashboard/tenant/API agents.

## Exact run command

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_profitability_playbooks_20261019 --read-only

PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_predictive_profitability_playbooks.py \
  tests/test_predictive_profitability_readiness.py
```

**No production edits, financial transactions, buyer creation, live forecasts, deployed model, original registry write, autonomous spend, outreach, policy bypass, new timer or duplicate data stores in this change.**

**Next evidence gate:** Economic scenario simulations are implemented with explicit hypothetical assumptions, but **source-authenticated unit economics, accepted customer prices, calibrated probability distributions, actual cash realization, and verified cohort gross profit** must be supplied by the existing owners before any predictive financial claim, capital allocation, live playbook automation or model promotion.
