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
- **CORRECTION:** July 24 production records identify `twenty-crm` as
  an LXD/Incus-fleet instance at historical address `10.118.155.248:3000`.
  The founder-approved Docker audit returned no matching Docker records
  because Docker was NOT the documented original runtime.
- The current LXD daemon is active but `lxc list --all-projects` returns
  **0 instances** and `lxc storage list` returns **0 pools**. This shows
  that the old instance is not currently registered on this host; it
  does **not** prove old disks, archives or external backups were deleted.
- Canonical CRM remains tenant-authorised **EmpireDB PostgreSQL**.
  Existing Founder CRM pilot and buyer records are not to be migrated,
  overwritten or joined on name alone. Twenty will be an optional
  read-only workflow/interface until a separately approved integration
  with explicit tenancy and role-bound rights is established.
- The server has approximately 24 GiB available RAM and 681 GiB free
  filesystem space from an October 19 check, but resource capacity
  alone does not authorise another always-on app.

## Owner-only metadata check, WITHOUT dumping secrets

The **corrected** audit inspects only current LXD project, instance and
storage-pool metadata. It does not query a customer database or secrets:

```bash
cd /home/ubuntu/empire_worktrees/lead_revenue_fabric_unified_20261019

# LXD metadata on the current host (already verified empty):
/srv/empire_os/.venv/bin/python -B \
  -m scripts.audit_legacy_crm_lxd_20261019 --read-only

# Authorised root-only backup *filename* inventory:
sudo /srv/empire_os/.venv/bin/python -B \
  -m scripts.audit_legacy_crm_lxd_backups_20261019 --read-only
```

**Output**: only LXD metadata and bounded archive filenames. LXD backups
under `/var/snap/lxd/common/lxd/backups` are root-restricted; the
non-root scan cannot establish absence. Never print container environment
variables or encryption/SMTP/API credentials. An empty LXD catalog must
not be mistaken for verified deletion of the old database.

## Restore original Twenty, not an empty replacement

1. **Inventory** any archived `twenty-crm` LXD instance exports,
   snapshot/version, guest PostgreSQL/Redis data, file-storage volumes,
   original encryption custody and preserved offsite backups.
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
   Restore a compatible isolated copy of the original LXD instance when
   its archive exists. A fresh supported Docker Compose installation
   is a **new Twenty instance**, not restoration of historical records.
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


## Corrected infrastructure checkpoint — LXD confirmed (19 October)

The founder's root-run `audit_original_twenty_docker_20261019` found zero
Docker containers/volumes matching Twenty. This was **not a valid recovery
test of the original installation**, because production July 24 evidence in
`42c0f6cc:STACK_DEPLOY_STATUS.md` and
`42c0f6cc:empire-os-startup.md` places the historic fleet in
LXD/Incus containers. Instance name: `twenty-crm`, old address:
`10.118.155.248:3000`.

Read-only check against the current LXD daemon:
- Active `snap.lxd.daemon`, `lxc` command available.
- `lxc list --all-projects`: **zero instances**.
- `lxc storage list`: **zero pools**.
- `lxc project list`: default project only.
- Current `127.0.0.1:3000`: unrelated Python SimpleHTTP, NOT Twenty.
- Protected LXD archive root
  `/var/snap/lxd/common/lxd/backups` still exists, but current
  unprivileged scan cannot read its contents. The broader archive
  audit also encountered **41 permission-denied paths**.
- No user-visible archived Twenty database has yet been verified;
  container removal/disk deletion has NOT been established.

Corrected scripts:
- `scripts.audit_legacy_crm_lxd_20261019 --read-only`
  checks LXD instance/pool metadata, and is already verified.
- `scripts.audit_legacy_crm_lxd_backups_20261019 --read-only`
  requires an authorised root operator for a complete read-only
  bounded filename inventory, with no contents, secrets, export
  or container start.

**Single required recovery-owner command:**

```bash
cd /home/ubuntu/empire_worktrees/lead_revenue_fabric_unified_20261019
sudo /srv/empire_os/.venv/bin/python -B \
  -m scripts.audit_legacy_crm_lxd_backups_20261019 --read-only
```

An absence of matching filenames in the two scanned roots still does
not rule out historical LXD exports stored on another host or in
offsite backups. A fresh empty Twenty application must never be
labelled restoration of the old workspace.
