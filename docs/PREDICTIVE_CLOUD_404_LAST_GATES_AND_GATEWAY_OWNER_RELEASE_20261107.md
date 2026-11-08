# Predictive Cloud protected gateway owner release — 7 November 2026 (22:xx UTC)

**Founder conditional approval already held. Do NOT request it again.** Complete issue #156 using the existing EmpireDB DBA/recovery and public-gateway owner lanes. Never invent a second gateway/release process.

## Authenticated source and recovery proof
- Exact fresh pgBackRest physical full backup: `20261107-182029F`, finished `2026-11-07T18:20:39Z`.
- Original DR worktree commit `681ee7399`, verified original receipt SHA256 `e7dc1eef721c52730f21b2327e1ad30e03ddb1408933824edec3eedc398b3ada`.
- Receipt `docs/architecture/EMPIREDB_NOV7_ISOLATED_RESTORE_V3_ACTUAL_RESULT.json`: `LOCAL_FRESH_ISOLATED_PHYSICAL_RESTORE_VERIFIED`, PostgreSQL 18 started and promoted on isolated same host, 101 restored user relations, 3 inspected nonempty source tables, 0 invalid indexes, `pg_amcheck --heapallindexed` PASS, isolated cluster stopped and removed, production remained active.
- **Not proven:** loss-of-server recovery, off-host custody and independent off-host *physical* restoration. Receipt explicitly sets `offhost_physical_restore_verified=false` and `server_loss_dr_ready=false`. Existing readable `/etc/empiredb-backup-public/verified-offsite/` contains only an older **October encrypted logical** receipt, not the 7 November physical backup.
- The remote ApexEngine currently reports only C: and D: filesystems; the old USB D: was previously reported as needing repair, so do not treat its presence or encrypted logical checksum as verified physical DR.
- Neither the original owner DBA approval for this exact DDL nor production credential/role custody was evidenced in the read-only audit. No unprivileged operator can self-sign DBA approval.

## Actual live gateway
- `empire-public-gateway.service` runs `linkedin_browser_ui_entrypoint:app` at `127.0.0.1:80`, with protected root-installed additive owner overlays (LinkedIn OAuth / browser UI, brokerage, social).
- The CRM pilot issuer at `127.0.0.1:8783` likewise uses a pinned owner overlay.
- Real GET `/v1/data/usage` on ports 80 and 8783: **404**. Search Intelligence port 8771 also gives 404 for this customer API, and is **not** the legitimate customer gateway.
- Current canonical production DB lacks both `empire_data_cloud_api` schema and the dedicated metering-role login.
- Shared production gateway/hub/Search Fabric files remain dirty and owned by other streams; don't overwrite them.

## New surgical source hardening
- Existing Data Cloud authorization middleware now intercepts **only** the three declared customer routes, not other owners' `/v1/data/*` paths. The issuer exchange route retains no-store caching.
- The guarded customer route assembly rejects attaching to an already started FastAPI host before mutating routes. It attaches the public verifier before appending the exactly three original customer endpoints; it refuses duplicates and unexpected candidate paths.
- Release evidence requirements now include genuine fresh isolated restore, **off-host physical recovery**, independent DBA SQL/ACL acceptance, **the original gateway rollback**, founder-only identity, and disabled billing/paid provider calls.
- All relevant owner feature, CRM, route, original API archive staging, SQL-hash and PPIR tests: **110/110 PASS** (two nonblocking warnings); local worktree only. Test fixture asserting all release flags is **synthetic** and cannot substitute for independent owner receipts.

## Exact prepared SQL
- Review-only path `docs/release_candidates/empire_data_cloud_meter_pg18_review_only_20261107.sql`.
- SHA256 `d20b0980c5e2d1348e7e0ecdcfa3fe021fc82b6bd1983750f37b2bf9b9ad8393`.
- Non-login, non-superuser function owner; metering role is initially **NOLOGIN** and has no direct table SELECT; scoped function EXECUTE only. Qualified DBA must independently accept the exact DDL, provision a separate securely held LOGIN/credential and confirm `session_user` from the customer API's production DB pool. Synthetic test role switching is not a production credential.
- Original customer API candidate archive SHA256 `718e752945abd27a20ca28f168f8e20e3b7fe0011151a1a270af76cd0c090ff5`; original API package must be provided to the original owner release through hash-pinned import staging, not recreated from mocks.
- Separate Data Cloud signing issuer/private key custody and pinned public verifier remain pending genuine production owner configuration; no CRM signing-key reuse.

## Shortest remaining production release sequence
1. **Original recovery owner** proves physical pgBackRest November backup copy in a genuinely separate off-host location, independently restores it with the correct key and PostgreSQL version, confirms original system-id/heap/index check, records a hash-pinned off-host receipt. An off-host *logical* ciphertext is not substitute. Never export encryption keys to the repo or GitHub.
2. **Original EmpireDB DBA** reviews exact SQL hash and local/off-host DR receipts, owner/ACL/search_path/role absence, current DB collision and migration lock; provides independently attributable DBA acceptance or explicit HOLD. No unilateral self-attestation.
3. **Original public gateway / CRM issuer owner** reconciles shared dirty production files and owner lease, pins exact route-overlay preimage, takes protected rollback and registers original candidate route module. Mount issuer only in protected issuer service and public-key-only verifier only in existing port 80 gateway. No new services/platforms. All database and auth preflight gates must pass before a service change.
4. Operate one authenticated, cost-capped genuine founder request with two independent tokens (CRM-verified Data Cloud session plus metered API key), inspect SQL reservation and tenant-bound usage. Verify unauthenticated 401 and held 403, idempotency 409, capped 429, provider-rights 503. Search/crawl, unauthorised source resale, paid provider requests, third-party customers and billing stay OFF.
5. Verify served origin route and regression of unrelated gateways, return `LIVE_FOUNDER_CANARY_VERIFIED` only with real receipts; rollback atomically on any unexpected result.

## Founder scope amendment — 7 November (usage-only pilot)
The founder explicitly approved moving **off-host disaster recovery to a post-pilot milestone** while retaining DBA acceptance, verified local restore/rollback, founder-only identity and live HTTP checks. This supersedes the off-host prerequisite **only** for the internal `GET /v1/data/usage` pilot. Commercial/customer API, external search, site audits, billing and automated paid provider calls remain OFF and continue to require their own full approvals.

The existing route assembly now accepts `usage_only=True`, which copies **only the original usage endpoint** from the exact three-route candidate. It validates `USAGE_PILOT_REQUIREMENTS` without falsely marking offhost recovery, source-rights approval or the live founder canary complete. It does **not** insert search or site-audit routes, and preserves unrelated owner gateway routes.

**Pilot remaining real blockers:** independent DBA acceptance and approved provisioning of exact SQL and least-privileged metering LOGIN; current live protected issuer/public-key verifier and entitled founder account; owner mutation lease and original gateway rollback. The original candidate archive must be hash-staged for the serving original owner; do not substitute the synthetic test endpoint.

**Current decision:** `FOUNDER_USAGE_PILOT_APPROVED_BUT_DBA_AND_LIVE_GATEWAY_INTEGRATION_PENDING`. Local restore PASS. Full commercial release remains held on distinct off-host/rights/customer terms. Do not imply live 404 fixed without actual served HTTP evidence.

## DBA review defect resolved in this existing candidate (7 Nov late review)

The original draft SQL `32d4c5c6...` accidentally granted the founder pilot runtime role permission to execute write-capable `reserve` and `settle` functions. The independently logged DBA *pre-review* correctly flagged this. The previous draft SHA is **superseded**, not accepted or applied.

**Current exact SQL SHA256:** `d20b0980c5e2d1348e7e0ecdcfa3fe021fc82b6bd1983750f37b2bf9b9ad8393`. Its existing founder-only runtime role has `USAGE` on schema and `EXECUTE` on `authenticate` + `usage_snapshot` only; writer functions are explicitly denied. Full commercial write operations will need separate original-owner DBA role review. This is a revision of the existing SQL candidate, **not** a new production migration.

**Verified real disposable PostgreSQL 18 (UTF8 matching canonical EmpireDB):**
- The candidate compiled and the direct SQL privileges check proved write-function EXECUTE denied while two read-functions remained permitted.
- Full isolated quota/host/cost-integrity tests passed; 3 concurrent reservations admitted and 17 rejected under the cap, run under disposable DBA-only context, **not** the founder runtime account.
- The **original** API handler from the hash-pinned source package was mounted through the existing founder session verifier; connected to an actual disposable PostgreSQL 18 socket using the dedicated role temporarily enabled as LOGIN **only in the disposable cluster**.
- Observed HTTP 200 for two independent credentials and a genuine SQL-backed usage snapshot; 401 with incomplete/bad credentials, 403 when founder entitlement was revoked; unrelated route remained reachable; search and audit routes were not mounted; direct DB write-function call returned permission denied.
- Disposable PostgreSQL instance was stopped and removed on exit. **0 production DB connections, 0 production SQL, 0 production gateway restarts, 0 provider calls, 0 billing**.
- Initial disposable cluster defaulted to `SQL_ASCII` and caused a 503 role-proof mismatch through byte-valued text; confirmed production DB uses `UTF8`, then reran with `initdb -E UTF8` and passed. The original adapter was **not rewritten** to hide a test-environment mismatch.

**Exact remaining owner decisions:** independent DBA accepts new SQL digest and production credential/rollback; actual protected CRM issuer and public gateway owner activates and proves live HTTP result. The founder already approved internal usage-only pilot; off-host physical recovery remains a post-pilot milestone. No additional founder approval or new platform is needed.

## Founder-approved bounded activation — existing services only

Founder explicitly approved private credential provisioning and guarded restart of the existing CRM issuer and public gateway. The migration has already been independently verified on production PostgreSQL 18.6; **DO NOT rerun the DDL**. Original production metering privileges are read-only: `authenticate` and `usage_snapshot` permitted, `reserve` and `settle` denied.

An additive, versioned operator command is staged in this SAME review PR:
`scripts/activate_data_cloud_founder_usage_20261107.py`.
It verifies the exact reviewed source/restore receipts, existing single owner identity, empty new metering tables, unmodified owner systemd overlay chain, current CRM private membership configuration, and both services' original health. On successful checks it provisions only a separate randomly generated API key and least-privilege metering LOGIN, fresh separate Data Cloud Ed25519 signer via **private CRM systemd LoadCredential**, approved founder tenant, and **only** the original customer GET `/v1/data/usage` in the existing port-80 app; existing private CRM gets only POST `/v1/data/auth/exchange`. No new service, account system, searching, site audit, billing or paid provider. The existing runtime package, base entrypoint and other owners' drop-ins are preserved.

The public process receives only the separate Data Cloud public verification key and restricted meter DB credential, **not** the private Data Cloud signing key. The founder's existing CRM login/membership reader remains the identity authority. The installer stores secrets in private OS paths, never the repository or output. It installs only additive owner-scoped versioned systemd overlays. On any failure it removes only those two new overlays, restarts the original two services and disables the pilot meter login/key/tenant. The schema stays intact.

A real live **operator-signed loopback canary** is tested with genuine PostgreSQL metering and real founder membership, but **is not a substitute for independently verifying the founder's actual CRM login-to-exchange flow**. That final first-party login test remains required before calling the overall pilot verified. The original web route and HTTP 200 are not claimed live until the installer produces its private release receipt. Off-host physical DR remains a post-pilot milestone.

**Execution:** run the installed exact reviewed script once as the authorised root operator with `--apply-founder-approved`. Its `--inspect-read-only` and `--rollback-founder-approved` modes share the same current service architecture. Report only the redacted receipt and live origin status; never paste API keys, signers, passwords, tokens or DSNs into chat.

## Founder-only activation rollback and exact resume (7 Nov, ~23:55 UTC)

The first founder-authorised operator execution created the **single** original founder tenant and API key, then failed **before gateway overlays were retained**. The failure triggered the protective rollback: `empire_data_cloud_meter_login` remains `NOLOGIN`, the tenant is inactive/held, its key inactive, both original CRM/public services restored and healthy HTTP 200, and public GET `/v1/data/usage` remains 404. The data migration is complete and MUST NOT be rerun. The original frozen package, private signing key, API key and private config remain preserved; do not generate duplicates or manually delete them.

**Concrete cause:** the original activation's `psycopg.connect(host="/var/run/postgresql", password=...)` cannot authenticate this new login because canonical production `pg_hba_file_rules` use `local all all peer` after earlier role-specific entries. The same EmpireDB listens at 127.0.0.1 and has existing `host 127.0.0.1/32 all scram-sha-256`; loopback password transport requires no PostgreSQL configuration change or restart.

**Recovery modification to the same installer:** switch only new Data Cloud restricted metering connections to `127.0.0.1:5432`, preserve existing CRM membership socket transport, add `--resume-preflight-read-only` (no mutation) and `--resume-founder-approved` (reuse exactly the previously stored founder tenant, key, Ed25519 signer, private config and frozen customer API). Preflight checks source hash, existing SCRAM listener, old version-pinned staged wrapper hash, original code provenance, file permissions, owner membership/CRM binding, matching Data Cloud signing public key, existing disabled key and held tenant, missing overlays and absence of any completed activation receipt. No duplicate INSERT/CREATE or migration.

The recovery updates the single frozen public gateway wrapper to the verified loopback transport, preserving original bytes in root-only backup; re-enables only the matching founder tenant/key/role; verifies genuine password authentication and SQL-backed read-only usage; writes pinned release evidence, adds only original gateway and CRM additive overlays, and confirms both original services, auth denials and live real-data usage canary. If any step fails, rollback *first* disables only this founder tenant/key and DB login, then removes only the new overlays. It does not restart unrelated services when a failure occurs before overlay installation. A previously verified release-evidence file can be safely reused only if its exact service preimage hashes and requirements match.

**Release truth:** source tested, recovery code staged for authorised SSH, not yet executed. Await actual read-only preflight then one bounded resume. A valid root-signed transport canary is not a genuine founder CRM login-to-exchange test; that still requires separate live proof before claiming complete founder customer workflow.

## Exact production database CONNECT denial and correction (8 Nov, 00:09 UTC)

The second founder-authorised bounded resume returned the actual PostgreSQL error: `FATAL: permission denied for database "empiredb" — User does not have CONNECT privilege`. This is an incomplete database-access grant in the Data Cloud installer, **not** an invalid password or a requirement for a new migration.

Independent read-only `pg_database.datacl` verified EmpireDB grants explicit `CONNECT` to individually approved runtime roles; `PUBLIC` is not granted database access. The existing `empire_data_cloud_meter_login` had `CONNECT=false`, `CREATE=false`, `TEMPORARY=false`; Data Cloud schema `USAGE=true`; only `authenticate` and `usage_snapshot` function EXECUTE true. The source SQL had created its restricted NOLOGIN role correctly, but its later private credential activation missed the database-level `CONNECT` privilege.

The approved founder-only resume now adds exactly `GRANT CONNECT ON DATABASE empiredb TO empire_data_cloud_meter_login` to the **same** existing transaction that re-enables the held single founder tenant/key and LOGIN. Before attempting psycopg password login, it verifies effective privilege tuple `CONNECT=true, CREATE=false, TEMPORARY=false`. This grant is also applied in any future initial founder-only admission (without changing existing migrations). Fail-closed rollback disables only the founder tenant/key, sets the meter role NOLOGIN and `REVOKE CONNECT ON DATABASE empiredb FROM empire_data_cloud_meter_login`, preserving other roles and services. Preflight requires tuple `false,false,false` prior to resume. No schema migration, DB server restart, broadened roles, source-provider activation or billing.

After the failed resume, read-only production checks confirm the metering role returned to NOLOGIN, the founder tenant remains inactive/held and founder API key inactive, no release evidence or systemd overlays persisted, both original public and private CRM services healthy HTTP 200, and public usage route HTTP 404. No duplicate credentials or tenants were introduced. All source-level regression tests including negative privilege combinations and rollback hold pass. A disposable runtime TCP regression command was restricted by connected remote tooling; do not claim a fresh independent production connection until actual founder SSH runs the corrected resume.

**Pending:** operator-run exact pinned resumed release, verify genuine SQL-backed HTTP and private issuer health; after that separately verify real founder CRM login-to-token-exchange (operator-signed canary alone is insufficient).
