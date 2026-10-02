# Strategic Growth Intelligence v2 — Architecture Contract

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Strategy / Marketing Growth / Astra Executive

## Goal
Upgrade and unify EmpireOS business-strategy systems so AI proactively discovers,
models, ranks and assigns growth strategies without waiting for Founder prompts.

This programme enhances existing systems; it does not replace them.

## Existing owners to preserve
- `strategy_operating_system.py` — strategy review/scoring primitives
- `gtm_offer_strategy.py` — niche/offer/demo strategy
- `market_domination.py` — market-capture/moat strategy
- `icp_buyer_trigger_intelligence.py` — ICP/account/trigger intelligence
- `commercial_marketing_registry.py` — campaign/product/ICP registry
- `locale_intelligence.py` — geography/locale/timezone evidence
- `outreach_intelligence.py` — governed account-entry/channel strategy
- `north_mini_agent.py` — legacy autonomous growth brain; to be modernized/replaced
- `experiment_analysis.py` / Economic Memory / Revenue OS learning — outcome learning
- Predictive Cloud / Future Trend / Competitive / Search / Media Intelligence — evidence sources

## End-state loop

```text
REAL SIGNALS + PREDICTIVE CLOUD + ECONOMIC MEMORY
  -> STRATEGY DISCOVERY
       markets / niches / products / offers / pricing hypotheses
       channels / zero-paid acquisition / partnerships
       SEO / AEO / GEO / content / media plays
       territories / locales / service corridors
       ICPs / account archetypes / buying committees / personas
       retention / expansion / cross-sell / white-label / affiliate plays
  -> EVIDENCE NORMALIZATION
  -> STRATEGY CANDIDATES
  -> MULTI-DIMENSION SCORE + CONFIDENCE
  -> PORTFOLIO / DIVERSIFICATION / DEPENDENCY CHECK
  -> EXPERIMENT DESIGN + KILL CRITERIA
  -> DEPARTMENT ASSIGNMENT
  -> EXISTING EXECUTION PLANE / QUEUES
  -> OBSERVED OUTCOME
  -> EXPERIMENT ANALYSIS + ECONOMIC MEMORY
  -> CALIBRATION
  -> NEXT STRATEGY GENERATION
```

## Proactive strategy domains
Every cycle may propose evidence-backed candidates across:
1. market/niche entry;
2. product and packaging;
3. pricing hypothesis (non-binding until commercial evidence); 
4. offer/demo/CTA;
5. buyer acquisition;
6. zero-paid acquisition;
7. partnerships/affiliates/channels;
8. SEO/AEO/GEO/search visibility;
9. media/content distribution;
10. geography/territory/locale;
11. ICP/account targeting;
12. persona/buying-committee targeting;
13. retention/expansion/cross-sell;
14. marketplace/auction liquidity;
15. supply acquisition;
16. operational leverage / automation;
17. data/product intelligence opportunities;
18. strategic moat / defensibility.

## Targeting rule
Strategy may identify **business accounts, ICPs, job roles, buying committees,
territories and public professional personas**. Person-level contact execution stays
inside governed outreach/contact-evidence systems. No strategy module may infer
sensitive personal traits, perform invasive profiling or independently send/contact.

## Zero-paid strategy
"Zero-paid" means strategies that do not require paid media/spend, including:
- owned content / SEO / AEO / GEO;
- community/public-intent capture;
- organic social/media;
- partnerships and affiliates;
- direct account research;
- referrals / warm intros;
- product-led/self-serve distribution;
- directory/ecosystem/listing presence;
- public-data-driven trigger outreach (execution governed separately);
- free/open-source distribution assets;
- buyer/supplier network effects.

It does not mean hidden cost is assumed to be zero. External-cost evidence remains
explicit and department budget rules apply.

## Strategy candidate contract
Each candidate MUST include:
- `strategy_id`
- `strategy_type`
- `thesis`
- `target_market`
- optional `territory`
- `target_icp`
- `target_roles`
- `channel`
- `offer_key`
- `evidence_refs`
- `evidence_confidence`
- `expected_upside_cents` when evidenced, otherwise null
- `estimated_external_cost_cents` when evidenced, otherwise null
- `time_to_signal_days`
- `reversibility`
- `strategic_fit`
- `data_advantage`
- `distribution_advantage`
- `competitive_gap`
- `learning_value`
- `dependencies`
- `risks`
- `experiment`
- `kill_criteria`
- `owner_department`
- `authority_required`

Missing evidence must remain null/unknown, never imputed as commercial truth.

## Strategy scoring
Score uses only available evidence. Proposed v2 dimensions:
- expected economic upside;
- evidence confidence;
- product/market fit;
- buyer accessibility;
- distribution advantage;
- data advantage;
- competitive gap;
- speed-to-signal;
- reversibility;
- learning value;
- moat contribution;
- operational complexity inverse;
- external-cost efficiency.

The score ranks experiments; it is not a revenue forecast or Founder approval.

## Portfolio intelligence
The engine must avoid recommending ten versions of the same idea. It must:
- deduplicate similar candidates;
- expose dependencies/conflicts;
- diversify across horizon/channel/market;
- identify prerequisite strategies;
- distinguish core optimization from exploration;
- limit simultaneous experiments to configured department capacity/budget;
- preserve kill criteria.

## Experiment contract
Every executable strategy becomes an evidence-backed experiment:
- hypothesis;
- baseline;
- intervention;
- target metric;
- measurement window;
- minimum evidence threshold;
- stop/kill criteria;
- owner;
- authority boundary;
- expected learning even if economics are unknown.

Experiment results flow to existing Experiment Analysis, Economic Memory and Revenue
OS learning systems before the strategy is repeated or scaled.

## North-mini modernization
Legacy `north_mini_agent.py` is not the canonical v2 runtime because it currently
contains old `/root` paths, SQLite state, simulated-charge assumptions and a direct
free-OpenRouter dependency.

v2 will:
- read current EmpireDB/runtime read models;
- use the model-health/router fabric rather than a fixed provider;
- operate inside current repo/runtime paths;
- produce typed strategy candidates, not free-form growth-plan JSON;
- delegate experiments through department queues/Execution Plane;
- retain no direct publish/send/spend authority;
- use outcome calibration/Economic Memory;
- retire stale context/artifacts under current agent lifecycle rules.

## Runtime cadence
A bounded strategy cycle should run after fresh intelligence/evaluation data and no
more frequently than useful evidence changes. Initial cadence: every 30 minutes,
plus event-driven triggers from major new signals/replies/outcomes.

The cycle is OBSERVE/planning by default. It can create department work items for
safe internal research/analysis. Live outbound, spend, terms, funds, deployment and
authority expansion remain governed gates.

## Founder surface
Expose:
- top current strategic opportunities;
- zero-paid growth plays;
- market/territory opportunities;
- ICP/persona opportunities;
- marketing/channel plays;
- experiments running / blocked / learned;
- why each recommendation exists;
- evidence confidence;
- expected upside only when evidenced;
- next Founder gates required.

## Completion slices
1. typed Strategic Growth candidate/portfolio engine;
2. strategy source adapters over existing intelligence systems;
3. proactive experiment/department assignment;
4. Strategy OS scoring enhancement;
5. GTM/offer strategy v2;
6. market-domination v2;
7. ICP/persona/trigger v2;
8. GEO/territory/locale v2;
9. marketing/channel/zero-paid v2;
10. outreach account-entry strategy v2;
11. North-mini modernization/removal of legacy state paths;
12. outcome-learning/calibration loop;
13. systemd runtime + self-heal;
14. Founder strategy surface;
15. live verify with real evidence and no synthetic commercial truth.
