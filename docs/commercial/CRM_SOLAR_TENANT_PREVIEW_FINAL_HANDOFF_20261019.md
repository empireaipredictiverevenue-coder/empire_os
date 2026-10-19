# EmpireOS CRM — Six Solar Prospect Name Preview: Final Operator Handoff

**Date:** 19 October 2026. **Status:** code fixed, isolated candidate frozen,
81 automated tests passed, operator preflight passed. **NOT DEPLOYED**.

## Mission and exact verified checkpoint

The original six UK solar Workspace Gmail sends (GB NRG, Perfect Sense
Energy, Solar4Good, Sustain Commercial Solar, SOL PV Group, 100% Renewables)
are backed by six independent, still-UNBOUND historical receipts in
EmpireDB migration 052. The latest Workspace scan has **0 new buyer reply
candidates**. No canonical approved original send, tenant contact
identity, genuine CRM customer or realised revenue has been asserted.

The next bounded capability is **duplicate screening** against existing
tenant-visible CRM prospects. The new endpoint is:
`GET /v1/revenue-crm/workspace-solar/prospect-name-matches/preview`.

It requires the existing authenticated, signed CRM tenant resolver, uses
the dedicated tenant-bound read-only repository, checks at most 500
prospect rows, and returns only exact-normalised possible name matches.
Any partial 500-row view is marked non-exhaustive; a matching name NEVER
proves consent, customer identity, matching outbound intent, verified
buyer interest or authority to send. It creates no CRM/contact rows,
emails, payments, scheduled jobs, new roles or new database schema.

## Diagnosed initial failure — fully corrected

The founder executed the previous release script and got:
`PRECHECK_PASS`, then `HOLD_BASELINE_OPENAPI_UNAVAILABLE`
when it called `http://127.0.0.1:8783/openapi.json`.

**This was a bad verifier assumption, not a CRM server failure.**
The existing private CRM intentionally disables `/openapi.json`,
`/docs` and `/redoc` (all 404). The script failed BEFORE release
installation, and subsequent verification confirmed the original
`founder-queue-20261018v1` release still active. No 60 drop-in,
new release directory, database or service mutation occurred.

The verifier now compares the **actual Python router contracts**
offline by importing the active 27-route package and the isolated
28-route candidate in separate clean Python processes. It compares
paths, HTTP methods, endpoint names/signatures, route metadata and
declared dependencies. It validates the single new GET and continues
to require that CRM public documentation endpoints stay disabled.
Authenticated private endpoints must continue to return 401 to guests,
and the existing Founder console assets must remain 200.

A separate final compatibility check corrected the helper for
`psycopg` 3's native `uuid.UUID` values in tenant/prospect columns;
it still requires canonical signed tenant scope and rejects cross-tenant
rows. The frozen helper source and SHA pinned in the release script were
updated together. The helper's native-UUID regression test passes.

**Latest complete result:** 81 relevant tests PASS, one unrelated
Starlette/anyio deprecation warning. Offline parity:
`CRM_PRIOR_ROUTER_CONTRACTS_PRESERVED_ONE_GET_ADDED`
(27 old routes, 28 new). Live read-only preflight:
`FROZEN_28_ROUTE_CRM_PACKAGE_VERIFIED` then `PRECHECK_PASS` and
`PRIVATE_CRM_SOLAR_NAME_PREVIEW_STAGED_NOT_DEPLOYED`.

## Source and release ownership

- Canonical repository: `/srv/empire_os`; do not reset or stage other
  agents' unrelated dirty files.
- Current live private CRM:
  `/opt/empire-ai/crm-pilot-releases/founder-queue-20261018v1`.
- Frozen additive candidate:
  `/home/ubuntu/empire_worktrees/empire_crm_solar_tenant_name_preview_20261019`.
- New immutable root-owned deployment target (operator-created only):
  `/opt/empire-ai/crm-pilot-releases/founder-queue-solar-name-20261019v1`.
- Existing rollback base drop-in (do not modify):
  `/etc/systemd/system/empire-revenue-crm-pilot.service.d/50-founder-release-20261018.conf`.
- New operator-created drop-in:
  `/etc/systemd/system/empire-revenue-crm-pilot.service.d/60-solar-tenant-prospect-name-preview.conf`.
- Exact release:
  `scripts/deploy_private_crm_solar_tenant_name_preview_20261019.sh`.
- Offline parity:
  `scripts/verify_private_crm_router_parity_20261019.py`.
- Source additions:
  `empire_os/workspace_solar_crm_tenant_prospect_match.py`
  and `empire_os/revenue_crm_api.py` (the frozen version has preserved
  other-agent founder queue, partners and commercial-loop routes).

The protected CRM environment/secret file remains in its existing
systemd configuration. Do NOT replace the frozen CRM package with the
older shared router or enable OpenAPI.

## Single remaining operator action

Remote Desktop Commander does not have authority to run this
privileged systemd cutover. The founder can use their trusted
interactive Ubuntu terminal:

```bash
cd /srv/empire_os
bash scripts/deploy_private_crm_solar_tenant_name_preview_20261019.sh --preflight
sudo bash scripts/deploy_private_crm_solar_tenant_name_preview_20261019.sh --apply-founder-approved-private-crm-name-preview
```

Require `PRIVATE_CRM_SOLAR_TENANT_NAME_PREVIEW_RELEASE_VERIFIED`.
The apply performs exact frozen-source, active-revision and service
checks; creates only the private CRM package/drop-in; restarts only
`empire-revenue-crm-pilot.service`; verifies all previous route
contracts, private authentication, asset parity, supporting services
and public Founder HTTP 404. If its health or parity check fails after
cutover, it automatically removes the new drop-in and restarts the
original CRM release.

Manual rollback **only if needed**:

```bash
sudo rm -f /etc/systemd/system/empire-revenue-crm-pilot.service.d/60-solar-tenant-prospect-name-preview.conf
sudo systemctl daemon-reload
sudo systemctl restart empire-revenue-crm-pilot.service
```

## Post-cutover evidence still required

After the operator succeeds, independently confirm:
1. Service is active and uses
   `founder-queue-solar-name-20261019v1`.
2. `/v1/revenue-crm/health` HTTP 200;
   `/v1/revenue-crm/prospects` and the **new** preview HTTP 401
   *when not authenticated*.
3. `/openapi.json`, `/docs`, `/redoc` remain 404;
   public Founder Mail remains 404; existing Founder/Gmail services
   still active.
4. Authenticated founder tenant session requests the preview through
   its existing signed CRM gateway. Report actual possible name matches,
   ambiguous duplicates, and whether a 500-row read was partial.
   Until then **NO REAL CRM PROSPECT MATCH CLAIM** is justified.

The next commercial steps are genuine buyer reply qualification,
original provider-message ancestry, suppression checks, signed
contact/tenant authority and approved follow-up; not another Gmail
monitor, not retrospective outbound approval, and not fake prospect
creation.
