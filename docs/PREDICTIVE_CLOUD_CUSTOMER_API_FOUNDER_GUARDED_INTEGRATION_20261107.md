# Predictive Cloud Customer API — Founder-only guarded integration

7 November 2026. Owner worktree `predictive_cloud_founder_session_20261107`.

## Implemented and tested
- Separate Ed25519 issuer/verifier for Data Cloud. Existing CRM verifier validates the original signed CRM bearer; founder owner membership and separate Data Cloud entitlement are rechecked.
- Data Cloud JWT: issuer `empire-os`, audience `empire-data-cloud`, scope `data:read`, five-minute TTL. CRM-only tokens cannot be used as Data Cloud bearer.
- Public gateway verifier has **no private signing key, CRM verifier or token-minting method**.
- Typed trusted principal injected into ASGI state, not inferred from caller-controlled headers.
- Additive gateway route-assembly factory accepts only `GET /v1/data/usage`, `POST /v1/data/search`, `POST /v1/data/site-audits` from the **original** customer API, never a second API implementation.
- Rejects insufficient independent preflight, unknown candidate paths and route collisions before mutating host.
- Tests on the isolated worktree prove signed founder token, membership revocation, no public token issuance, backward compatibility with CRM security tests and no mutation on preflight hold.

## Explicit release blockers (not falsely resolved)
1. Bring the **original customer API candidate** `empire_data_cloud_gateway_empiredb_candidate_20261107.zip` through the existing EmpireOS release-owner process. Do not rebuild it. Pin and review its source and manifest.
2. **Canonicalise principal contract:** its `gateway_attestation.py` must import/re-export `VerifiedPrincipal` and `verify_gateway_attestation` from `empire_os.predictive_cloud_gateway_attestation`. Otherwise two identical-looking but different Python classes will cause 401. Add a test against the actual candidate route closure and real signed Data Cloud session.
3. The original candidate SQL and restricted `empire_data_cloud_meter_login` passed isolated PostgreSQL 18, including 20-way concurrent quota enforcement, but **do not exist in canonical production EmpireDB yet**. DBA must inspect and apply only after separate protected migration approval and rollback proof. No automatic schema application.
4. The independent entitlement callback must read live EmpireDB founder membership and a **separate Data Cloud pilot entitlement**. The callback must fail closed on missing permission. The CRM token's `crm:read` alone never permits Data Cloud access.
5. Restricted signing-key custody: mount `DataCloudFounderAuthority` only on the existing protected issuer service after confirming its service identity. Mount `DataCloudPublicVerifier` only on the existing gateway; never expose the issuer on the public gateway.
6. Existing Scrapling/Decodo/third-party research remains **held from customer data redistribution** without independent licence evidence. Site audit must remain 503 until HTTPS public-IP/redirect/DNS rebinding/robots/consent and explicit host allowlists are verified. Recording an old source observation is not a fresh live crawl.
7. Run **one** genuine existing-founder authenticated, independently cost-capped transaction, obtain SQL reserve/settle receipt, provider source timestamp, actual provider cost evidence or explicit unverified-cost status, and 401/403/409/429/503 negative canaries. Prove rollback before enabling any external tenant. Finance and billing remain OFF.

## Existing production observations
- Search Intelligence `:8771/v1/search/health` returns HTTP 200.
- Customer Data Cloud `:8771/v1/data/usage` returns HTTP 404.
- `/srv/empire_os/empire_os/public_gateway.py`, `hub.py`, `search_intelligence/api.py` and `search_fabric/search.py` remain dirty due to other owners. This owner branch does **not** overwrite them.
- The public gateway is a chain of owner-managed ASGI entrypoints; **do not** point the customer API at Search Intelligence on port 8771 just to eliminate 404.

## Approval boundary
Founder authorised solving the customer 404. This document is *not* approval for protected database migration, live signing-key rollout, service restart, external customer access, paid provider calls or billing. These require their individual verified release gates.

## Verification command
```bash
cd /home/ubuntu/empire_worktrees/predictive_cloud_founder_session_20261107
PYTHONDONTWRITEBYTECODE=1 /srv/empire_os/.venv/bin/python -B -m pytest -p no:cacheprovider -q \
 tests/test_predictive_cloud_founder_session_20261107.py \
 tests/test_predictive_cloud_route_assembly_20261107.py \
 tests/test_revenue_crm_signed_auth.py \
 tests/test_revenue_crm_authenticated_router.py \
 tests/test_crm_membership_authority_ephemeral.py
```
