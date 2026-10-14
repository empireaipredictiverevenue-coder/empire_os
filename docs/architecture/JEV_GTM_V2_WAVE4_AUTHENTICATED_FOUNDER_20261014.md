# JEV GTM V2 — Wave 4: Authenticated Founder Research Boundary

Date: 2026-10-14
Branch: `feature/jev-gtm-v2-20261014`
Starting commit: `ae25e9fc`
Mode: OBSERVE; no production activation, service restart, new DB role, migration, outbound send, payment, or spend.

## Engineering objective

Connect the existing governed Economic Signal Fabric to an *optional*, tenant-restricted Founder Console research view without inventing buyers, widening database grants, exporting PII or exposing a route without independent founder authentication.

## Existing first-party contract inspected

- `migrations/empiredb/018_tenant_context_foundation.sql`: `public.empire_current_tenant_id()` resolves binding by **session_user**, not a request parameter or caller-defined GUC.
- `migrations/empiredb/039_tenant_economic_signal_reader.sql`: `public.empire_read_economic_signals(uuid,timestamptz)` grants execution to the existing `empiredb_tenant_reader` group, not the general app role. It is a tenant-bound, 24-hour observed Economic Signal Fabric source, not a buyer-intent inbox.
- `empire_os.economic_signal_reader.read_economic_signals` validates provenance, source family, tenant/entity/binding and exposes no send authority.
- `empire_os.jev_gtm_founder_review.build_jev_founder_economic_review` returns only economic signal family counts, an evidence fingerprint and truthful research status.
- `empire_os.founder_dashboard_service` is the existing loopback-only Founder Read API. No separate HTTP server or scheduler needed.

## Implemented, tested

### Existing-role PostgreSQL transport
`empire_os/jev_gtm_economic_transport.py`:

- Requires an explicitly supplied **dedicated tenant-bound, NOINHERIT login** and trusted expected tenant from the hosting founder service; no existing secrets or environment files are read automatically.
- Before any economic read: `SET TRANSACTION READ ONLY`, tight query timeouts, verify precisely the single existing reader-role membership, reject extra inherited/bypass/admin roles, `SET LOCAL ROLE empiredb_tenant_reader`, compare server-side `empire_current_tenant_id()` to the expected tenant.
- Existing economic bridge checks `SHOW transaction_read_only` before its canonical query.
- One canonical entity UUID per call; bounded economic read; no user-selected SQL or direct table scans.
- Returns only the prior no-PII founder summary. Database errors/credentials are sanitised.
- Does not provision database accounts or expose access to the public app.

### Founder Read API integration
`empire_os/founder_jev_api.py`, `empire_os/founder_dashboard_service.py`:

- Register `GET /v1/founder-jev/status` on the **existing** Founder Read API, not a new application/server.
- Status reports schema version, native Choice/Score/Noul compatibility evidence, unavailable live-data counts and explicit `production_activated=false`.
- **NO entity research route exists in the default service.** `GET /v1/founder-jev/research/{entity_id}` is registered by `create_founder_jev_router` only when the host injects BOTH a trusted reader and an independent server-side founder authorizer.
- The authorizer runs before any database read. Denial, errors or missing role evidence fail closed.
- Response must match the exact 23-field no-PII, OBSERVE-only founder review contract. Extra fields, new authority, contact clearance or artificial revenue claims produce 503 and no payload leakage.

### Regression cases

`tests/test_jev_gtm_economic_transport.py`: fake PostgreSQL sessions assert read-only transaction, exact reader-only membership, tenant-scope checks, bad-credential handling, denials before signal query, no DML, sanitised errors and end-to-end authenticated FastAPI route -> dedicated reader -> canonical economic reader -> no-PII view.

`tests/test_founder_jev_api.py`: default route inventory, truthful statuses, reader/auth pairing requirement, denied request no reader calls, authorizer exceptions, invalid UUID, unsafe response rejection and aggregate-only success.

All database cursors/tenant rows in tests are synthetic fixtures, not claims about live EmpireDB.

## Proof still required before activation

1. Independent, founder-approved configuration of a dedicated existing-role login and an authenticated founder authorization check in the loopback service. The current default has **no reader** and deliberately publishes no entity-level research.
2. Real live EmpireDB role/session/tenant readback and source rows. A previously attempted privileged aggregate probe was blocked by remote safety controls; do not bypass or guess counts.
3. Distinct tenant-bound canonical buyer contact and reply linkage evidence via existing CRM. The Economic Signal Fabric proves observations, not buyer interest or contact permission.
4. Independent representative real-label calibration of Choice, Score and Noul. The synthetic live Noul result was not persuasive enough to claim production decision readiness.
5. Founder UI presentation in the existing console, review workflow, production merge, deployment and release gauntlet; preserve concurrent website and Founder Console changes. No production merge is authorised in this commit.

Completion claim: **engineering integration with safe default behavior and mock-bound acceptance tests**, NOT production connection, live buyer access, or realized revenue.
