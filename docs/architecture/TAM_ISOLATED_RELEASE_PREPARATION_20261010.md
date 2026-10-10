# Isolated TAM Market Reader — Prepared Release, Founder Approval (Preparation Only)

**Prepared 10 October 2026 — OBSERVE / HELD.**

Founder's instruction approves *preparing* this TAM-only role, login, secret-delivery and bounded research-reader release. **It does not approve any production DDL, password provisioning, unit installation/start, live market-data reading, credentials modification or automatic scheduling.** This release is separate from legacy migration 028 and preserves every existing Market GPS/materializer grant.

## Exact package

| File | Role in release |
| --- | --- |
| `deploy/empiredb/tam_isolated_roles_bootstrap.sql` | **HELD** DBA-only single-use transaction. Adds `empire_tam_market_reader` NOLOGIN and `empire_tam_market_login` LOGIN, NOINHERIT, CONNECTION LIMIT 2, `PASSWORD NULL`; grants only the isolated membership, CONNECT and schema USAGE; checks no direct source table rights |
| `migrations/empiredb/043_tam_isolated_restricted_reader.sql` | **HELD**, run after bootstrap in separately authorised transaction. Copies the existing vetted canonical country/identity query without changing its evidence meaning; SECURITY DEFINER STABLE owned by `empiredb_migrator`, empty search path, max 5,000 rows. Only the isolated capability receives EXECUTE. Rejects old-role rights and requires source-table isolation |
| `empire_os/tam_market_runtime.py` | Uses isolated login and role **only** for future canonical TAM reads. Verifies live role/function/grants before data SELECT; still offers *legacy passive* `probe_tam_reader_capability` for the existing Market GPS diagnostic, with no TAM activation authority |
| `empire_os/tam_isolated_credential.py` | Requires dedicated systemd `CREDENTIALS_DIRECTORY` and `tam-market.dsn`, permission 0400/0600, exact TAM login/local `empiredb`. No fallback to old Market GPS env, secret, login or broad role |
| `deploy/systemd/empire-tam-market-read.service` | **HELD**, not installed or started. On-demand oneshot with `LoadCredential`, `ProtectSystem=strict`, `NoNewPrivileges`, private runtime writes, no timer or `WantedBy` |
| `deploy/empiredb/tam_market_scope.env.example` | Non-secret scope-only template; no tenant/sector/country values approved by implication |
| `deploy/empiredb/tam_isolated_rollback_held.sql` | **HELD** transaction to remove only the new function/role/login; does **not** revoke legacy materializer privileges. Requires separate rollback approval if ever used |
| `tests/test_empiredb_tam_isolated_restricted_reader.py`, `tests/test_tam_isolated_credential.py`, existing TAM/Market GPS/Radar tests | Disposable PostgreSQL integration, positive/negative permission checks, credential denial, rollback and full-stack nonregression |

Do **not** run migration 028 with the old materializer. The observed conflict remains recorded at `docs/architecture/TAM_PRODUCTION_ROLE_CONFLICT_20261010.md`.

## Implementation sequence — each write independently gated

1. **Pre-release READ-ONLY catalog inventory** by authorised DBA: verify database/schema/source columns, migration sequence/ownership, object/function collision, memberships, inherited and PUBLIC grants, running Market GPS role and credentials, existing backup/recovery strategy, and no unauthorised privilege elevation. Obtain backup/rollback evidence before touching production. The current code package and disposable tests are not proof of live migration readiness.
2. **Founder approval A (DDL):** separately approve creating the two isolated roles and the bounded function. Then an authorised DBA runs bootstrap and new **043**, not 028, with `ON_ERROR_STOP`/transaction safeguards. Confirm both old live materializer SELECT grants remain unchanged and the new role has zero base-table/column permission. Verify `get_tam_market_observations(integer)` owner, SECURITY DEFINER/STABLE, empty search path, explicit EXECUTE (not PUBLIC) and bounded read-only semantics. If any guard fails, abort. Do not weaken checks.
3. **Founder approval B (credential + on-demand service):** separately approve generating a NEW strong local-only credential for `empire_tam_market_login`, writing `/etc/empire/tam-market.dsn` as private root-managed secret, and binding only to the held on-demand systemd unit via `LoadCredential`. Do not use the existing `market-gps.dsn` or install a long-running timer. An authorised operator must pre-provision the private output directory before installing the unit. Nonsecret `/etc/empire/tam-market-scope.env` must contain explicitly founder-approved research scope, sector and two-letter country codes. The repo template is intentionally not approved market data.
4. **Preflight (no market rows):** run the on-demand isolated reader preflight under the authorised protected service credential context, verify `isolated_tam_contract_verified=true` for the new identity. Legacy Market GPS passive probe will continue indicating incompatible legacy-role privileges: that is expected and not new TAM evidence.
5. **Authorised first bounded OBSERVE run:** execute the one-shot with `--refresh --limit 1000`; this repeats preflight before reading. Check private `0600` canonical snapshot, source row count, explicit ISO-2 locale, no inferred TAM denominator unless independent provenance exists, no buyer-intent/demand inference and no commercial execution. Verify Opportunity Radar and founder view safely consume the snapshot without promoting it to buyer demand or revenue.
6. **Regression/readback:** prove original Market GPS continues normally with unchanged role/DSN/snapshot; verify no cross-tenant SaaS login claims. Independent founder approval required for any customer-facing launch, outbound, payment or production automation.
7. **Rollback:** stop only the TAM on-demand context, revoke/destroy the newly provisioned TAM secret through authorised secret-management procedure, and (if separately approved) execute `tam_isolated_rollback_held.sql`. It drops only the TAM function and isolated roles, failing if unexpected object dependencies exist. Restore/verify Market GPS remains healthy; **never** revoke/downgrade legacy materializer rights to make TAM pass.

## Production truth at preparation time

- Existing protected Market GPS run: healthy, observed 10 October; legacy role has effective source table grants; original 028 function is missing.
- New isolated roles/login/function: **not deployed to production**; bootstrap leaves login with `PASSWORD NULL` even in its test staging, and does not provision any real secret.
- Credential and on-demand service: files **prepared in repository only**; unit not installed or enabled. Protected host paths were not read or written.
- TAM snapshot: **not live**; `runtime/tam_market_intelligence/latest.json` remains absent. No real TAM buyer demand or revenue is claimed.
- No new worker timer. No external sends, contracts, funds, customer-tenant login or traffic activation.

**Completion standard:** don't call TAM operational until the new isolated SQL catalog has passed on the real server, a separately authorised protected credential proves an actual bounded source read, and Radar confirms the admitted research is still non-commercial.
