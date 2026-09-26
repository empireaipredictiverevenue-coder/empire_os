# Empire AI — Quantitative Intelligence Architecture

Date: 2026-09-20
Status: CANONICAL QUANT / DECISION-SCIENCE LAYER

The Quantitative Intelligence layer is the mathematical verifier beneath **Predictive Cloud**: Astra, Predictive Revenue, Digital Twin, Experiment/Causal, Risk and Capital/Portfolio Intelligence.

It exists so high-value decisions are not based on LLM confidence or persuasive
language. LLMs generate hypotheses and plans; the Quant layer measures
probability, uncertainty, economics, risk and information value.

## 1. Core Objective

Convert evidence into calibrated numerical decision support:

**observations -> distributions -> expected value -> uncertainty -> downside ->
causal evidence -> scenario distribution -> portfolio constraints ->
value of information -> ranked decision packet -> verified outcome -> update.**

## 2. Quant Brain Layers

### 2.1 Descriptive Statistics
- robust counts/rates
- medians/quantiles
- cohort distributions
- rolling windows
- seasonality
- anomalies
- change points
- missingness/unknown profiles

### 2.2 Bayesian Updating
Use prior + real observed evidence to maintain beliefs for:
- conversion probability
- buyer acceptance
- renewal
- churn
- source reliability
- offer win rate
- corridor performance
- campaign response
- fulfilment success

Posterior beliefs must record prior, evidence count and update time.

### 2.3 Calibration
Track predicted probability vs observed frequency.
Metrics:
- Brier score
- log loss where appropriate
- calibration error/buckets
- forecast error
- interval coverage
- prediction drift

### 2.4 Expected Economics
For every candidate action:
- probability of success
- expected revenue
- expected cost
- expected gross profit
- expected loss/downside
- time-to-revenue
- capital at risk
- opportunity cost

Expected gross profit is not actual gross profit.

### 2.5 Risk / Tail Analysis
- downside probability
- loss-at-risk
- worst-case bounded scenario
- drawdown / cash exposure
- concentration risk
- correlated corridor/source risk
- capacity failure risk
- data/source uncertainty

### 2.6 Monte Carlo / Scenario Distribution
Digital Twin scenarios should become probability distributions, not only point
estimates.

Use cases:
- corridor demand/capacity
- seat economics
- campaign economics
- fulfilment cost
- renewal/churn
- capital allocation
- revenue forecasts

Every simulation stays:
simulation_only=true
actual_revenue=false

### 2.7 Causal / Experiment Layer
- randomized holdouts where possible
- uplift/incrementality
- pre/post with controls where justified
- heterogeneous treatment effects later
- causal confidence
- attribution uncertainty

Do not claim causal lift from correlation alone.

### 2.8 Optimization / Operations Research
Optimize bounded resource allocation:
- buyer capacity
- inventory routing
- territory coverage
- campaign budget recommendations
- agent/model compute
- sales/closer time
- crawler/source spend
- capital deployment

Constraints are explicit:
- capacity
- cash
- risk
- geography
- exclusivity
- service level
- legal/compliance
- approval
- minimum margin

### 2.9 Portfolio Intelligence
Treat markets/corridors/products as a portfolio.

Measure:
- expected return
- uncertainty
- covariance/correlation
- concentration
- diversification
- capacity
- downside
- time horizon
- liquidity/ability to pause

### 2.10 Value of Information
Before expensive acquisition/research, ask:
"What is the expected value of learning this fact?"

Use VOI to prioritize:
- crawler depth
- decision-maker enrichment
- satellite imagery
- paid data
- additional experiment samples
- human review
- premium model calls

### 2.11 Sequential Decisioning
Later:
- Bayesian bandits
- contextual bandits
- sequential tests
- adaptive allocation

Only after experiment integrity and real outcome volume justify them.
No uncontrolled reinforcement learning against production revenue.

### 2.12 Forecast Ensemble
Combine deterministic/statistical/model forecasts only when:
- each component has provenance
- historical calibration exists
- ensemble weights are versioned
- unavailable components remain unavailable

### 2.13 Decision Theory
Astra's choice function should consider:
- expected utility
- uncertainty
- downside
- reversibility
- information gain
- time-to-value
- confidence
- authority
- strategic option value

## 3. Quant + AGI Relationship

AGI layers:
- generate hypotheses
- understand qualitative context
- plan
- retrieve evidence
- coordinate specialists

Quant layer:
- tests claims numerically
- estimates uncertainty
- calculates economics
- ranks options
- detects weak evidence
- calibrates prediction quality
- prevents eloquent guesses from becoming decisions

Verifier checks both.

## 4. Quant + Data Plane

Quant calculations must consume:
- point-in-time-correct features
- provenance
- data contracts
- event time
- outcome time
- lineage

Training/evaluation cannot use future information.

## 5. Quant + Predictive Cloud / Predictive Revenue

Canonical commercial score is not one opaque number.

A candidate can expose:
- p_conversion
- p_payment
- p_fulfilment
- conditional deal value
- expected revenue
- expected cost
- expected gross profit
- downside loss
- time-to-revenue
- uncertainty
- data-quality confidence
- causal evidence strength
- calibration state

## 6. Quant + Buyer / Seat / Corridor

For each corridor:
- demand distribution
- buyer-capacity distribution
- conversion distribution
- lead/call/appointment value distribution
- margin distribution
- renewal/churn posterior
- overflow probability
- seat utilization
- expansion value
- concentration risk

For each seat:
- expected utilization
- expected delivered units
- expected MRR
- overage expectation
- expected gross profit
- renewal probability
- capacity failure probability

## 7. Quant + GTM / Outreach

Use quantitative models for:
- account priority
- trigger strength
- expected response
- expected meeting
- expected close
- expected gross profit
- touch fatigue
- sequence lift
- channel incrementality
- source-to-revenue attribution

No invented response-rate assumptions may be presented as observed data.

## 8. Quant + Search / Content

Rank content/search opportunities by:
- demand evidence
- commercial intent
- expected conversion
- expected revenue
- production cost
- time-to-index/time-to-value
- confidence
- competition
- citation probability
- expected gross profit

Rankings alone are not success.

## 9. Quant Control Rules

- Unknown input -> unknown output where calculation requires it.
- Predictions always labelled predictions.
- Simulation always labelled simulation.
- All probability values bounded [0,1].
- Every prior is explicit.
- Every model/calculation version is recorded.
- All outcome updates require verified real outcomes.
- Synthetic data may test algorithms but cannot update production commercial
  beliefs as if real.
- Model/weight changes go through evaluation + shadow + approval.
- Quant recommendations have no execution authority.

## 10. Immediate Engineering Slices

1. Quant Decision Packet
2. Bayesian conversion updater
3. Expected value / gross-profit distribution
4. Risk-adjusted ranking
5. Monte Carlo scenario preview
6. Value-of-information preview
7. Calibration metrics
8. Portfolio/corridor concentration
9. Causal evidence bridge to Experiment Engine
10. Quant Control Tower for Astra

## 11. Long-Term Quant Brain

When real data volume supports it:
- hierarchical Bayesian market/corridor models
- survival/time-to-event models
- causal forests / uplift modelling
- probabilistic graphical models
- constraint optimization / integer programming
- contextual bandits
- robust optimization
- ensemble forecasting
- uncertainty-aware multimodal models
- agent/model compute portfolio optimization

The Quant Brain is successful when Empire can say:

"We chose this action because its expected gross profit, downside, uncertainty,
evidence quality and information value dominated the alternatives — and here is
how that prediction compared with the real outcome."


## Quant Decision Packet

Quant Brain now exposes one typed decision-support packet combining:

- expected economics;
- Monte Carlo downside distribution;
- risk-adjusted value;
- optional Value of Information;
- optional Brier/log-loss/reliability calibration from verified outcomes.

The packet is **UNAVAILABLE** when required evidence is missing.

It must not manufacture:
- probability of success;
- uncertainty;
- confidence;
- time-to-revenue;
- price/cost bounds.

Verified Commercial Product Catalog policy economics may supply price/cost
scenario inputs. Probability and uncertainty remain UNKNOWN until supported by
Predictive Intelligence / verified outcome cohorts.

Canonical implementation:
- `empire_os/quant_brain.py::quant_decision_packet`
- `empire_os/opportunity_quant_review.py`
- `POST /v1/quant-brain/decision-packet/preview`

Quant output remains recommendation/decision support only and has no capital,
commercial, payment or revenue-recognition authority.
