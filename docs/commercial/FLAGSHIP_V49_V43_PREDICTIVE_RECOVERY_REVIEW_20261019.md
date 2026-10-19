# Empire AI — v49 and V43 Predictive Recovery: safe owner integration

19 October 2026. Isolated existing Predictive Intelligence owner worktree. This review uses **both** founder-provided files: the 2026-10-19 legacy Predictive handoff and the v49 shadow ZIP; no actual legacy USB database is imported.

## Source custody and original offline verification

Uploaded ZIP SHA-256: `1a8a17c52944d6416eae8dd44baf0beb0b409a2c672731d56a16797f8bc0f001`.

Uploaded companion handoff SHA-256: `dd2756a2f17be14b290bdc211a348490b595f7bdd42012276fe76c46a07ea8b8`.

Original self-contained ZIP source files were inspected safely without running legacy payout, email, SMS, voice, pipeline or network code. The exact extracted original shadow's `run_offline_shadow.py` yielded smoke PASS, and `test_legacy_v49_match_shadow.py` passed 15 tests locally. The reference report on four **synthetic** contractors: legacy ranked four, strict evidence fixture passed one, old average rank 0.725, strict-example average rank 0.887, one geo mismatch, one specialty mismatch and one capacity verification hold. These are **not** production customer observations.

## Implemented in the existing Predictive owner branch

- `empire_os/flagship_legacy_v49_shadow.py`: pure counterfactual with the original five weights (metro 0.40, specialty Jaccard 0.25, trust 0.15, recency/rotation 0.10, capacity 0.10). Contrasts legacy permissive geo-OR-specialty eligibility with independent research-only geography, specialty, license, capacity, same-tenant, suppression, rights, trust and dispatch-evidence gates.
- `tests/test_flagship_legacy_v49_shadow.py`: reproduces the uploaded example's exact aggregate scores, holds, numerical counterexamples and cross-tenant/suppression safety; no customers, addresses or contact exports.
- `empire_os/flagship_v43_novelty_shadow.py`: **proposal-based** synthetic V43 source-yield experiment; any Bloom positive not confirmed in the exact digest inventory is retained as potentially novel. ETag 'not modified' is never buyer proof, confirmed rights, true semantic relevance or independent freshness. No source collection or actual HTTP fetch occurs.
- `tests/test_flagship_v43_novelty_shadow.py`: Bloom false-positive/false-negative controls; future, missing, invalid, duplicate, stale, unreviewed and rights-unknown input holds.
- `scripts/review_flagship_legacy_shadow_20261019.py`: deterministic synthetic-only reproducible command; no production source or DB reads.

### Existing canonical ownership and mapping

| Legacy field/behaviour | Existing EmpireOS owner/contract | Safe use |
| --- | --- | --- |
| metro, claimed adjacent markets, specialty Jaccard | existing geo, contractor research and buyer buybox owners | A **counterfactual**. Existing exact territory, licensing and product gates always take precedence |
| trust score, dispatch recency, capacity | existing Buyer Capacity / CRM / suppression owners | Require source-bound evidence. No v49 trust midpoint and no capacity based on a self-claim |
| weighted matcher rank | existing `lead_scoring_v2.py` and Quant Brain | Separate quality, evidence confidence, conditional economics and independently verified probability |
| nightly 90-day bucket tuner with >=10 observations and $500 minimum fee | existing `lead_shadow_calibration_benchmark.py` | **Do not import thresholds, retrain or auto-write**; existing prequential temporal holdout wins only when genuine, prior, paired outcomes exist |
| similarity outcomes and historical attribution | existing Economic Memory / original forecast registry | Never import legacy Supabase or private embeddings; require tenant/opportunity and original prospective forecast with independent payable/settlement receipt |
| V43 conditional fetch, Bloom, SLM | existing Search / Source Intelligence owners | Test only on rights-cleared frozen corpora after owner handoff. Bloom positives require exact confirmation; V43 marketing savings remain unverified |
| NWS/storm/social events, digital twins | existing Storm Predictor, Knowledge Graph, Market Features and shadow simulations | Use source time, licensing, versioned event IDs. Never treat simulations and forum posts as successful customer outcomes |
| Solana/USDC payouts, old 70/20/10 and automatic dispatch | retired legacy v49 paths | **Not imported**. Current payment policy USDT on BSC remains separately gated |

The canonical `homeowner_matching.py` has a separate stateful job workflow and is NOT interchangeable with a proof of pay-per-lead buyer capacity; it was not modified. No existing CRM, Search Intelligence, source collectors, outbound, payment, cloud production, registry or original model weights were changed.

## Production truth and next required commercial evidence

Observed on 19 October at review time: original Economic Memory learning readiness `INSUFFICIENT_VERIFIED_EVIDENCE`, verified commercial calibration reviews = **0**, verified outcome feedback = **0**. The current Opportunity Factory source snapshot was 11/11/11/11 with canonical source join passing, but this has previously fluctuated due to upstream Community Intent. These are timing-specific observations; rerun source-epoch diagnostics before future buyer evidence matching.

**Next gate:** supply genuine independently reviewed first-party buyer terms, verified lawful territory/specialty/capacity, source rights and exact same-tenant/same-opportunity receipts. For scientific calibration, register original forecasts prospectively, then join independent terminal verified outcomes and actual funds/delivery in Economic Memory. Require complete forecast denominator and historical base-rate controls. With zero current paired outcomes, no model promotion or prediction accuracy claim is justified.

## Repeat offline shadow on the owner server

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_flagship_legacy_shadow_20261019 --synthetic-only
PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -B -m pytest -q tests/test_flagship_legacy_v49_shadow.py tests/test_flagship_v43_novelty_shadow.py
```

**Feature-only release boundary:** no production deploy, database migrations, fund movement, real contact, Coder task, approval escalation, external model fetch, or automatic training.
