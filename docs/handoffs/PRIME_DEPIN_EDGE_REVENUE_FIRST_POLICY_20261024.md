# EmpireOS Predictive Cloud — Revenue-First DePIN/Edge Policy

**24 October 2026.** Owner: original EmpireOS Core & Operations / EmpireDB DR owner.
Feature branch: `feature/predictive-edge-depin-governance-20261024`
Worktree: `/home/ubuntu/empire_worktrees/predictive_edge_depin_governance_20261024`

## Locked founder direction

1. **No purchased GPUs or paid edge services until verified realised revenue exists.**
   Current GPU/edge allocation = **0**. A claimed `closed_won`, forecast
   P10/P50/P90, simulated expected value, pipeline stage, fake revenue Boolean
   or arbitrary caller-provided receipt **does not unlock spend**.
2. Preserve the **original** EmpireOS/ASTRA/PRIME, local inference, EmpireDB,
   pgBackRest backup/archive, Smart CRM and existing server. No new system
   replacing them; no Supabase, Stripe payouts or Solana conversion.
3. Continue using existing owned compute. Only after independent authentic
   finance reconciliation and a separately approved founder cost/contract
   and security review can a NEW owner-controlled release consider external
   GPUs or regional infrastructure.
4. The DePIN API URL, GPU price, supplier capability, advertised 80% saving,
   remote data rights and vendor claims in the pasted concept are **unverified**.
   Do not assume a live `/deploy` or `/execute` API or use `:latest`
   images. Do not copy the apparent demo API key into any environment.

## What is actually built

`empire_os/predictive_edge_depin_governance.py` is a small **pure,
OBSERVE-only proposal evaluator** living on a feature branch derived from
the already completed PRIME source branch. It does not install or create any
server, send any provider calls, create a PostgreSQL publication/slot,
move the primary, touch DNS, change backups, connect to a DB, use secrets,
accept payments, or run a daemon.

- Provider quotes are only cost hypotheses; fixed GPU count × fixed hours +
  egress + other estimated costs, reported as exact minor units with explicit
  currency and no FX assumption. Quotes are never independently attested
  by this module.
- The spend policy is hard-coded as
  `REVENUE_GATED_COMPUTE_SPEND_CAP_CENTS = 0`. Both top-level spending caps
  and individual GPU candidate caps must equal zero; all GPU candidates
  retain blockers for independently verified realised revenue, approved
  external provider custody and future founder release authority.
- Accepts only allowlisted research categories and explicit, bounded,
  structured candidate inputs. Cannot smuggle in `revenue_verified`,
  `closed_won_revenue`, a fake approval or any provisioning intent.
- Replica suggestions remain **proposals**; a supplied all-green checklist
  is not proof of privileges, data rights, TLS, WAL retention, replication
  topology, schema/sequences or failover. Source primary remains unchanged.
- No API credentials, customer records or log payloads are returned.

### Actual read-only existing host observation

Captured using `empire_os.data_cloud_infrastructure.observe_local_host()`
in the feature worktree (not by configuring or provisioning a provider):
- 8 logical CPU cores
- ~62.7 GiB total RAM
- ~615.2 GiB free disk
- `psql` and `pgbackrest` executables available
- Existing minimal capacity policy: `capacity_ready=True`
- GPU spend cap: **0**, deployed GPU nodes: **0**, created replicas: **0**

These host checks establish **local available capacity only**. They do not
measure sustained workload latency, verify a current backup or a completed
restore rehearsal, certify GPU availability, or prove external DR.

## Original EmpireDB recovery architecture

The server has PostgreSQL 18 main online and the existing pgBackRest
archive/recovery programme. Do **not** apply the pasted
`archive_command='cp %p ...'`, add logical replication slots, publish
tables, or promote a replica on this branch.

Any eventual regional replica requires the original DB owner to decide
physical streaming vs logical table replication, audit tenant RLS, privacy,
data residency, TLS/auth, DDL/sequence synchronization, WAL retention caps
and alerts, backup/failover/restore, rollback and full security review.
Read-only analytics replicas must never become a second writable EmpireDB.

## Subsequent GPU revenue gate — no automatic unlock

The **future** owner-approved process, if commercially justified:
1. Authenticate a genuine settled and recognised EmpireDB commercial event,
   product/order lineage, settlement and fulfilment evidence. One single
   verified event cannot certify aggregate monthly profitability.
2. Assess sustained realised revenue and cash margin against a conservative
   GPU cost ceiling, including network/data egress, currency settlement,
   taxes where applicable and provider contractual risk.
3. Benchmark whether existing 8-core local deployment is actually exhausted
   or GPU acceleration demonstrably improves paid customer delivery.
4. Obtain an independent verified provider quote, security/data residency
   and container provenance assessment; avoid placing private customer data
   on DePIN hosts without specific approval.
5. Founder separately approves exact scope, payment method, maximum spend,
   expiry, audit owner, rollback and kill switch. Only a new controlled release
   could enable anything. This branch **does not** implement provisioning.

## Verification / owner handoff

Reproduce:
```bash
cd /home/ubuntu/empire_worktrees/predictive_edge_depin_governance_20261024
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B -m pytest -q \
  -p no:cacheprovider tests/test_predictive_edge_depin_governance.py \
  tests/test_predictive_revenue_prime.py \
  tests/test_predictive_revenue_brain_bridge.py \
  tests/test_predictive_revenue_prime_status.py \
  tests/test_data_cloud_infrastructure.py \
  tests/test_sovereign_infrastructure_observer.py
```

All candidate and authority assertions are *code-contract tests*; they do
not authorise customer release, remote data transfer or database changes.
Core owner must reconcile with other agents' uncommitted work independently.
Feature changes remain isolated; production unchanged.

Rollback: reject/revert the new feature commit/worktree. No DB, service,
GPU, DNS, payment or data transfer cleanup is required because none occurred.
