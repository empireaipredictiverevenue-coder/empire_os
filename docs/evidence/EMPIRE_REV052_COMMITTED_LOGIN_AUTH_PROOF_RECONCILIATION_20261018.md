# EmpireDB REV052 — reconcile an already-committed restricted evidence login

**18 October 2026 | Existing production login NOT to be reprovisioned | Read-only diagnosis**

## Production terminal evidence

Founder executed the approved, serial `--preflight && --apply-approved-one-tenant-login` command.

```text
REV052_STATUS=READY_ONE_FOUNDER_TENANT_RESTRICTED_LOGIN
REV052_EXECUTION_AUTHORITY=none
REV052_FAILURE_STAGE=AUTHENTICATED_FUNCTION_PROOF
REV052_STATUS=HOLD_OR_UNVERIFIED_NO_BLIND_RETRY
REV052_DATABASE_TRANSACTION_COMMITTED_VERIFY_CREDENTIALS=REQUIRED
```

The **database transaction already committed**, which should have created one
dedicated LOGIN, assigned exact `SET TRUE, INHERIT FALSE` membership in the
pre-existing REV051 restricted NOLOGIN capability, and inserted one tenant
binding. The private server credential and narrowly amended local SCRAM HBA
were preserved for reconciliation; do **not** rerun mutating provisioning,
rotate the password, drop the role, or rewrite the HBA.

This state is not yet a verified authenticated production reader or a real
financial event; it is only a committed and subsequently unverified release.

## Reproduced post-commit verifier defect

The existing Python `live_login_proof()` compared a
`psycopg`-returned PostgreSQL `session_user`/`current_user` pair to
Python string literals. In an independently disposable PostgreSQL 18
fixture, actual SCRAM authentication **passed**, but the driver returned the
`name`/text role fields as **ASCII bytes**, e.g.
`b'empire_predictive_revenue_evidence_login'`. This made the original
equality check false before `SET LOCAL ROLE` or the bounded function
call, explaining a reproducible false-negative verification stage.

The existing login verifier now normalises **only** ASCII bytes or existing
strings through `role_name_text()`. Invalid encodings/types fail closed.
No database roles, HBA, tenant bindings, function grants or credentials
are modified by this source-code correction.

The expanded isolated PostgreSQL fixture proved that:
1. The exact production REV052 preflight SQL runs and verifies role, tenant,
   source and capability prerequisites against test-only data.
2. SCRAM login works; wrong password is refused.
3. `psycopg` supplies role names as bytes in this fixture.
4. The corrected **original** `live_login_proof()` now returns TRUE using
   this same disposable SCRAM-authenticated login and the existing function.
5. A separate redacted verifier performs the real read-only session and
   function call successfully.
6. An owner's existing synthetic recognised event can be read through the
   reader, while foreign-tenant events and direct ledger-table SELECT are
   denied. The fixture is deleted after the test.

## Safe root-local reconciliation (NO second provisioning)

New code:
`scripts/review_rev052_committed_login_readonly_20261018.py`

It is **explicitly read-only**, requires `--read-only`, and uses only:
- Postgres peer-admin `BEGIN READ ONLY` catalogue queries for one existing
  login, its hardened role attributes/SCRAM verifier **boolean**, one tenant
  binding, membership options, HBA validity, and financial-table privileges.
- The current 0700 root-owned vault and 0600 root-owned passfile under
  `/etc/empire/revenue-event-evidence`. The password is read into local
  process memory solely to authenticate the existing login and never printed.
- A real SCRAM authentication using that one login, `SET TRANSACTION READ
  ONLY`, `SET LOCAL ROLE` to the existing restricted capability, and one
  function call with a fixed nonexistent UUID. The function is expected to
  return **zero matching events**, which proves only executable permission,
  **not zero real commercial revenue**.
- Redacted booleans and, when relevant, a PostgreSQL SQLSTATE code. No raw
  exceptions/connection strings, real event IDs, amounts, private credentials
  or financial source rows are disclosed.

Run after the commit reaches the canonical repo:

```bash
cd /srv/empire_os
sudo ./.venv/bin/python -B -m scripts.review_rev052_committed_login_readonly_20261018 --read-only
```

Expected success:
`"status":"REV052_EXISTING_RESTRICTED_LOGIN_VERIFIED"`.

If status is HOLD, use only the safe `failure_stage`, `sqlstate`, and
`catalog_checks` / `auth_checks` booleans to diagnose. Do not rerun
the mutating `--apply-approved-one-tenant-login` command.

## Scope still open even on reader proof success

No production recognised revenue event has yet been verified. No approved
customer finance reports, payment settlement or reversal finality, full-day
census, revenue calibration, outgoing mail, live checkout, or new customer
grants are implied. The historical REV051 reader function and its SHA256 are
unchanged. Other agents' working-tree files are not touched.
