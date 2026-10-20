# Empire AI — Exact Canonical Order Verification and Shadow Learning Handoff

Date: 20 October 2026
Branch: `feature/commercial-verified-outcome-operator-20261020`
Worktree: `/home/ubuntu/empire_worktrees/commercial_verified_outcome_operator_20261020`

## Actual implementation

The previous release integrated genuine original Buyer Capacity and first-party Buyer Scout source-health snapshots into the **existing** Ops Control cycle. This increment builds a private, exact-order **read-only review** using the current Revenue OS / execution bus owner contracts. It adds NO agent, cron, self-triggered commercial campaign, CRM mutation, payment action, model training or database write.

New modules:

- `scripts/review_verified_commercial_order_20261020.py`: explicit `--read-only` CLI. A human/authorized original owner supplies exactly one canonical tenant UUID and 1–20 known fulfilment-order UUIDs. No buyer discovery or background scanning. It only uses `EmpireDbProvider.read_only_snapshot()`, `CanonicalDataGateway`, `ExecutionBusDataRepository` and existing `inspect_canonical_order_outcomes()`. It returns privacy-minimal cohort totals; invalid or unavailable originals result in unknown totals, never invented zero sales. Raw database errors/credentials/IDs are not echoed.
- `empire_os/commercial_verified_learning_review.py`: existing verifier + original Quant Brier scoring for an independently validated canonical feedback packet and a purported original prediction. Requires exact tenant/order binding and original prediction window. Separates confirmed recognized revenue, verified actual costs and gross profit. Reports original prediction custody **not established** by this module, and keeps shadow calibration metrics distinct from retraining.
- `empire_os/commercial_adaptive_ops_bridge.py`: passive `original_order_outcome_reader_capability` in the normal and degraded existing Founder Ops commercial status. It detects the original owner reader method's availability **in the running deployed code**; does NOT open the DB or claim that orders exist.
- `tests/test_verified_commercial_order_operator.py` and `tests/test_commercial_verified_learning_review.py` plus an existing Ops Control end-to-end sandbox test: negative verification, privacy, exact order boundaries, no synthetic-data promotion, no send/spend, and method-presence transition.

## What is genuinely missing

The code for `ExecutionBusDataRepository.verified_outcome_feedback()` was observed on the live host within **another owner's uncommitted changes**, not the clean committed release base. This branch leaves that owner file completely unchanged. Until they separately publish the authenticated canonical reader, running the new CLI returns `CANONICAL_OWNER_READER_NOT_DEPLOYED` and performs **no database connection or order query**.

No actual authorized tenant/order pair was supplied for this new workflow. The tests use clearly synthetic offline fixtures only; the deployed Ops status cannot treat them as real revenue.

When an existing authorized owner provides tenant+order IDs, the CLI is run in its own restricted operating context, with an approved read-only `EMPIREDB_DSN`; the read-only snapshot blocks mutation. Never paste tenant IDs, customer records, DSNs or order IDs into global Ops logs, test fixtures, chat handoffs or outbound job prompts.

## Operator workflow

**Read-only exact-order review (only after the owning canonical repository reader is deployed):**

```bash
cd /srv/empire_os

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_verified_commercial_order_20261020 \
  --read-only \
  --tenant-id "${AUTHORIZED_TENANT_ID}" \
  --order-id "${AUTHORIZED_CANONICAL_ORDER_ID}"
```

The process must already have an authenticated, appropriately restricted `EMPIREDB_DSN` in its environment. Do not print credentials. The existing provider creates a transaction with `read_only_snapshot()`. The command validates all UUIDs and 20-order bound before any database connection.

**If the original reader is not deployed:** the command prints `CANONICAL_OWNER_READER_NOT_DEPLOYED` with no speculative money metrics. **If an order is missing or cannot be verified:** it reports incomplete proof and suppresses cohort revenue/profit totals.

**Shadow prediction review (after original canonical owner has supplied verified feedback):**

```python
review_verified_learning_candidate(
    feedback=original_owner_verified_feedback,
    original_prediction=original_prediction_from_existing_owner_or_none,
    tenant_id=authenticated_tenant_id,
    exact_order_id=canonical_order_id,
    now=timezone_aware_utc_clock,
)
```

The function only computes an in-memory metric and returns a sanitized packet. Even a numerically correct Brier score on a supplied prediction **does not authenticate the original prediction's storage/provenance**; the existing Revenue OS calibration and model-review owner must independently attest original prediction custody and eligibility.

## Operations and owner authority

- Existing Ops Control continues on its own timer. There is no new scheduler.
- Newly surfaced static method-readiness field: `adaptive_commercial_summary.original_order_outcome_reader_capability`.
- A ready method is *not* a ready contract, a verified sale, or a functioning tenant-scoped DB role; it is only a code presence check.
- No automatic canonical DB reading occurs from the global Founder Ops loop. Per-tenant transaction results never go into global Ops memory.
- After a real verified order, original economic / calibration / finance owners still govern permissible learning, spend, buyer routing and financial recognition.
- A nonzero purchase or source count from Buyer Scout remains separate from canonical payment and realized margin.
- Provider exceptions are not echoed. A canonical reader or datasource error leaves results unknown, not falsely successful.

## Release checks

Test the new modules plus existing Revenue OS, predictive calibration, original full Ops Control, buyer source-health, and Owner Console suites in isolated worktree. Reconcile new upstream commits; preserve every other agent's uncommitted file. Activate only the passive source readiness update through the existing Ops timer after controlled merge. **Do not merge the other owner's dirty canonical repo file and do not run a live order review without an explicit authenticated order/tenant source.**
