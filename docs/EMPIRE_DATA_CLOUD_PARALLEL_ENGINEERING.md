# Empire Data Cloud — Parallel Engineering Plan v1

Date: 2026-09-27
Status: ACTIVE BUILD PLAN
Architecture owner: Empire Data Cloud / EmpireOS platform architecture
Integration owner: single merge owner on `feature/empire-data-cloud-v1`

## Build rule

Parallelism is allowed only with isolated path/domain ownership.

No agent may:
- modify another lane's owned files without an explicit handoff;
- touch production data;
- deploy production;
- change canonical database truth;
- bypass Supabase containment;
- widen commercial/payment/revenue authority;
- edit protected recovery/toop paths.

Every lane produces:
1. architecture-compatible implementation;
2. focused tests;
3. failure-path tests;
4. observability/readiness output where applicable;
5. clean diff;
6. independent verification evidence.

## Lane A — Core Data Fabric

Branch: `agent/data-cloud-core-v1`
Preferred builder: Hermes
Verifier: Swarm V6 / independent pytest lane

Owned paths:
- `empire_os/data_cloud_contract.py`
- `empire_os/data_fabric.py`
- `empire_os/data_backends/**`
- `tests/test_data_cloud_contract.py`
- `tests/test_data_fabric.py`
- `tests/test_data_backends_*.py`

Deliver:
- stable vendor-neutral repository/transaction interfaces;
- explicit tenant context;
- single-primary write semantics;
- shadow-read compare hooks;
- backend capability/health contract;
- fail-closed missing-tenant and authority behavior.

Forbidden:
- live DB connections;
- schema mutation;
- production cutover.

## Lane B — Migration / Discovery

Branch: `agent/data-cloud-migration-v1`
Preferred builder: Pi
Verifier: Empire Coder / Swarm

Owned paths:
- `empire_os/data_cloud_migration.py`
- `empire_os/data_cloud_discovery.py`
- `tests/test_data_cloud_migration.py`
- `tests/test_data_cloud_discovery.py`
- `docs/EMPIRE_DATA_CLOUD_MIGRATION.md`

Deliver:
- repository scan for direct Supabase dependencies;
- migration inventory model;
- schema/table dependency classification;
- cutover readiness state machine;
- verification manifest;
- rollback manifest;
- no data transfer yet.

Forbidden:
- dumping production data;
- writes to either canonical backend;
- bypassing current 402 containment.

## Lane C — Reliability / HA / Backup

Branch: `agent/data-cloud-reliability-v1`
Preferred builder: Hermes
Verifier: Swarm V6

Owned paths:
- `empire_os/data_cloud_reliability.py`
- `empire_os/data_cloud_topology.py`
- `tests/test_data_cloud_reliability.py`
- `tests/test_data_cloud_topology.py`
- `deploy/systemd/empire-data-cloud-*.service`
- `docs/EMPIRE_DATA_CLOUD_RELIABILITY.md`

Deliver:
- health/topology model;
- primary/replica/DR roles;
- replication-lag policy;
- backup/PITR readiness contract;
- restore-verification state;
- Reliability Agent integration contract;
- no automatic destructive repair.

Forbidden:
- installing PostgreSQL;
- changing systemd live state;
- production failover.

## Lane D — API / Control Plane

Branch: `agent/data-cloud-api-v1`
Preferred builder: Pi
Verifier: Empire Coder / Swarm

Owned paths:
- `empire_os/data_cloud_api.py`
- `empire_os/data_cloud_control_plane.py`
- `tests/test_data_cloud_api.py`
- `tests/test_data_cloud_control_plane.py`
- `docs/EMPIRE_DATA_CLOUD_API.md`

Deliver:
- private-first versioned API contracts;
- projects/tenants/service identities;
- reserved REST/GraphQL/RPC/vector/events/AI/MCP surfaces;
- OpenAPI-ready metadata;
- external/public exposure false by default;
- quota/metering hooks.

Forbidden:
- public deployment;
- raw SQL endpoint;
- service-role secret exposure.

## Lane E — Tenancy / Security

Branch: `agent/data-cloud-security-v1`
Preferred builder: Empire Coder
Verifier: Swarm V6

Owned paths:
- `empire_os/data_cloud_security.py`
- `empire_os/data_cloud_tenancy.py`
- `tests/test_data_cloud_security.py`
- `tests/test_data_cloud_tenancy.py`
- `docs/EMPIRE_DATA_CLOUD_SECURITY.md`

Deliver:
- authenticated tenant context contract;
- service identity/capability model;
- least-privilege role plan;
- cross-tenant fail-closed policy;
- secrets policy;
- audit identity;
- destructive-operation founder gate.

Forbidden:
- production role creation;
- secret generation/storage;
- disabling RLS/security.

## Integration lane

Branch: `feature/empire-data-cloud-v1`
Owner: architecture/integration only.

Integration responsibilities:
- review each lane against architecture;
- resolve interfaces centrally;
- no blind merges;
- run focused lane tests;
- run combined regression;
- inspect diff;
- verify no direct authority expansion;
- create server discovery plan;
- only then ask founder to run a tiny live-readiness command.

## Promotion gates

### Foundation gate
- architecture contract present;
- all five lanes pass isolated tests;
- combined tests pass;
- Control Fabric component registered;
- no live mutations.

### Infrastructure gate
- server capacity discovered;
- PostgreSQL installation plan verified;
- storage/backups target defined;
- private networking defined;
- restore strategy defined.

### Migration gate
- dependency inventory complete;
- schema inventory complete;
- migration verifier complete;
- rollback proof designed;
- Supabase remains canonical.

### Cutover gate
Requires explicit founder approval and live evidence. No agent can grant it.
