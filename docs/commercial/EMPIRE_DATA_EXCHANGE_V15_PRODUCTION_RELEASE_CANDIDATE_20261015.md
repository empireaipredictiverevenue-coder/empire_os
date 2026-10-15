# Empire Data Exchange V15 — Production release candidate evidence

Date: 2026-10-15 UTC | Release scope: construction-source OBSERVE custody ONLY

## Exact artefact

Base implementation: commit `693e555f` on `feature/empire-data-exchange-20261014`.
This release hardening increment adds the disposable live PostgreSQL 18
gauntlet, source-identity enforcement in the SQL trigger, and safe PostgreSQL
SQLSTATE diagnostics (never credentials/source text).

**PREPARED, NOT APPLIED** schema proposal:
`docs/commercial/prepared_sql/PREPARED_ONLY_data_exchange_observation_custody_20261015.sql`

SHA256: `d0288b5d69e29da2759e4ba64d67f7399fd5271eb5fefb959a4986a3a2996769`

Do not use any other SQL hash when performing a release. Compare the exact
file hash with the review receipt immediately before migration.

## Independent on-server PostgreSQL gauntlet

Operator: `PYTHONPATH=. /srv/empire_os/.venv/bin/python -m scripts.gauntlet_data_exchange_postgres_isolated`

The test starts **disposable PostgreSQL 18.6** as the unprivileged `ubuntu`
user in a private temporary directory, listening solely on a private UNIX
socket (TCP disabled). It creates an independent fixture-only DB, migrator
and custodian roles, applies the exact above SQL, and then performs actual
DML with a separate LOGIN + SET ROLE, not mocks:

- First and second OBSERVE snapshots committed and read back.
- Exact repeat is a no-op; no extra history row.
- Independent chain recomputation and V14 signal board reconstruction pass.
- Incomplete insert denied by DB constraints.
- A convincingly-shaped row with forged official source URL rejected.
- A convincingly-shaped row with private contact data rejected.
- UPDATE, DELETE and TRUNCATE rejected by real PostgreSQL trigger.
- Exactly two historical rows remain after negative tests.
- Test PostgreSQL stopped and removed automatically.
- Zero production DB changes, customer delivery, payments or outbound.

The PostgreSQL DDL originally contained an operator-precedence type-cast bug
in an added source-URL check. The live gauntlet exposed SQLSTATE 22P02 and
the URL/record-ID expressions were explicitly parenthesised. The exact SQL
hash above refers to the **corrected** version, which passed the live gauntlet.

## Only remaining production operations

The release candidate is internally verified but **not yet installed in
EmpireDB**. These are actual release actions, not feature development:

1. Confirm canonical EmpireDB migration ledger and other teams' live
   migration ownership. Multiple worktrees have incompatible `051` and
   `052` drafts. DO NOT assign `052` by assumption. Allocate one unique
   ordered migration number by the production migration owner.
2. Verify the exact SQL hash above and prepare a reviewed rollback/backup
   plan without bypassing append-only custody.
3. Through the existing authorised database administrator, provision
   `empire_data_exchange_custodian` as NOLOGIN/NOINHERIT, no SUPERUSER,
   no BYPASSRLS or broad app membership. The prepared SQL requires this
   existing role; it intentionally creates no role or password.
4. Apply the exact schema under the established `empiredb_migrator`
   privilege, then verify the table's FORCE RLS, dedicated SELECT/INSERT
   only, and append-only triggers.
5. Provision a dedicated protected `EMPIRE_DATA_EXCHANGE_CUSTODIAN_DSN`
   LOGIN with **only** required role membership. Avoid `empiredb_app`,
   public API exposure and printing secrets.
6. Run exactly one OBSERVE source capture with the gated
   `--append --approved-custody-only` operator and protected
   `EMPIRE_DATA_EXCHANGE_CUSTODY_RELEASE` setting, then read back the
   canonical row. The first observation is not a verified event/change.
7. At a later actual observation, append the second sample and run the
   existing V14 source-change board. No fabricated field transitions.
8. Record evidence, absence of unauthorised customer exports/payment,
   and a database integrity/readback receipt before marking
   `PRODUCTION_OBSERVE_ACTIVE`.

### Production status at handoff

**CODE/SQL VALIDATED ON POSTGRESQL 18 / PRODUCTION NOT APPLIED**.

Remote Desktop Commander currently executes as `ubuntu` and cannot read
the root-owned `/etc/empiredb.env`; direct `sudo -n` was rejected by
Remote Commander's command policy. The production database has NOT been
modified by this feature. Founder already gave permission to work toward
this bounded production release, but this doesn't provide database login or
elevated OS privileges. Don't route around those boundaries.

## Non-goals

No new Supabase, agent timer, scheduled fetcher, external database,
customer API, contact enrichment, direct-outbound sender, predictive
probability, AGI-human-level claim, data-licence approval or funds movement.
Only source-traceable canonical historical observations in the existing DB.
