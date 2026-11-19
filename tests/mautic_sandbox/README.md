# Isolated Mautic 7 contract sandbox — held for a permitted Docker runtime

This is an **optional test fixture only**, not a replacement for Smart CRM or
EmpireOS. It is not automatically launched or registered as a production
service. No company contact list, customer data, SMS, email provider,
publishing account, sender or production DB connection is mounted.

## Contents and provenance

- compose.yaml: official Mautic 7.2.2-20261026-apache image (the published
  October 2026 Mautic 7.2.2 Apache tag), plus isolated MySQL 8.4.
- scripts/preflight_mautic_contract_sandbox.py: no-write Compose validation
  and Docker daemon accessibility check.
- Canonical Python integration, held SQL, PostgreSQL isolated tests and
  evidence are in the existing EmpireOS branch. No Mautic source code was
  copied or redistributed.

Sources: https://hub.docker.com/r/mautic/mautic/tags and
https://github.com/mautic/docker-mautic/tree/main/examples/basic.

## Sandbox guardrails

- Both services require the manual Compose profile mautic-contract-only;
  a default docker compose up starts neither.
- The database has **no host port**; Mautic's web port is bound strictly to
  127.0.0.1:18080; the Docker network is internal.
- No Mautic worker or cron service is started, so campaign automation is
  not executed. No SMTP credentials or customer data are configured.
- Named volumes contain only synthetic fixture state. No host bind mounts,
  Docker socket or privileges are shared into containers.
- Limits: 1 CPU / 1 GB for MySQL, 1 CPU / 1.5 GB for web; no restart policy.
- Do not attach a live SMTP account, enable internet egress, import real
  contacts or change production services while evaluating this fixture.

## Verified preflight and controlled activation

A no-write preflight is run from the integration branch:

    /srv/empire_os/.venv/bin/python -B scripts/preflight_mautic_contract_sandbox.py

It validates the Compose schema, image tags, bound ports, private network,
profiles and mount restrictions without starting services or printing
credentials. It then checks Docker daemon access.

As of 2026-11-19 the preflight passed Compose/isolation checks and returned
MAUTIC_RUNTIME_BLOCKED_DOCKER_DAEMON_ACCESS (exit 24), because the current
EmpireOS operator cannot use /var/run/docker.sock. The workstation WSL
instance also failed during read-only probing. The existing LXD environment
has no configured storage pool/profile and is not used as an escalation
route. Neither Docker group permission nor host configuration was changed.

**The isolated test runner is now provided by GitHub Actions on the
integration branch**, not by escalating permissions on the EmpireOS host.
The official Mautic 7.2.2 Apache application, disposable MySQL database and
private-only synthetic webhook receiver were started and tested successfully.
No root-equivalent Docker group permissions were granted to the production
Ubuntu operator. Do not add them as an ad hoc workaround.

On 2026-11-19, run
https://github.com/empireaipredictiverevenue-coder/empire_os/actions/runs/44526866616
verified native signed webhook delivery, a real HTTP 503 retained/retried
queue entry, successful subsequent HTTP delivery, and queue acknowledgment.
The hosted runner removed all containers, database volumes and its private
network. No customer emails or production data were used.

## Test conditions once the application exists

1. Confirm Mautic version and exact image digest after pulling.
2. Create synthetic Mautic contact/form/subscription test events only.
3. Configure an isolated, authenticated webhook receiver to verify actual
   payload shape, delivery and retry. Mautic's private-address protection
   must not be disabled or bypassed in production.
4. Reconcile the resulting signed event with the existing EmpireOS
   tenant-bound CRM mapping and canonical PostgreSQL inbox.
5. Verify suppression/no-send, replay, retries and subscriber state; no
   customer mail or campaign execution is required.
6. Preserve founder/DBA release approval gates before any production
   migration or endpoint registration.

**Current verified state (2026-11-19):** The full Mautic 7.2.2 test
application installed 127 database tables and responded privately with HTTP
302. Its native persisted webhook queue issued a signed request to the
actual EmpireOS HMAC review adapter. A deliberately returned HTTP 503
preserved the queued event with retry count 1; the next processing pass
delivered the signed suppression-review event successfully and removed the
queued record. GitHub Actions run 44526866616 finished SUCCESS and verified
container, network and database volume cleanup.

**Still held:** Any production tenant contact binding, database migration,
public route registration, sender activation, publishing, deployment,
customer outreach, payment and commercial-revenue claim. All runner
events and credentials were synthetic.
