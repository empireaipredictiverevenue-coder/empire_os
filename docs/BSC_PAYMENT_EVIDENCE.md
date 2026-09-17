# BSC payment evidence — staged, OBSERVE-only

The preview adapter reads approved terms from canonical Supabase and checks BSC.
It never records evidence, activates buyers, delivers orders, or recognizes revenue.
The SQL recorder is implemented, but API roles cannot execute it or insert evidence.
No live migration has been applied.

The request binds buyer, order, amount, payer, treasury, terms fingerprint, expiry,
and minimum payment block. Amounts are read as text to preserve token precision.
A trigger rechecks those terms under row locks when inserting evidence.
Unique keys reserve a transaction, request, and order once. Identical RPC retries
return the existing evidence ID; differing evidence fails. Evidence is append-only.
Approved request terms are immutable; cancellation and expiry remain possible.
The verifier supplies chain evidence; PostgreSQL cannot verify the chain itself.

## Validation
Real PostgreSQL integration tests run in an isolated temporary cluster on loopback
port 55439. No production URL/credential is accepted by the test runner.
Dependencies are pinned and locked under tests/payment_db.
From the repository root, with a non-root user and an unused port 55439:
```bash
npm ci --prefix tests/payment_db --no-audit --no-fund
EMPIRE_PG_TEST_DEPS="$PWD/tests/payment_db" node tests/payment_db/test_recorder.mjs
.venv/bin/python -m pytest -q tests/test_bsc_usdt_verifier.py tests/test_bsc_payment_evidence.py
```
The runner stops its temporary PostgreSQL process in finally. Its temporary data
directory is retained for diagnosis. Tests use minimal dependency schemas and
synthetic fixtures exclusively in the isolated database.

## Deployment gates
1. Explicitly approve applying the schema migration to owbeinlfcfdtwcwrttjy.
2. Apply the exact reviewed migration and verify the resulting schema/permissions.
3. Prepare the governed request-approval workflow and dedicated verifier permissions;
   this migration intentionally withholds API recording permissions.
4. Replace migration 006's legacy payment verification branch before buyer activation.
5. Review revenue recognition separately; USDT is not automatically GBP/USD revenue.

No execution-mode, runtime route, queue handler or production service change is
included. Absence of these tables fails closed. No SQLite fallback exists.
