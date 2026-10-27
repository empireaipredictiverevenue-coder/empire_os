# EmpireOS V11 — Original CRM owner security acceptance evidence

**Scope:** one original CRM/EmpireDB tenant-scoped order, original Founder Console.
**Status:** HOLD_OWNER_RELEASE. This note does not grant deployment or access.

## Verified in this session

- The production first-party CRM pilot service is active and its private loopback health reports read-only pilot authority. This is only service health, not order evidence.
- Unauthenticated GETs to the private pilot's original prospects and buyers endpoints each returned HTTP 401. This does not replace owner-approved session / access-control testing.
- Existing V11/CRM bridge tests plus the actual HELD RPC executed inside disposable PostgreSQL 18: **96 tests passed**, with one Starlette/anyio dependency deprecation warning. The isolated tests verify same-tenant buyer/event/order continuity and negative cases including cross-tenant access, missing buyer, conflicting identity and revoked tenant binding.
- Original production checkout (not review worktree): **69 original Revenue CRM transport and signed-auth tests passed**, one dependency warning. The CRM owner still has uncommitted `empire_os/revenue_crm_transport.py` login-attestation changes. No edits were made to that file.
- Existing V11 review-branch redacted founder progress component remains prepared, independently type-checked, and not wired to any public or unauthenticated live route.

## Not verified, and still held

- The exact RPC from `CRM_SCOPED_LINEAGE_RPC_HELD_20261026.sql` has NOT been approved or installed by this workstream. No production database catalogue or grant attestation was obtained; the attempted administrative read was denied by the remote-command policy. Do not work around that denial.
- The metadata-only owner catalogue audit in `CRM_V11_OWNER_RELEASE_CATALOG_AUDIT_20261027.sql` is now **validated in an isolated PostgreSQL 18 fixture** with `tests/test_crm_v11_catalog_readonly_fixture.py`. The first test exposed a concrete PostgreSQL 18 representation mismatch: `SET search_path = ''` is stored as `search_path=""`, not exclusively `search_path=`. Both the audit and the original scoped-reader provenance predicate were repaired to accept only these explicit empty-path representations. A negative fixture test confirms `search_path=public` returns `catalog_preflight_passed=false`. **Production catalogue read and release remain HELD** until the original DBA independently authorises and runs the check; this fixture does not grant founder approval or prove an actual order.
- No authorised signed founder tenant session, exact order/prospect/opportunity triplet, independently accepted buyer terms, confirmed fulfilment, signed payable contract, BSC finality, reversal census, or actual revenue payment was observed.
- The existing Founder Console has no new live V11 order detail route or display release. No customer data was read or simulated to claim this milestone.

## Actionable, single-owner release handoff

1. Original CRM transport owner publishes/tests their own dedicated-login attestation before any PR merge. Do not replace their uncommitted file with the older review branch.
2. Original CRM/DBA security owner independently reviews the HELD exact-order SQL, verifies security-definer owner, fixed empty search path, explicit restricted EXECUTE and no PUBLIC/raw-table grants in a controlled environment, then approves or rejects its deployment with a rollback record.
3. Original first-party CRM owner uses a genuine member-authenticated signed tenant session through the dedicated reader. Test one **pre-existing** exact order, buyer, prospect and opportunity ID through the approved RPC. Absence or mismatch stays UNKNOWN; do not synthesize an order.
4. Existing Founder API owner exposes only the prebuilt redacted `founder_case_view` through a properly session-scoped server route; existing console owner mounts the staged view after private access tests.
5. RevenueRecognition and FulfilmentOperations attach independent real receipts. A reported CRM 'paid'/'settled' field is not proof of funds, margin or learning rights.

**Do not** start another CRM, worker, database, browser login bypass, payment path or duplicate console. PR #119 stays a review candidate.
