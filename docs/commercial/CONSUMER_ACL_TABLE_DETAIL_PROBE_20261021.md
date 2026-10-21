# Empire AI consumer opt-in — TABLE_ACL diagnostic continuation

**21 October 2026. Production first failing stage remains TABLE_ACL. No production change is authorised by this diagnostic.**

## Original production evidence

The founder executed the exact root-owned read-only segmented diagnostic on EmpireDB, receiving:

```json
{"email_sent":false,"first_failing_stage":"TABLE_ACL","production_database_modified":false,"status":"CONSUMER_PRIVATE_IDENTITY_DIAGNOSTIC_HOLD","subscriber_rows_fetched":false}
```

This shows earlier stages reached and passed through authenticated TCP SCRAM, root key-vault validation, exact role membership, `SET LOCAL ROLE`, five FORCE RLS tables and exactly five scoped policies, but **does not establish which table privilege failed**. The held code treats a boolean mismatch and SQL exception identically. No CRM exposure should be asserted without direct catalog evidence.

## New non-mutating ACL isolation

`scripts/review_consumer_table_acl_detail_20261021.py` is a root-only `--read-only` diagnostic:

- Authenticates as only the existing consumer login using the original **unchanged** root-owned review implementation pinned to SHA256 `7799c81a37a0806a370a710a20ea32f59304ce7fb30e5c0d69feb031056aac42`. It never prints or persists the password/key material.
- Explicit `SET TRANSACTION READ ONLY` and `SET LOCAL ROLE empire_consumer_optin_writer`.
- Tests the **five exact consumer tables**, each against four discrete catalog checks: writer SELECT present; `empiredb_app` SELECT denied; `empiredb_readonly` SELECT denied; PUBLIC SELECT denied.
- Responds with only these public role-permission booleans, table name from an internal whitelist, and the first failing check; if a PostgreSQL error prevents that, reports only the stage and an allowlisted 5-character SQLSTATE (no SQL exception text).
- **No** subscriber SELECT, inserts, alterations, grants, revokes, HBA edits, role changes, email messages or service activation.

SHA256: `443653773a21d2e55062c74c123814234503d061441591162176f6b2a5a93e45`

Staged nonsecret source:
`/var/tmp/empire-consumer-acl-detail-20261021.yD5GyGvp/review_consumer_table_acl_detail_20261021.py`

## Execution in trusted founder terminal

Because staging is Ubuntu-owned, **do not run it as root from that directory**. First copy the checksum-verified source to a root-owned 0500 target, then execute:

```bash
sudo -n install -D -o root -g root -m 0500 \
 /var/tmp/empire-consumer-acl-detail-20261021.yD5GyGvp/review_consumer_table_acl_detail_20261021.py \
 /usr/local/lib/empire-os/private-consumer/review_consumer_table_acl_detail_20261021.py && \
printf '%s  %s\n' \
 '443653773a21d2e55062c74c123814234503d061441591162176f6b2a5a93e45' \
 '/usr/local/lib/empire-os/private-consumer/review_consumer_table_acl_detail_20261021.py' \
 | sudo -n sha256sum --check --status && \
sudo -n /srv/empire_os/.venv/bin/python -B \
 /usr/local/lib/empire-os/private-consumer/review_consumer_table_acl_detail_20261021.py \
 --read-only
```

## Testing

- **203 selected Python regression tests pass**, one preexisting Starlette/AnyIO deprecation warning.
- Disposable PostgreSQL 18 fixture passed: all four permissions across five new consumer relations reported correctly in the healthy fixture. An intentionally introduced `empiredb_app` SELECT grant on **only one test table** produced `CONSUMER_ACL_READONLY_HOLD`, naming that exact table and `crm_app_select_denied`. The original grants were restored **only in the temporary fixture**. The database was destroyed automatically.
- Nine targeted unit tests verify per-table categorization, read-only SQL, stage-level exception redaction and root-only execution.

## Next action after the production readback

Inspect the exact failed table/permission or safe SQLSTATE. If genuine table ACL exposure is detected, determine the source of the drift before proposing an exact-table fix, test that fix on disposable PostgreSQL and obtain a separate founder authorisation for any production privilege mutation. If an incorrect checker query is diagnosed, patch and test the verifier with **no production ACL modification**.

Private subscriber service, public signup, Resend send, buyer referral and payments remain off.
