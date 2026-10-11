# Founder CRM post-redemption read-only recovery — 11 October 2026

## Production outcome and no-repeat gate

The founder ran the approved, authenticated loopback-only first-login action. Real service logs verified:
- `POST /v1/revenue-crm/auth/accept-invite` HTTP 200.
- `POST /v1/revenue-crm/auth/login` HTTP 200.
- `GET /v1/revenue-crm/prospects?limit=1` HTTP 503, about four seconds later.
- `GET /v1/revenue-crm/buyers?limit=1` HTTP 200.

The canonical founder account is `active`, password initialized, invitation redeemed, token invalidated. Never rerun invitation provisioning or redemption; do not regenerate database passwords or the JWT signer.

Independent live first-party account-bound membership checks passed. The dedicated buyers reader passed. The static prospects view has a sequential scan and sort with an estimated plan cost around 19,111, and a read-only query timed at 2.1 seconds, with evidence that the 4-second database timeout can cause intermittent 503. No data, customer rows, JWTs or credentials were printed.

## Minimal patch

`empire_os/revenue_crm_transport.py`: use **8000 ms for only two static prospect SQL constants** `PROSPECT_LIST_SQL` and `PROSPECT_ONE_SQL`. Keep buyer SQL budget **4000 ms**, tenant proof, read-only transaction, and fail-closed redaction unchanged. No SQL, privilege, schema, RLS, DB roles, indexes or runtime service definition changes.

`scripts/redeem_founder_crm_invitation_local.py`: add `--verify-existing-login`, using interactive masked password entry and the existing first-party login endpoint, printing only login success and numerical HTTP codes for authenticated prospect and buyer reads. Does **not** read invitation token or call the invitation redemption route. HTTP local GET timeout is 12 seconds so its bound exceeds the 8-second SQL budget. No public ingress or marketing.

Tests include prospect/buyer-specific timeout selection, existing tenant and session isolation behavior, refused unapproved requests, secret-safe login recheck, and original first-invite behavior preserved.

The main repository contains pre-existing **uncommitted, unrelated CRM transport authority checks** from another agent. Preserve them untouched. Integrate only this small timeout hunk and tests into the existing shared checkout, without blanket committing other agents' diffs.

## Activation boundary

The code update alone does **not** update the already-running Uvicorn worker. Founder approval is required before restarting **only** `empire-revenue-crm-pilot.service`; never restart PostgreSQL, the founder dashboard, outbound or other agents' services.

After a separately authorised bounded restart, founder can enter the *existing* password (not the invitation token) in an interactive SSH session:

```bash
cd /srv/empire_os
./.venv/bin/python scripts/redeem_founder_crm_invitation_local.py --verify-existing-login
```

Success: `CRM_FOUNDER_EXISTING_LOGIN=PASSWORD_AUTHENTICATED`, `CRM_FOUNDER_PROSPECT_HTTP=200`, `CRM_FOUNDER_BUYER_HTTP=200`, `CRM_FOUNDER_SETUP=FIRST_PARTY_LOGIN_VERIFIED`. Anything else stays fail-closed. The local service remains bound exclusively to `127.0.0.1:8783`.

The immediate 8-second bounded mitigation is not a permanent database performance optimisation. Later query tuning is a separate reviewed task; do not block first founder login on a new migration.
