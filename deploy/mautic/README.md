# EmpireOS Smart CRM — Mautic 7 private, no-send rollout

**Status:** configuration prepared and Docker Compose syntax validated. **NOT deployed**.
The existing EmpireOS database, CRM service and worker fleet are unchanged.

## Exact scope

- Official Mautic **7.2.2** Apache image and MariaDB **11.4.13** are
  referenced by Docker Hub **immutable multi-platform OCI index digests**.
- Dedicated MariaDB database and Docker volumes; **no access to EmpireDB**.
- Only the local HTTP listener **127.0.0.1:18784** is published. The MariaDB
  container publishes no host port. Both containers use a single
  `internal: true` Docker network, so they cannot send SMTP or reach
  arbitrary external websites. No cron, mail workers, SMS or seeded
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
