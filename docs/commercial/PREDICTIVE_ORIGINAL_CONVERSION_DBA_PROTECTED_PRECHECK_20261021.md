# EmpireDB original conversion register — protected read-only DBA prerequisites

Date: 2026-10-21; existing Predictive worktree, no production DDL or credentials applied.

## Actual present operating evidence

The founder's authenticated, tenant-scoped and read-only dedicated registry check returned `DEDICATED_ORIGINAL_CONVERSION_REGISTRY_NOT_INSTALLED` with all dedicated objects and roles absent. The original conversion migration remains staged and immutable-source pinned to an engineering commit. The founder and Predictive Cloud services are running.

The existing `empire-data-cloud-backup-observer.timer` runs at 15-minute intervals under Unix user `postgres` and its service recently reported success. However, an unprivileged `pgbackrest info` returned permission denied reading `/etc/pgbackrest/pgbackrest.conf`. An observer process reporting success **does not prove** there is a recent completed backup or independently tested PITR. The same command must not be rerouted around root/protected filesystem permissions.

## Added privileged source inspection

`scripts/review_original_conversion_dba_prerequisites_20261021.py` is an independent, strictly read-only evidence checker. It runs solely for a separately authorised root operator and accesses pgBackRest as `postgres` using the EXISTING protected `/etc/pgbackrest/empiredb.conf`. It uses only the `info --output=json` operation. Existing `review_pgbackrest_info` assesses a healthy `empiredb` stanza and recorded full-backup chain; this change adds a maximum age of **24 hours** as a conservative production DDL preflight threshold. A completed backup never proves a completed restore.

The second command is one catalog-only `psql -X -q -t -A` query against canonical `empiredb`, run as local Unix `postgres`. It inspects canonical DB/version, role attributes, tenant resolver owner/SECURITY DEFINER shape, source-defined five-object absence, `archive_mode`, and latest archiver failure relative to last successful archive. It does not query user records, finance, tenants, original predictions or protected parameters such as `archive_command`.

No stderr, raw pgBackRest JSON, WAL name, account identifier or password is returned. The output contains only redacted boolean readiness, backup age and aggregate archiver failure count. A successful observation is `PRE_DDL_BACKUP_AND_AUTHORITY_METADATA_REVIEW_READY`, but even this has explicit false values for `independent_restoration_or_pitr_drill_verified`, `offnode_backup_verified`, `original_operator_dba_security_review_signed`, `release_commit_approved_for_database_ddl`, `registry_ddl_executed` and `production_forecasting_enabled`. Missing privileges, malformed evidence, missing backup, stale backup or a resolver/schema anomaly fail closed.

`scripts/run_guarded_original_conversion_dba_preflight_20261021.sh` pins a full 40-character commit, validates only three Python files, copies the minimal approved code to an immutable root-owned `/opt/empire/original_conversion_dba_preflight_<SHA>`, checks exact SHA-256, and executes the data-free read-only checker in an isolated environment. `--check` does not connect to production or the backup repository. `--run-read-only` explicitly requires the existing authorised privileged operator. The normal unprivileged remote connector cannot operate this root-only check and must not attempt to bypass its policy.

## Remaining nonnegotiable gates

A healthy backup metadata result plus archiver observations still does not prove successful recovery, off-node backup protection, exact release security review, independent ASTRA GPT-6 review or customer eligibility. Before any live DDL, a DBA must verify a **fresh, recoverable backup and PITR/restore test**, check source-owner responsibilities and operation impact, and obtain an **explicit founder approval naming the exact migration/commit**. After a separately approved schema install, runtime LOGIN memberships, customer forecasts, original outcomes, training and commercial operations each need additional independent gates.

No deployment command is included in this candidate. It is an evidence-gathering and security-review tool only.
