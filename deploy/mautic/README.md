# EmpireOS Smart CRM — Mautic 7 private, no-send rollout

**Status (2026-11-20): PRIVATE MAUTIC 7.2.2 INSTALLED AND HEALTHY; EMPIREDB REVIEW-ONLY INBOX PROVISIONED. No live contact-source binding or outbound sending.**
Original Smart CRM and PostgreSQL services remain active without restart; EmpireDB now also contains the narrowly provisioned Mautic inbox and NOLOGIN writer role.

## Exact scope

- Official Mautic **7.2.2** Apache image and MariaDB **11.4.13** are
  referenced by Docker Hub **immutable multi-platform OCI index digests**.
- Dedicated MariaDB database and Docker volumes; **no access to EmpireDB**.
- The Compose file declares `127.0.0.1:18784:80`, but Docker does **not** publish a host port from this `internal: true` network. Verified `docker port` and host `ss` return no published listener. The MariaDB container also publishes no host port. The existing ApexEngine SSH connection now privately forwards its own `127.0.0.1:18784` to the Mautic container's internal bridge IP. This is a local, session-dependent administrator tunnel, **not a public host listener**. Both containers remain on the private Docker network without arbitrary outbound internet or SMTP reachability. No cron, mail workers, SMS or seeded
  contacts are deployed.
- This phase **does not deliver Mautic webhooks** to Smart CRM: the Docker
  internal network cannot reach the existing CRM loopback listener
  `127.0.0.1:8783`. A separately approved authenticated bridge/network
  design and an actual first-party source binding are required.

## Exact operator-gated release

1. Privileged EmpireOS/Docker owner checks the production instance and
   verifies existing Docker projects and port ownership before starting.
   The remote `ubuntu` session is **not** in the docker group; the
   connected terminal forbids `sudo`. Do not alter that ownership
   or access control indirectly.
2. The authorised owner provisions **independent cryptographically random**
   `EMPIRE_MAUTIC_DB_ROOT_PASSWORD` and `EMPIRE_MAUTIC_DB_PASSWORD`
   in a **private 0600 env file outside Git**, inside the existing
   approved secret-storage and backup system; never paste the values
   into logs, chat or version control.
3. Within this directory, preview the rendered configuration using
   `docker compose --env-file /path/to/approved/private.env -f compose.mautic7.private-nosend.yaml config --quiet`.
   Record the actual immutable image digests and inspect network, volumes,
   mounts and backup/restore plan. Do not use sample/demo data.
4. Using the same private env file, the **authorised privileged operator**
   may run `docker compose --env-file /path/to/approved/private.env -f compose.mautic7.private-nosend.yaml up -d db mautic_web`
   only after backup, image vulnerability review and change controls pass.
   No `down -v`, automatic upgrade, public reverse proxy, cron, queue
   worker or send setup is authorised by this manifest.
5. The operator must **read back** actual container health, app version,
   local HTTP response, DB persistence, data-volume backup and rollback.
   Passing `docker compose config` is only syntax validation, not a
   running Mautic installation or completed application setup.
6. Separately: DBA-reviewed EmpireDB inbox/writer migrations and
   first-party Mautic numerical-contact to Smart CRM prospect identity,
   then one no-send signed webhook canary and authenticated inbox readback.
   Explicitly review a safe ingress connection before permitting webhook
   delivery; never expose existing CRM `8783` directly to the internet.

## Live facts checked 2026-11-19

- `postgresql@18-main.service` and `empire-revenue-crm-pilot.service`
  active; actual EmpireDB readonly tenant login checked.
- Mautic inbox table: **absent**; Mautic NOLOGIN inbox writer role:
  **absent**; Mautic dedicated tenant logins: **zero**.
- `php`, `composer`, `mysql` CLI absent on host; Docker Compose v5.7.1
  installed but Docker daemon is denied to the `ubuntu` connector session.
- `scripts/test_mautic_crm_pg_isolated.sh` proves integration only on a
  disposable PostgreSQL 18 instance. No real contact identities or source
  approvals have been established.

## Latest guarded preparation and actual hold — 20 November 2026

- Pinned Mautic 7.2.2 and MariaDB 11.4.13 Docker image digests
  independently match Docker Hub's published images. Two independent
  owner-only database credentials were generated outside Git, at
  /home/ubuntu/.config/empireos/mautic_review/private.env (mode 0600).
  The Compose file passes actual Docker Compose validation using them.
  This does not install or activate any container.
- scripts/review_mautic_live_release_20261120.py performs a read-only
  authenticated EmpireDB catalog check and local service/Docker/Compose
  readiness checks. It exposes no credentials, customer identity or data.
- The user-level connected operator lacks Docker daemon access. The
  existing active privileged helper is narrow and does not authorise
  Docker installation or database migrations. Do not bypass that policy.
- scripts/build_mautic_atomic_dba_sql_20261120.py validates both
  original source SQL files by pinned SHA256 and prepares a SINGLE
  atomic PostgreSQL transaction. It never connects to the database.
- In disposable PostgreSQL 18, an intentionally introduced late index
  conflict causes the transaction to fail and leaves neither the new
  role nor the inbox table. The clean transaction then passes all
  eight isolated signed-webhook, tenant-RLS and inbox tests, followed
  by an empty-only rollback rehearsal. The collision and data cleanup
  are fixture-only, NEVER production changes.
- A real EmpireDB DBA release still requires exact founder-controlled
  change/rollback receipt, canonical database identity, full logical
  backup and globals with integrity checks, production migration
  ownership/number, independent tenant login binding, and postcommit
  permissions/readback verification. Prepared SQL is not permission
  to run production DDL.
- Production still has no Mautic service or HTTP listener, no Mautic
  inbox or writer, and no independently verified real Mautic numeric
  contact to Smart CRM prospect linkage. No source/send/marketing
  workflow is authorised merely by these preparations.

### Reproducible nonprivileged checks

Run from the isolated integration worktree:

    /srv/empire_os/.venv/bin/python -B scripts/review_mautic_live_release_20261120.py
    /srv/empire_os/.venv/bin/python -B scripts/build_mautic_atomic_dba_sql_20261120.py
    bash scripts/test_mautic_crm_pg_isolated.sh

These commands do not require or obtain Docker admin / EmpireDB DBA
authority. They cannot install Mautic or migrate production, and they
do not restart the Smart CRM pilot or permit outbound sending.

## Verified live deployment and database provisioning, 20 November 2026

The earlier "not deployed" statements in the original preparation notes
refer to the state before this release. Current authenticated evidence:

- Founder operator path: **ApexEngine's existing SSH alias `empire`**.
  Its configured, non-interactive `sudo` privileges were confirmed.
  The Ubuntu-only connector lacked Docker access; no existing helper
  allowlist or Ubuntu group permissions were broadened. Root's Docker
  Compose CLI plugin was installed from the already available, hash-checked
  local binary (SHA256 `af426722a8af5de812fcee30cc1c39f0639f5f723cbadefb25e5d4db054064cf`).
- `activate_mautic7_private_nosend_20261120.sh` installed the exact
  digest-pinned Mautic 7.2.2 and MariaDB 11.4.13 Docker images into
  `empire-mautic-review`. The private Docker network and dedicated
  named volumes are present. Both containers report **healthy**.
- `finish_private_install.sh` ran the genuine official Mautic CLI
  installer. Database schema: **126 tables**. Mautic CLI confirms
  `Mautic 7.2.2 - app/prod`. The private HTTPS warning is expected:
  this application has NOT been exposed on the public internet.
- **Actual Mautic HTTP:** the Apache application responded with a
  redirect to its dashboard. The private ApexEngine tunnel delivered
  HTTP **200** for `http://127.0.0.1:18784/s/login`. This port is
  local to ApexEngine while the SSH tunnel is running. The EmpireOS
  public host did not open the declared 18784 port.
- Root-owned Mautic backup receipt
  `/var/backups/empiredb/mautic-app-20261120/20261120T103507Z`
  contains the SQL dump of all 126 Mautic tables, private local config,
  admin recovery credentials, and a verified SHA256 manifest.
- Founder-approved EmpireDB migration receipt
  `/var/backups/empiredb/mautic-inbox-20261120/20261120T102945Z`.
  Before migration, a complete `pg_dump -Fc` and
  `pg_dumpall --globals-only` were independently hash-verified.
  After migration, the dedicated Mautic NOLOGIN writer role and
  `public.empire_crm_mautic_event_inbox` exist with forced RLS;
  schema/table privileges, tenant isolation and zero initial rows
  were verified postcommit.
- The two protected SQL scripts were reconciled against the **actual**
  canonical PostgreSQL roles: the live migrator role is NOLOGIN/INHERIT,
  and the optional legacy CRM journey-writer role is absent.
  Neither attribute is a reason to manufacture a new production role.
  The final combined atomic SQL digest was
  `0efa236d8deb18c98cd99609d20ab669d5b142cd2e8de4d612ca98b2feb9445d`.
  Disposable PostgreSQL 18 tests passed with those exact role conditions.
- A **real authenticated CRM tenant login**, after the existing
  application's `SET LOCAL ROLE empire_revenue_crm_reader`, successfully
  performed a read-only query of the live Mautic inbox:
  **tenant match TRUE, SELECT TRUE, INSERT FALSE, 0 events**. A direct
  login without the required `SET LOCAL ROLE` is intentionally
  restricted; it is not a database-grant defect.
- Read-only Mautic source counts from the **actual installed MariaDB**:
  **0 contacts, 0 webhooks, 0 queued webhooks and 1 administrator**.
  Therefore there is currently NO genuine Mautic numeric contact to
  bind to an existing Smart CRM prospect. The integration router remains
  unmounted and both CRM and Mautic sending/workers remain disabled.
- No customer or partner was contacted, no synthetic customer or revenue
  event was claimed, and no original Smart CRM/PostgreSQL service was
  restarted. The private application is installed, but its link to real
  consented CRM contacts is **not live**.

**Important:** Do not rerun the one-shot deployment/migration scripts
against the now-provisioned environment. Inspect actual state and use
the existing founder/DBA change gates for any subsequent modification.
The private MariaDB and admin credential backups contain sensitive
secrets: keep them root-owned and never attach them to chats or Git.
