# BSC payment evidence — staged, OBSERVE-only

The preview adapter reads approved terms from canonical Supabase and checks BSC.
It never records evidence, activates buyers, delivers orders, or recognizes revenue.
The SQL recorder is implemented, but API roles cannot execute it or insert evidence.

Canonical Supabase project `owbeinlfcfdtwcwrttjy` has the BSC schema, buyer-payment
bridge, and governed request workflow applied. At the 2026-09-17 production review,
`bsc_payment_requests`, `bsc_payment_evidence`, `bsc_payment_request_events`, and
`buyer_commercial_evidence` all contained zero rows. Normal API roles cannot record
evidence. `record_bsc_payment_evidence` is executable only by the NOLOGIN
`empire_bsc_verifier` permission role (plus the database owner).

The request binds buyer, order, amount, payer, treasury, terms fingerprint, expiry,
and minimum payment block. Amounts are read as text to preserve token precision.
A trigger rechecks those terms under row locks when inserting evidence.
Unique keys reserve a transaction, request, and order once. Identical RPC retries
return the existing evidence ID; differing evidence fails. Evidence is append-only.
Approved request terms are immutable; cancellation and expiry remain possible.
The verifier supplies chain evidence; PostgreSQL cannot verify the chain itself.

Forward migration `20260917165008_bind_buyer_payment_to_bsc_evidence.sql` is now
applied to canonical Supabase as migration `20260917165748_bind_buyer_payment_to_bsc_evidence`.
It replaces the legacy `crypto_payment_requests` verification branch for buyer commercial
evidence. A `verified_payment` must reference canonical `bsc_payment_evidence` and
match the buyer, order, commercial terms hash, payer, treasury, BSC chain/token,
amount floor, minimum block and confirmation threshold. The bridge does not record
payments or activate buyers by itself.

Migration `20260917170944_govern_bsc_payment_requests` adds separation of duties:
`service_role` may propose or cancel an open request but cannot approve or record;
`empire_payment_approver` may review/approve/cancel but cannot record; and
`empire_bsc_verifier` may review/record but cannot approve. Both custom roles are
NOLOGIN/NOINHERIT and are not members of `service_role`. They receive no direct
payment-table write privileges. Proposal/approval/evidence lifecycle events are
append-only in `bsc_payment_request_events`. One open request per fulfilment order
and proposal idempotency are enforced by unique indexes.

## Validation
Real PostgreSQL integration tests run in isolated temporary clusters on loopback.
No production URL or credential is accepted by the test runners. Dependencies are
pinned and locked under `tests/payment_db`.

```bash
npm ci --prefix tests/payment_db --no-audit --no-fund
EMPIRE_PG_TEST_DEPS="$PWD/tests/payment_db" node tests/payment_db/test_recorder.mjs
EMPIRE_PG_TEST_DEPS="$PWD/tests/payment_db" node tests/payment_db/test_buyer_payment_bridge.mjs
EMPIRE_PG_TEST_DEPS="$PWD/tests/payment_db" node tests/payment_db/test_payment_workflow.mjs
.venv/bin/python -m pytest -q tests/test_bsc_usdt_verifier.py tests/test_bsc_payment_evidence.py tests/test_buyer_allocation.py
```

Current validation: 24 recorder database tests, 5 buyer-payment bridge database
tests, 14 payment-governance database tests, and 73 Python tests pass. Test fixtures are synthetic only inside disposable
local PostgreSQL databases; production business/payment data is never synthesized.

## Deployment status and remaining gates
1. BSC payment schema migration is applied to canonical Supabase.
2. Buyer-payment bridge migration is applied and verified. `anon` and `authenticated`
   cannot execute `verify_buyer_commercial_evidence`; `service_role` can.
3. Governed request proposal/approval and verifier role separation is deployed.
   No login identity has yet been provisioned for either custom role.
4. Build the operator approval tool and verifier service identity without granting
   either role to `service_role` or exposing a public mutation endpoint.
5. Keep `record_bsc_payment_evidence` unavailable to `service_role`; verification
   must use the dedicated verifier boundary.
6. Review revenue recognition separately; receipt of USDT is not automatically
   recognized GBP/USD revenue.

No execution-mode, runtime route, queue handler, or production service change is
included. EmpireOS remains in OBSERVE mode. No SQLite production fallback exists.
