# Empire AI / EmpireOS — Six-company CRM duplicate preview

**19 October 2026 | Build complete, private CRM activation NOT applied**

## Current facts

- Six original Workspace solar outreach messages are verified in authenticated
  Gmail and preserved in the new migration-052 historical evidence table.
- The existing five-minute Gmail monitor showed zero inbound provider-header
  candidates at the 19 October 2026 08:02 UTC observation.
- The existing restricted canonical intent reader showed no Gmail-thread or
  exact-recipient `outbound_intents` matches for the six known sends.
- Historical evidence is valid, but does not prove commercial contact authority,
  tenant membership, canonical message approval, opt-out clearance or revenue.

## New capability prepared

`empire_os/workspace_solar_crm_tenant_prospect_match.py` provides a
deterministic, privacy-minimal candidate duplicate check for:
GB NRG, Perfect Sense Energy, Solar4Good, Sustain Commercial Solar,
SOL PV Group and 100% Renewables.

A new route is added to the **existing** Revenue CRM router:

`GET /v1/revenue-crm/workspace-solar/prospect-name-matches/preview`

The route first passes through **the existing signed authenticated CRM
tenant resolver**, with a dedicated PostgreSQL tenant login and
`empire_current_tenant_id()` validation. It uses the pre-existing
`PostgresRevenueCrmRepository.prospects(limit=500)`, which reads the
RLS-scoped `public.revenue_crm_prospects` view. The route will not use
the Founder global reply-reader role, guest headers, an arbitrary
`tenant_id` parameter, or a shared database login.

A casefolded/whitespace-normalised *exact business name* can identify a
potential duplicate or several duplicate prospects **within that verified
CRM tenant only**. Candidate prospect IDs are returned only to the
authenticated tenant; no customer emails, phone numbers, provider
message IDs, contact details or other tenants' rows are included. A
500-row limited view is labelled non-exhaustive, and zero matches in
that window do not imply a database-wide absence.

**Never interpret name equality as original contact authentication,
consent, suppression clearance, buyer interest, an approved historical
send, a canonical intent match, or authority to create/send a CRM case.**
Output flags remain FALSE for contact verification, CRM mutation,
outbound and financial actions. Any cross-tenant row or invalid input
fails closed.

## Owner-safe frozen preview

The live private CRM pilot runs from
`/opt/empire-ai/crm-pilot-releases/founder-queue-20261018v1`. Its
`empire_os/revenue_crm_api.py` contains other agents' founder action,
partner conversation, calendar and commercial-loop routes not present
in the canonical shared source. It must **not** be replaced wholesale.

An isolated candidate was prepared at
`/home/ubuntu/empire_worktrees/empire_crm_solar_tenant_name_preview_20261019`.
The active CRM `empire_os/` package was copied and differs in only
the new helper plus its one additive API-route change. Other live API
features were preserved. Isolated import checked all **28 resulting** CRM router routes,
including existing founder acquisition, partner and commercial-loop
paths. The current live CRM service is still healthy;
the new route returns 404 there, correctly indicating it has **NOT
been deployed**.

Read-only test suite passed across original CRM authentication,
tenant reader, existing CRM API and new bounded name-match tests.

## Rollback-protected private release staged and preflighted

The operator-owned, hash-pinned release
`scripts/deploy_private_crm_solar_tenant_name_preview_20261019.sh`
now installs the exact frozen two-file addition from the copied **active**
CRM owner release—not the older canonical CRM source. Only the existing
`empire_os/` Python application package is copied; root-only override
files, older release operation directories and private credentials are
excluded. The protected systemd environment file, existing signed
tenant membership verifier and existing database reader are reused.

The read-only preflight verifies the active owner version, the pinned
checksums of both changed source files, byte-for-byte parity of all
unmodified application code, all 28 resulting CRM routes, existing
authenticated-route HTTP 401, current health, other service health
and public Founder HTTP 404.

If the owner separately authorises the private CRM UI/API deployment,
the operator-only apply creates the new root-owned application release at
`/opt/empire-ai/crm-pilot-releases/founder-queue-solar-name-20261019v1`
and adds the new isolated
`60-solar-tenant-prospect-name-preview.conf` drop-in. It does **not**
change the existing
`50-founder-release-20261018.conf` file. A successful cutover
requires healthy loopback CRM, the new GET returning HTTP 401 without
authentication, all 27 previous Python router contracts unchanged,
the existing prospects endpoint still HTTP 401, no public exposure and
healthy Founder/Gmail services. On failure the new 60 drop-in is removed,
systemd reloaded and the previous founder queue release restarted.

Current status: **corrected preflight passed, release staged only; NO production CRM
cutover**. A valid authenticated CRM owner session is required to
inspect actual tenant-scoped name-match candidates. It would be incorrect
to claim a production name match before that authenticated read occurs.

Operator commands (private-release authorisation required):

```bash
cd /srv/empire_os
bash scripts/deploy_private_crm_solar_tenant_name_preview_20261019.sh --preflight
sudo bash scripts/deploy_private_crm_solar_tenant_name_preview_20261019.sh --apply-founder-approved-private-crm-name-preview
```

Expected marker:
`PRIVATE_CRM_SOLAR_TENANT_NAME_PREVIEW_RELEASE_VERIFIED`.
No extra database migration, role, timer, CRM write, email send, or
payment activation is included.

## Failed operator attempt and owner-safe correction — 19 October 2026

The founder ran the staged private CRM operator command. Its initial
read-only checks passed with
`FROZEN_28_ROUTE_CRM_PACKAGE_VERIFIED` and `PRECHECK_PASS`, but the
privileged script stopped at `HOLD_BASELINE_OPENAPI_UNAVAILABLE` after
receiving HTTP 404 from `/openapi.json`.

This was a mistake in the **release verifier**, not a CRM defect.
The existing first-party pilot intentionally constructs FastAPI with
`docs_url=None`, `redoc_url=None` and `openapi_url=None`.
Independent live checks confirmed all three documentation paths are HTTP
404, the prior Founder CRM remains ACTIVE from
`founder-queue-20261018v1`, and neither the proposed 60 systemd drop-in
nor the new release directory exists. The new preview still returns 404;
all prior authenticated routes retain expected 401 responses. No
production CRM or database mutation occurred.

The release script was corrected to use
`scripts/verify_private_crm_router_parity_20261019.py` instead of
fetching OpenAPI. That helper uses separate minimal-environment Python
processes to import the exact pinned old and staged CRM router sources
**without live CRM credentials**. It asserts all 27 old route paths,
HTTP methods, endpoint names/signatures, dependencies and route metadata
are unchanged, and the sole 28th endpoint is the proposed GET.
After the private service switch, it independently checks the copied
root-owned target package against the same active baseline. The
production HTTP smoke checks also confirm authenticated GETs still
return 401, existing Founder console assets return 200 and
`/openapi.json`, `/docs` and `/redoc` remain 404.

The corrected stage/parity tests passed and the updated read-only
release preflight passed; no live CRM switch was performed while fixing
this verifier. **Do not enable OpenAPI** to make the release succeed.

## Remaining commercial authority boundaries

The preview is a deduplication aid, not a CRM intake or an automated
prospect-ingest system. Only verified founder-tenant session users can
access it. A name match does not establish a verified original contact
identity or tenant relationship for that Gmail thread. No genuine buyer
reply has been detected in the Workspace scan so far; subsequent
original provider chain, sender, content, suppression and commercial
intent checks remain required before any canonical CRM promotion.
