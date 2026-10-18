# EmpireOS — held REV051 original revenue event evidence reader

**18 October 2026 | Founder decision: no production DDL or new credentials authorised by this task | EmpireDB only**

## Live source truth

The founder ran the existing exact read-only PostgreSQL catalog check:
`scripts/probe_predictive_revenue_event_reader_catalog_readonly.sql`

This produced `HOLD_EVENT_READER_CATALOG_NOT_PROVEN` with the following **live database facts**:
- `correct_database=true`, `all_three_source_tables_exist=true`, `canonical_session_tenant_resolver_exists=true`.
- `function_exists=false`, `capability_exists=false`, `dedicated_login_member_exists=false`.
- Remaining capability/ACL/owner booleans were false largely because these prerequisite objects **do not yet exist**, not because a deployed permission was necessarily found to be insecure.
- `rows_read_from_financial_source_tables=0`, customer release false, payment/settlement not verified.

The earlier Python source inventory had established the reader implementation exists as another agent's **untracked** source file, but no migration defines its expected function. We deliberately did **not** overwrite that code, introduce another data service, or claim the reader is live.

## Prepared *held* migration: migration 051

`migrations/empiredb/051_predictive_revenue_event_reader_held.sql` is new **staged DDL**. It has **not been applied to live EmpireDB**.

Its exact, bounded scope:
1. Preflight confirms the correct `empiredb` and a privileged DBA; halts on existing role/function collision, missing trusted session tenant resolver, missing source tables, unsafe inherited source-table privileges or migrator ownership mismatches. One transaction.
2. Create one `NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS` role `empire_predictive_revenue_evidence_reader`. Grant *only* public-schema `USAGE` and function `EXECUTE`; no underlying financial table privilege, login, membership, tenant binding or password is created.
3. Create one `SECURITY DEFINER`, STABLE `public.read_predictive_revenue_event_v1(uuid,text)` owned by the existing `empiredb_migrator`, with locked empty `search_path`. This returns exactly 12 scalar fields consumed by the existing first-party Python reader, selected by an exact event UUID.
4. Guard the source inside SQL: event `revenue_recognized` + source `actual_revenue=true`; order settled or outcome-captured; event/order same buyer, product and positive price; non-empty matching causal lineage; event and order buyers bound to the **same tenant**. A **trusted** `public.empire_current_tenant_id()`, derived from authenticated PostgreSQL `session_user` binding, must equal the matched buyers' `org_id` and the supplied tenant parameter. Invalid/missing tenant binding produces **no result**. A caller cannot use `SET ROLE`, query parameters or custom GUCs to switch its `session_user`.
5. Revoke function EXECUTE from PUBLIC, grant only to the dedicated capability. Explicitly do **not** create a dedicated LOGIN or grant membership. The live catalogue check is designed to remain **HOLD on login membership** after this migration until a separately reviewed per-tenant login and session-role binding exist.

It is not a payment/settlement audit. Even a returned 12-field event/order match is **one verified database record**, not a complete day, actual bank deposit, reconciled refunds, consumer buyer contract, customer release, autonomous sales or forecast accuracy.

## Actual isolated PostgreSQL execution evidence

A **separate, temporary PostgreSQL 18 cluster** was created under a private `/tmp/empire-rev051-fixture-*` directory, listening on a private Unix socket with TCP disabled. It was destroyed on test script exit, and production services/roles/schema/data were untouched.

`scripts/test_predictive_revenue_event_reader_051_ephemeral.sh` successfully:
- Ran the exact held migration against synthetic three-table schema and trusted session-tenant resolver in the isolated cluster.
- Checked the **existing** catalogue preflight returns HOLD before an ephemeral dedicated login is granted.
- Checked the **same** catalogue preflight returns `CATALOG_PREREQUISITES_PRESENT_NOT_EVENT_PROVEN` *after* test-only login grants.
- Returned one matching synthetic single revenue event for its rightful tenant; returned zero for cross-tenant requests in both directions and one intentionally mismatched priced event.
- Explicitly denied the dedicated capability direct `commercial_events` SELECT and a financial DELETE; no customer records, payment network, accounting database or production transactions involved.

This isolated run discovered a non-security catalogue false-negative: PostgreSQL 18 stores `SET search_path=''` as the config string `search_path=""`, not always `search_path=`. The existing catalog SQL has been tightened to accept precisely either **empty** representation (no other search path), preserving security requirements. Both the held migration and catalogue query passed together on the isolated cluster after the correction.

Run isolated regression again when needed:

```bash
cd /srv/empire_os
bash scripts/test_predictive_revenue_event_reader_051_ephemeral.sh
./.venv/bin/python -m pytest -q tests/test_revenue_event_reader_051_held_20261018.py
```

**Neither command touches live EmpireDB.** This work is feature-prepared only; migration and login activation are not founder-approved.

## Production deployment sequence is not authorised in this handoff

Before any production DDL, owner should explicitly approve the exact scoped migration after backup/rollback readiness check and a code/schema privilege review. Do not run migration 051 automatically in a department cycle or normal deployment. Do not provision a login, map tenants, copy credentials, send marketing, move funds or activate customer delivery on this basis.

If the founder approves the *exact role+single-event function* DDL, apply it once through the controlled DBA release, rerun the existing PostgreSQL catalog preflight. Expect the login field to stay false because this scoped phase intentionally creates **no login**. A subsequent *separately approved* dedicated login/tenant mapping can then be tested as a **read-only** capability; first actual record validation must use an existing legitimate event in an authorised tenant and never invented payment data. No inferred daily totals or customer-facing financial claim at any of these stages.

## Relationship to existing app and commercial work

The existing Founder API evidence guards remain live. The unchanged other-agent Python reader and source reconciler remain owned by their worktree. This release does not add an endpoint, app, timer, model, new database or payment authority, and does not mutate the existing buyer, order or revenue tables. Its only live-affecting action **if independently approved in the future** would be to create the missing dedicated database capability objects.

## 18 October founder approval / guarded deployment preparation

The founder has now **explicitly approved applying only REV051's restricted NOLOGIN
capability role and exact one-event read-only function**, after the existing
production backup, WAL-archive, schema and object-collision preflight. The
approval does **not** include a new login, tenant binding, broader privileges,
financial event write, customer-report entitlement or unrelated production
migration.

A bounded release helper has been added:

`  scripts/deploy_approved_rev051_guarded_20261018.sh  `

This shell script runs only from the local EmpireOS server and only with the
explicit `--apply-approved-role-function-only` flag as root. It first verifies
an immutable SHA256 digest of the reviewed migration, checks that an existing
pgBackRest repository has a recent completed backup, confirms the active
canonical PostgreSQL primary has archiving enabled, and verifies via the
existing read-only database catalogue probe that the specific capability role
and function do not yet exist. If any prerequisite is not demonstrated it
**stops without DDL**.

The only potential database mutation is the exact, already tested, atomic
`051_predictive_revenue_event_reader_held.sql` transaction. Afterward the
same catalogue probe must show a hardened NOLOGIN role, correct SECURITY
DEFINER/STABLE function, locked search path, migrator ownership, restricted
function EXECUTE and no direct ledger-table access. The post-deploy catalogue
status still intentionally **HOLDs on dedicated_login_member_exists=false**.

The connected remote terminal can inspect local files and application services,
but cannot access the privileged pgBackRest configuration or PostgreSQL
administrator session. Therefore backup status and actual live migration
must be checked from an authorised local administrator shell. Do not claim the
role/function has been installed until the guarded script reports
`REV051_DEPLOYMENT_DONE=ROLE_FUNCTION_ONLY_LOGIN_AND_PAYMENTS_UNCHANGED`.

After the prepared script is committed in the canonical checkout, the founder
can execute exactly:

```bash
cd /srv/empire_os
sudo bash scripts/deploy_approved_rev051_guarded_20261018.sh --apply-approved-role-function-only
```

If the script emits `REV051_DEPLOYMENT_HOLD`, inspect its precise blocker.
Do not bypass any failed backup or catalogue check and do not provision a
login as a workaround. No service restart is necessary to install a PostgreSQL
reader capability with zero connected application callers.
