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
- SHA256 `32d4c5c680b9be8021422c9173f662175ae42b1eaef1fb82205c06e1a3684e53`.
- Non-login, non-superuser function owner; metering role is initially **NOLOGIN** and has no direct table SELECT; scoped function EXECUTE only. Qualified DBA must independently accept the exact DDL, provision a separate securely held LOGIN/credential and confirm `session_user` from the customer API's production DB pool. Synthetic test role switching is not a production credential.
- Original customer API candidate archive SHA256 `718e752945abd27a20ca28f168f8e20e3b7fe0011151a1a270af76cd0c090ff5`; original API package must be provided to the original owner release through hash-pinned import staging, not recreated from mocks.
- Separate Data Cloud signing issuer/private key custody and pinned public verifier remain pending genuine production owner configuration; no CRM signing-key reuse.

## Shortest remaining production release sequence
1. **Original recovery owner** proves physical pgBackRest November backup copy in a genuinely separate off-host location, independently restores it with the correct key and PostgreSQL version, confirms original system-id/heap/index check, records a hash-pinned off-host receipt. An off-host *logical* ciphertext is not substitute. Never export encryption keys to the repo or GitHub.
2. **Original EmpireDB DBA** reviews exact SQL hash and local/off-host DR receipts, owner/ACL/search_path/role absence, current DB collision and migration lock; provides independently attributable DBA acceptance or explicit HOLD. No unilateral self-attestation.
3. **Original public gateway / CRM issuer owner** reconciles shared dirty production files and owner lease, pins exact route-overlay preimage, takes protected rollback and registers original candidate route module. Mount issuer only in protected issuer service and public-key-only verifier only in existing port 80 gateway. No new services/platforms. All database and auth preflight gates must pass before a service change.
4. Operate one authenticated, cost-capped genuine founder request with two independent tokens (CRM-verified Data Cloud session plus metered API key), inspect SQL reservation and tenant-bound usage. Verify unauthenticated 401 and held 403, idempotency 409, capped 429, provider-rights 503. Search/crawl, unauthorised source resale, paid provider requests, third-party customers and billing stay OFF.
5. Verify served origin route and regression of unrelated gateways, return `LIVE_FOUNDER_CANARY_VERIFIED` only with real receipts; rollback atomically on any unexpected result.

**Current decision:** `PRODUCTION_HOLD_OFFHOST_PHYSICAL_DR_AND_DBA_ACCEPTANCE`. Local restore PASS does not grant release authority. The founder's approval is preserved and exact implementation is staged.
