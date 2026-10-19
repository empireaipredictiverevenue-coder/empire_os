# Empire AI — Original Twenty Open-Source CRM Recovery

**19 October 2026. Unified Lead Intelligence owner. Not a rebuild.**

## Production truth (checked directly)

- **Git history proves former Twenty startup was claimed:** commit
  `42c0f6cc`, description included "Twenty CRM started".
- **Hermes integration catalog contains**
  `/home/ubuntu/.hermes/hermes-agent/plugin-catalog/twenty-crm.yaml`,
  with repository `TREE-Ind/hermes-twenty-crm` and documented Twenty
  REST/GraphQL tool descriptions. A catalog entry does NOT prove an
  installed/running plugin, authenticated workspace, original data
  volume or active CRM integration.
- Port `127.0.0.1:3000` responds HTTP 200 at `/`, but is owned by
  Python SimpleHTTP, **not Twenty**. Its `/healthz` returned 404,
  `/graphql` returned 404. Thus **original Twenty is NOT currently
  verified running**; do not replace the existing process on :3000.
- Root Docker socket and `/var/lib/docker` are unavailable to the
  unprivileged Ubuntu MCP account. Neither container names nor volume
  data can be enumerated by this agent. This is an access limitation,
  **not evidence that the previous Twenty database was deleted**.
- Canonical CRM remains tenant-authorised **EmpireDB PostgreSQL**.
  Existing Founder CRM pilot and buyer records are not to be migrated,
  overwritten or joined on name alone. Twenty will be an optional
  read-only workflow/interface until a separately approved integration
  with explicit tenancy and role-bound rights is established.
- The server has approximately 24 GiB available RAM and 681 GiB free
  filesystem space from an October 19 check, but resource capacity
  alone does not authorise another always-on app.

## Owner-only metadata check, WITHOUT dumping secrets

The bundled script performs only read-only container/volume **name**
inventory and filters for Twenty. It does not call Docker inspect's
environment dump or query any customer database:

```bash
cd /home/ubuntu/empire_worktrees/lead_revenue_fabric_unified_20261019

# Unprivileged dry run: HOLD until authorised Docker access.
/srv/empire_os/.venv/bin/python -B -m scripts.audit_original_twenty_docker_20261019 --read-only

# Owner may execute on the authorised infrastructure console:
sudo /srv/empire_os/.venv/bin/python -B \
  -m scripts.audit_original_twenty_docker_20261019 --read-only
```

**Output**: only matching container names, image tags, coarse status and
volume names. Do not copy Docker `inspect` environment variables or
Twenty encryption/SMTP/API credentials into chats. If no matching
volume names are returned, use the backup inventory and known Compose
project name; Docker labels and names can differ.

## Restore original Twenty, not an empty replacement

1. **Inventory** the original Compose project, image digests, installed
   Twenty version, server/worker containers, existing PostgreSQL and
   Redis services, named DB volume, file-storage volume and backups.
   Record facts first, no restarts, no deletes.
2. **Verify backups** and confirm the Twenty workspace and company
   record census in an isolated restored snapshot. Backup must match
   the original version/schema. If legacy database data is absent,
   report it missing; do not claim a new blank Twenty workspace is a
   recovery.
3. **Preserve encryption custody:** Twenty requires its
   `ENCRYPTION_KEY` for encrypted secrets. Older deployments may use
   `APP_SECRET`. Keep original keys in a protected secrets store,
   rotate during a planned security window; do not insert old secrets
   in repository files or public logs.
4. **Private deployment** only after backup and identity verification.
   Use Twenty's official version-compatible Docker Compose, pinned
   version/digest, an isolated PostgreSQL service and Redis.
   Change the app's loopback bind to a non-conflicting private port;
   :3000 is occupied by another EmpireOS service. No public ingress
   or automatic outbound/email/marketing integration.
5. **Authentication / tenant proof:** verify Founder membership,
   existing Twenty workspace access, role boundaries and private UI.
   A health check alone does not prove identity or row security.
6. **Read-only integration:** use Twenty as a selected customer workflow
   UI. Reconcile only independently proven B2B company identities
   and tenant scope through the canonical EmpireDB review service.
   Exclude subscriber lists, person emails, insurance claimants,
   medical patients, synthetic buyer seats and cold outreach from
   automatic imports. No two-way CRM sync or dual-write.
7. **Production release gate:** authorise isolated Twenty container
   start only after verified original volume and version, protected
   auth, SMTP disabled, no unexpected port conflict, and offline
   read-only API smoke tests. Explicit separate approval before data
   imports, outbound integrations or public service exposure.

Official Twenty self-host guide:
https://docs.twenty.com/developers/self-host/capabilities/docker-compose

Official source:
https://github.com/twentyhq/twenty

## Build implemented in this branch

- `empire_os/twenty_recovery_boundary.py`: read-only original
  instance/health/catalog evidence with explicit separation of
  historical code from restored database truth.
- `scripts/review_twenty_recovery_20261019.py --read-only`:
  bounded localhost health query and old Git/plugin metadata
  readback, no data/secret reads or CRM writes.
- `scripts/audit_original_twenty_docker_20261019.py --read-only`:
  owner-only metadata inventory; fail-closed on Docker permission
  denial, never concludes old volumes were deleted.
- `compare_twenty_business_export`: offline firm-domain, provenance
  and tenant-specific review. No people, contact emails, audience
  imports, buyer intent, database writes or outbound.
- `GET /v1/founder-lead-supply/twenty-recovery`: staged **private
  Founder API route** returning aggregate readiness and blockers only.
  NOT currently deployed to running Founder production service.

## Current go/no-go

**Status: HOLD ORIGINAL DATABASE / WORKSPACE VERIFICATION.**

No Twenty container started, old database restored, original user
records verified, mail configured, marketing list imported, canonical
EmpireDB data changed, or funds spent. Root owner access to the
original Docker volumes / backups is the only blocker that must be
resolved *before* discussing any restore launch.
