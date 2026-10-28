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

## V11 real-driver signed order-to-founder proof — isolated only

New `tests/test_crm_v11_scoped_reader_pg18_end_to_end.py` executes the **actual**
`crm_scoped_lineage_reader.review_signed_scoped_lineage` with a real
`psycopg` connection, real PostgreSQL 18 NOINHERIT tenant-bound logins,
the actual held `SECURITY DEFINER` RPC installed **only inside the ephemeral
fixture**, and a cryptographically signed synthetic CRM bearer. It injects
ONLY the existing independently maintained suppression-reader
`CRM_LOGIN_AUTHORITY_SQL` test contract into the unpublished transport guard;
production transport source remains untouched.

The tests prove a correctly signed tenant A can retrieve its fixture order;
tenant B and wrong database-session identity cannot; missing or revoked
session_user tenant bindings immediately fail closed. Another isolated test
uses a **test-only protected CRM view** to pass that signed order through the
**unchanged V11 bridge**, its original CRM view transport, and the redacted
Founder case DTO. The fixture status intentionally says `paid`, but V11
still shows `BUYER_ACCEPTANCE` as its first missing verified handoff,
`revenue_recognized_here=false`, and
`independent_evidence_attested_here=false`.

No production signed bearer, real order, account password, production DBA
catalogue grant, CRM owner release, real payment or live founder route was
involved. The original owner-held SQL and unpublished login changes remain
separate, and this does not automatically qualify a production release.


## Original first-party CRM authenticated order HTTP route — review candidate

The isolated PR now includes `empire_os/crm_revenue_case_private_api.py` and
an **optional, default-disabled** registration in the existing
`revenue_crm_pilot_activation.build_pilot_routers`. It does not start a
second FastAPI app, database login or gateway. It preserves the original
two-router private CRM pilot service and its 127.0.0.1 boundary.

The only new endpoint, if the **original CRM service owner** explicitly
sets `EMPIRE_CRM_V11_ORDER_READ_ENABLED=1` in that existing private service
configuration and authorises a guarded deployment, is:

`GET /v1/revenue-crm/prospects/{prospect_id}/opportunities/{opportunity_id}/orders/{order_id}/revenue-case`

It requires the exact original Ed25519-signed, active-membership CRM bearer,
the original authenticated read resolver and the matching dedicated per-
tenant login and original tenant-scoped RPC. The handler also verifies
the exact tenant/order in the V11 result and strictly validates a
field-allowlisted Pydantic model; it returns only the redacted
`founder_case_view`, not the original order, tenant UUID, token,
DSN, financial data or unverified receipts. It uses no-store headers,
cannot recognise money, sends no mail and writes no tables.

In the absence of the flag, the endpoint is not registered (404). Without
valid member authentication it returns 401. On missing/held RPC, scope
mismatch, tampering or unreadable evidence it fails closed with a redacted
503. The original private service itself still remains off the public
internet, and its existing security middleware applies.

`tests/test_crm_v11_private_order_api_pg18.py` covers actual HTTP
access over the original CRM router, signed synthetic token, real psycopg
and ephemeral PostgreSQL exact-order RPC; an order with test
`fulfilment_state='paid'` still yields **no verified revenue**.
It also covers default-off and exact opt-in installation through the
original private pilot config, private FastAPI service startup, rejection
of unauthenticated and cross-tenant attempts, and rejection of a payload
with unexpected secret fields. All original account and database test
credentials are synthetic and disposable.

**Release remains HELD**, separately requiring the original CRM owner's
uncommitted transport guard release, the original DBA's authorised
exact-order SQL security review/deployment, a genuine existing
authenticated tenant/order read, and the existing founder-console owner's
private server-side session binding. Do not attach this response to the
general unauthenticated Founder Overview API or enable the opt-in as a
substitute for any of those gates.


## V11 founder-only membership correction — 27 October

An additional security review of the optional V11 HTTP endpoint found that
the original `SignedCrmTenantVerifier` intentionally allows any tenant member
with `read` permission, including ordinary viewers. The order-specific
`founder_case_view` is an internal founder operations display: generic CRM
read membership MUST NOT be sufficient authority for this panel.

The opt-in V11 route now also verifies an active **owner** membership through
the *original* first-party CRM `verified_membership` lookup. It first
authenticates the signed original Ed25519 token, then extracts only the
already signature-validated subject and resolves that same subject and tenant
against the original active membership reader. The membership must have
exact user and tenant binding, role `owner`, and original `admin` authority.
Unsupported, revoked, viewer, analyst, operator, and admin memberships are
refused; caller-controlled `X-Role` or `X-Owner` is never trusted.
Missing original membership authority prevents route construction.

Disposable PostgreSQL/HTTP tests include signed positive owner access and
negative viewer, analyst, operator, and admin access, including spoofed
owner headers. This hardening is **review branch only**; the live CRM owner
must still approve integration with the actual founder's owner membership,
publish their transport guard, and obtain the independent DBA SQL release.
No new token issuer, login, DB role, Founder Overview exposure, or outbound
permission is introduced.


## Original dedicated-login authority: isolated privilege-mutation proof

The V11 original signed-order reader now has direct disposable PostgreSQL 18
negative tests in `tests/test_crm_v11_scoped_reader_pg18_end_to_end.py`
covering a *real* `session_user` and original restricted SQL query.

A previously valid signed owner order is denied after each one of these
**fixture-only** login changes: `INHERIT`, `BYPASSRLS`, `CREATEDB`,
revoke the required `empire_revenue_crm_reader` membership, or grant
another unrelated role. The test reverts each temporary privilege change
and verifies the legitimate signed order read is restored.

This independently tests the attestation semantics the original CRM
transport owner is preparing, but **does not publish or replace** that
owner's dirty production transport. The original DBA must still verify
the real designated tenant login grants and production RPC catalogue
with owner authority. No production role was changed or queried.
