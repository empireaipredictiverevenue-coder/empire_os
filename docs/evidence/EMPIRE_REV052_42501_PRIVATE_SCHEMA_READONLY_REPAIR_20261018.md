# REV052 – production login permission-probe 42501 reconciliation

**18 October 2026 · Existing EmpireDB login · no DDL, HBA, credentials or grants**

## Founder output

The already-committed REV052 login's read-only reconciliation returned:

- `auth_connection_verified=true`
- All 16 catalog checks `true` (correct DB, single hardened SCRAM LOGIN, exact
  NOINHERIT/SET TRUE/ADMIN FALSE capability membership, active founder tenant
  binding, source-table SELECT denied, HBA rule and reader function)
- `failure_stage=LOGIN_PRIVILEGES`, `sqlstate=42501`
- `REV052_POST_COMMIT_NOT_VERIFIED`.

This does **not** mean the source ledger is readable or the login password
failed. It is a permission-denied error while attempting a metadata query
under the restricted authenticated LOGIN, before `SET LOCAL ROLE`.

## Isolated PostgreSQL root-cause reproduction

Using the actual existing REV052 synthetic PostgreSQL18 fixture with a
disposable Unix socket, the test revoked `USAGE ON SCHEMA public FROM PUBLIC`
while leaving the trusted owner and the restricted capability's narrow
schema/function privileges unchanged. Under the restricted LOGIN:

- `SELECT session_user::text, current_user::text` succeeded.
- `has_schema_privilege(session_user,'public','USAGE')` returned `false`.
- Three `has_table_privilege(session_user,'public.<source>','SELECT')` name
  lookups all raised exact PostgreSQL `42501`. The login cannot resolve
  relations in that hardened namespace, which is an intended restriction.
- `SET LOCAL ROLE empire_predictive_revenue_evidence_reader` succeeded and
  the existing `SECURITY DEFINER` bounded function executed correctly,
  including tenant isolation and denied direct ledger SELECT.
- After patching the role/session verifier to avoid the unauthorized
  table-name lookup, both the original `live_login_proof()` and the existing
  read-only `review()` returned success in the isolated hardened fixture.
- The administrator-only `BEGIN READ ONLY` catalogue still independently
  verified the absence of direct source-table grants for the LOGIN.

This is a **reproduced equivalent cause**, not an independently captured
production SQL error message. The production read-only check must still pass
before we call the real REV052 login fully verified.

## Narrow fix

1. `scripts/provision_revenue_event_evidence_login_20261018.py` now tests
   only `session_user/current_user` under the restricted LOGIN before
   switching to its verified capability. It does **not** retry provisioning.
2. `scripts/review_rev052_committed_login_readonly_20261018.py` continues
   to require all administrator-only, read-only database catalogue checks
   (including raw ledger SELECT denied on three tables) **before opening any
   credential**. The authenticated probe checks login identity, capability
   switch, EXECUTE privilege and a fixed intentionally absent sentinel UUID.
   The output explicitly attributes raw table-denial evidence to
   `ADMIN_READ_ONLY_CATALOG`, not to the restricted session.
3. `scripts/diagnose_rev052_login_privilege_readonly_20261018.py`
   supplies an optional strictly read-only root-local diagnostic with
   individual metadata probes under PostgreSQL SAVEPOINTs. Denied 42501
   metadata lookups cannot abort later authorised function tests. It emits
   only booleans and sanitized SQLSTATE codes; no raw SQL exception,
   credentials or source-event records.
4. `scripts/test_rev052_42501_probe_ephemeral.sh` exercises this exact
   hardened-schema regression, original application verifier and restricted
   admin-catalog plus authenticated-session proof on disposable PostgreSQL18.

## Production reconciliation command — **read-only**, not provisioning

```bash
cd /srv/empire_os
sudo ./.venv/bin/python -B -m scripts.review_rev052_committed_login_readonly_20261018 --read-only
```

If it returns
`"status":"REV052_EXISTING_RESTRICTED_LOGIN_VERIFIED"`, the already-created
login is now authenticated and the restricted, zero-result sentinel function
call is verified. It **does not prove any real commercial event was read**.

If it still returns HOLD, the bounded separate diagnostic is:

```bash
sudo ./.venv/bin/python -B -m scripts.diagnose_rev052_login_privilege_readonly_20261018 --read-only
```

No `--apply-approved-one-tenant-login` command should ever be rerun.
No extra permission grants, role-membership change, schema relaxation, HBA
edits, password reset, new backup/recovery infrastructure, paid traffic,
outbound or customer report access were needed or authorised for this repair.

The narrow REV051 reader role/function and the canonical tenant trust
model stay as previously deployed. Payment settlement, real event proof,
full-day revenue census and client delivery remain explicitly unverified.
