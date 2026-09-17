# BSC payment evidence — staged, OBSERVE-only

The preview adapter reads approved terms from canonical Supabase and checks BSC.
It never records evidence, activates buyers, delivers orders, or recognizes revenue.
The SQL recorder is implemented, but API roles cannot execute it or insert evidence.

Canonical Supabase project `owbeinlfcfdtwcwrttjy` currently has migration
`20260917161939_bsc_usdt_payment_verification` applied. At the 2026-09-17 review,
`bsc_payment_requests`, `bsc_payment_evidence`, and `buyer_commercial_evidence`
contained zero rows. `record_bsc_payment_evidence` remained owner-only; service_role,
authenticated, and anon could not execute it.

The request binds buyer, order, amount, payer, treasury, terms fingerprint, expiry,
and minimum payment block. Amounts are read as text to preserve token precision.
A trigger rechecks those terms under row locks when inserting evidence.
Unique keys reserve a transaction, request, and order once. Identical RPC retries
return the existing evidence ID; differing evidence fails. Evidence is append-only.
Approved request terms are immutable; cancellation and expiry remain possible.
The verifier supplies chain evidence; PostgreSQL cannot verify the chain itself.

Forward migration `20260917165008_bind_buyer_payment_to_bsc_evidence.sql` replaces
the legacy `crypto_payment_requests` verification branch for buyer commercial
evidence. A `verified_payment` must reference canonical `bsc_payment_evidence` and
match the buyer, order, commercial terms hash, payer, treasury, BSC chain/token,
amount floor, minimum block and confirmation threshold. The bridge does not record
payments or activate buyers by itself.

## Validation
Real PostgreSQL integration tests run in isolated temporary clusters on loopback.
No production URL or credential is accepted by the test runners. Dependencies are
pinned and locked under `tests/payment_db`.

```bash
npm ci --prefix tests/payment_db --no-audit --no-fund
EMPIRE_PG_TEST_DEPS="$PWD/tests/payment_db" node tests/payment_db/test_recorder.mjs
EMPIRE_PG_TEST_DEPS="$PWD/tests/payment_db" node tests/payment_db/test_buyer_payment_bridge.mjs
.venv/bin/python -m pytest -q tests/test_bsc_usdt_verifier.py tests/test_bsc_payment_evidence.py tests/test_buyer_allocation.py
```

Current validation: 24 recorder database tests, 5 buyer-payment bridge database
tests, and 73 Python tests pass. Test fixtures are synthetic only inside disposable
local PostgreSQL databases; production business/payment data is never synthesized.

## Remaining deployment gates
1. Review and explicitly approve the forward buyer-payment bridge migration before
   applying it to canonical Supabase.
2. After applying it, verify function ACLs and rerun Supabase security advisors.
3. Build the governed payment-request approval workflow and dedicated verifier role;
   API payment recording remains intentionally disabled.
4. Do not grant the recorder to service_role as a shortcut around verifier governance.
5. Review revenue recognition separately; receipt of USDT is not automatically
   recognized GBP/USD revenue.

No execution-mode, runtime route, queue handler, or production service change is
included. EmpireOS remains in OBSERVE mode. No SQLite production fallback exists.
