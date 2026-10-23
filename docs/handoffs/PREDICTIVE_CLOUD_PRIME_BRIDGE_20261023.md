# Predictive Cloud PRIME — isolated source integration handoff (2026-10-23)

## Scope and custody

Feature branch: `feature/predictive-revenue-brain-bridge-20261023`
Worktree: `/home/ubuntu/empire_worktrees/predictive_revenue_brain_bridge_20261023`

**Owner boundary:** This is an additive OBSERVE-only Python adapter, not a
replacement ASTRA, agent queue, database, financial ledger, notification
system, CRM, prediction registry, or browser/voice controller.

Existing ownership remains:
- `empire_os.storm_intelligence_runtime` / `storm_opportunity_bridge`:
  observed storm snapshots and candidacy (not verified damage/buyer demand).
- `empire_os.permit_product_integration`: read-only official permit
  evidence and separately supplied, scoped buyer/economics read assessments.
- `empire_os.predictive_revenue_jev`: canonical signal-to-research
  recommendation and Quant economic guards.
- `empire_os.predictive_calibration`,
  `predictive_revenue_forecast_origin`, and
  `predictive_revenue_enterprise_forecast_scorecard`: prediction/evaluation
  controls. No model or proof promoted in this change.
- `empire_os.predictive_revenue_canonical_reader`: narrow EmpireDB revenue
  event truth; no new database access, accounting recognition or payments.
- `empire_os.predictive_fabric_production_bridge`: canonical commercial
  owner for customer/buyer/product execution, unchanged.
- ASTRA and existing independent coding agents: orchestration remains in
  original control plane. Nothing has been dispatched or deployed.

## New code

- `empire_os/predictive_revenue_brain_bridge.py`:
  composes existing permit and storm projections through JEV;
  prepares bounded read-only CRM pipeline evidence summaries, never pays,
  sends, allocates, promotes or counts closed-won as actual revenue.
  Missing probability evidence prevents modelled aggregate values.
  Outputs distinguish not-connected data from verified zero.
- `empire_os/predictive_revenue_prime.py`:
  optional reproducible, seed-bound 1,000–20,000-trial Bernoulli hypothetical
  contract-value P10/P50/P90 distributions. Uses exact integer accounting
  cents, verified-shaped source refs (not authenticated source claims) and
  integer basis points. Explicitly assumes **independent win events** with
  **no invented deal-value variance**, no conversion calibration, no FX
  conversions, no payment/recognition prediction, no confidence coverage,
  no accuracy claim. Percentiles are descriptive of a supplied scenario
  model, **not statistical confidence intervals**.
  Churn inputs produce private founder-retention-review tasks only. No
  email address, contact text, message, risk probability, consent,
  suppression approval or outbound execution is copied/promoted.
- `scripts/review_predictive_revenue_prime_readonly_20261023.py`:
  read-only source probe that prints only aggregate counts and status.
  It never reads a live CRM account or ledger, loads credentials, writes
  runtime files, or triggers a scheduler.
- `empire_os/predictive_revenue_prime_crm.py`: optional, explicitly
  injected canonical `PostgresRevenueCrmRepository` read only, with the
  original tenant-matching restricted role and bounded 100-row query.
  Returns prospect/closer aggregate indicators, **never treats prospects
  as deals or their probabilities as calibrated outcomes**.
- `empire_os/predictive_revenue_prime_status.py`: aggregate-only public-source
  observation renderer with evidence holds and sanitized failure modes.
- `empire_os/predictive_cloud_status_api.py`: adds
  `GET /v1/predictive-cloud/prime/status` to the EXISTING
  Predictive Cloud router, mounted by the original loopback-only private
  Founder service. No additional process or unauthenticated customer API.
  This endpoint NEVER accepts a tenant/query to access real customer CRM.
- Contract tests under
  `tests/test_predictive_revenue_brain_bridge.py`,
  `tests/test_predictive_revenue_prime.py`,
  `tests/test_predictive_revenue_prime_crm.py` and
  `tests/test_predictive_revenue_prime_status.py`.

## Source probe of canonical live paths

Read from `/srv/empire_os` as of 2026-10-23:
- 173 acquisition inbox records total (not all permits).
- Permit product integration surfaced **95** permit observations, with
  `buyer_demand_unknown`; not verified leads.
- `runtime/storm_opportunity/latest.json`: 0 candidates, snapshot
  generated 2026-10-05, **stale** at review time.
- No CRM deal import or account tenancy claim.
- No real verified forecast cohort or payment read.
- No paid traffic, outbound, chain transactions, production data writes,
  database migrations, systemd changes or production deployment.

### Repeatable read-only check

```bash
cd /home/ubuntu/empire_worktrees/predictive_revenue_brain_bridge_20261023
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_revenue_prime_readonly_20261023 \
  --source-root /srv/empire_os
```

This only demonstrates local source visibility for the system-owned
`empire-internal` OBSERVE dataset. It takes no tenant input. The actual
read-surface owner must authenticate any external tenant through the existing
signed CRM membership and tenant role chain before returning tenant data.

## Integration/release gates

1. Original Core & Operations / ASTRA owner to reconcile concurrent production
   source edits without overwriting uncommitted code. Accept this branch only
   after reviewing the additive contract, combined regressions and rollback.
2. Storm owner to refresh real official source batches under existing rate/
   license/retention rules; verify authoritative provenance and freshness.
   Do not use proxy escalation or infer actual property damage.
3. Permit owner to verify source rights, geography and quality; complete
   legitimate buyer demand and economic evidence; no homeowner personal data
   promotion from public permit observations.
4. Smart CRM owner to establish authenticated tenant-scoped read projection,
   exact allowed stage and monetary fields, stable evidence refs and source
   timestamps. No write role/DB migration is part of this branch.
5. Finance/EmpireDB owner to provide independently authenticated historical
   payment/recognition events and usable training/validation cohorts, before
   treating probability, churn, MRR, cash velocity or P90 as predictive
   commercial outputs. An authenticated single recognised event does not
   prove a complete daily total.
6. Scientist/calibration owner to evaluate time-split leakage-free forecasts
   against base rates, correlated outcomes and drift. Only after performance
   validation could calibrated models be proposed for governance review.
7. Retention/marketing owner to verify suppression, lawful basis, permissions,
   consent where required, deliverability and exact founder approval for
   any future contact. No intervention is enabled here.
8. Independently gate any deployment, migration, money movement, binding
   terms, paid traffic or live outbound through existing founder controls.

### Prior environment corrections

Canonical DB: **EmpireDB** (not Supabase).
Chain: **USDT on BSC** (not Solana).
Payment: no new Stripe payout integration.
Ad traffic: no paid traffic.
`USDT` cents in this module describe caller-provided accounting projections,
**not on-chain USDT token base units**, which require separate settlement proofs.

## Rollback

Do not merge or deploy until owners review. If rejected, delete the isolated
feature worktree/branch after ensuring no other owner is using them. This
change has no DB migrations, external writes or new daemons to roll back.

## Proof, not promotion

Latest tests and live-source read outputs must be read from the branch before
release. No forecast accuracy, buyer intent, revenue uplift or autonomous AGI
claim is established by unit tests, simulations or read-only snapshots.


## Final integration verification for this release candidate

Executed in the isolated feature worktree against the existing installed
virtualenv with `PYTHONPATH="$PWD"`:

- Combined targeted and adjacent suite: **141 passed, 1 dependency warning**.
- The existing `build_founder_dashboard_service()` test app mounted
  `GET /v1/predictive-cloud/prime/status` with no service-code edit; a
  FastAPI TestClient HTTP GET returned **200** and
  `READ_ONLY_EVIDENCE_HOLD`.
- Read-only original-source check: **95 permit observations**, 0 storm
  opportunity candidates, STALE 2026-10-05 storm snapshot.
- No prospect/customer data or identifiers returned by the new founder route.
  The separately injected canonical CRM adapter is tested against bounded
  mocked repository responses; it has **not** read the live CRM or proved
  source completeness.
- True CRM pipeline, verified outcome cohort, reliable P10/P90 coverage,
  churn labels, cash flow and finance reconciliation are **not** completed
  by these tests.

### Owner merge recipe — DO NOT APPLY TO A DIRTY ROOT BLINDLY

1. Preserve and reconcile the original owners' uncommitted modifications.
2. Inspect the latest feature commit and exact modifications, especially
   `predictive_cloud_status_api.py`, then merge/cherry-pick only after
   resolving any conflicts with concurrent website/CRM/core releases.
3. Re-run all affected test families on the combined source tree.
4. Confirm founder API network binding, reverse proxy access restrictions,
   and non-public route exposure. The passing in-process HTTP test is
   **not** an external access-control audit.
5. Execute the project's root-owner guarded release with rollback,
   separately authorised by the original owner. Read the actual running
   private route after deployment.
6. Never activate new payout rails, contact campaigns, DB migrations, or
   autonomous model/agent authority as part of this integration.

No live production runtime has been changed by this feature branch.
