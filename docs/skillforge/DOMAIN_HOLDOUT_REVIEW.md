# SkillForge — Commercial and Predictive domain holdout review

**State: OBSERVE / author-authored synthetic cases / policy proposal only.**

This evaluation tests actual named EmpireOS functions against 41 hand-authored,
non-sensitive contract scenarios. The proposed stricter safety checks exist
**only in** `empire_os/skillforge_domain_holdouts.py`. They are not invoked by
live product or forecasting readers. The runner uses no credentials, database,
customer data, network, inference service, billing or outbound tools.

## Measured code-contract replay

| Domain | Specific baseline | Case count | Actual code matched authored labels | Proposed checks matched authored labels | Newly caught issue cases | Regressions |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Commercial product catalogue | `assess_catalog_item` + `public_catalog_projection` | 22 | 12 | 22 | 10 | 0 |
| Predictive Cloud V3 foundation | `forecast_observed_metric` | 19 | 16 | 19 | 3 | 0 |

The ten catalogue case IDs caught by the proposed validation are:
`missing_price_cents`, `zero_price_cents`, `negative_price_cents`,
`missing_acquisition_cents`, `negative_fulfilment_cents`, `currency_mismatch`,
`unit_mismatch`, `margin_floor_breached`, `invalid_margin_floor`,
`missing_product_id`.

The three V3 cases are `duplicate_observation_dates`,
`irregular_daily_cadence` and `future_observation_leakage`.

These counts are *not* live production incident counts. In particular, the
commercial catalogue reads a restricted, canonical EmpireDB RPC, which may
already reject such malformed records upstream; this replay assesses the
**downstream** Python projection under deliberately malformed verified-state
inputs. The predictive tests exercise a V3 directional forecast function, **not**
the entire production Predictive Cloud opportunity loop or future-outcome
forecast accuracy.

## Source and evidence contracts

- Fixtures are checked in as:
  `tests/fixtures/skillforge_domain/commercial_catalogue_v1.json` and
  `tests/fixtures/skillforge_domain/predictive_cloud_v1.json`.
- Each case has an authored expected allow/block decision; there are positive,
  negative, boundary, missing-evidence and leakage cases. These labels have
  **not been independently reviewed** and the candidate validation was
  written with access to them; measured agreement is susceptible to overfit.
- Reports include fixture and code content digests and block evaluations if
  either file changes during replay. The runner checks that the imported
  production module comes from the intended checkout. Private optional reports
  are append-only and stored with file permissions `0600`.
- Existing SkillForge review drafts are linked by component identity, but are
  not modified, approved, loaded or executed.
- All reports explicitly record `labels_independently_reviewed=false`,
  `skill_quality_verified=false`, `proposed_policy_deployed=false` and
  `execution_authority=none`.

## Operator commands (from `/srv/empire_os`)

```bash
./.venv/bin/python scripts/skillforge_domain_holdout.py --domain both
./.venv/bin/python scripts/skillforge_domain_holdout.py --domain both --save-private
./.venv/bin/python -m pytest -q tests/test_skillforge_domain_holdouts.py
```

The first command prints only high-level results. The second stores full
synthetic case-by-case comparisons in `runtime/skillforge/domain_holdouts/`.
No systemd changes or new timers are required.

## What independent evaluation still requires

1. **Independent policy/label review:** owner or separate reviewer verifies each
   expected decision from canonical EmpireDB product contracts and forecast
   specifications, then locks an unseen holdout set with provenance and
   immutable file digests. The implementer must not tune the proposal to this
   holdout after review.
2. **Actual outcome evidence:** for catalogue cases, verify economic facts,
   effective windows, permitted units and source-of-truth amount semantics; for
   forecasts, collect time-separated outcomes that were not in training or
   prompt context, measuring errors and calibration rather than just input
   admission.
3. **Skill-level A/B:** run the *same* isolated agent/model and sealed cases
   without and with the SHA-256-pinned skill instructions, using repeatable
   model parameters, timestamped output artifacts, exact source/model digests,
   negative cases and no production tools. This current domain replay tests
   proposed deterministic input guards, **not** skill instructions.
4. **Regression/risk assessment:** check that any strict gate does not reject
   valid catalogued free products, allowed multi-currency costs, volume-based
   billing, irregular yet valid time-series data or approved exceptions under
   authoritative business rules.
5. **Governed promotion:** required independent quality/security/licence
   reviews, founder approval and digest-pinned trust registry update; tests
   and positive scores alone never grant execution rights.

**Release recommendation:** retain all proposed guards in evaluation-only
code until the authoritative price, cost, unit and forecasting timestamp
contracts are checked. No automatic skill promotion, recognition of revenue,
production forecast change or live outbound follows from these observations.
