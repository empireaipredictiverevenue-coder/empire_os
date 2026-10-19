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

## Remaining activation boundary

This is a **staged, owner-coordinated private CRM enhancement**.
A verified isolated runtime release based on the current active
snapshot and a privileged operator cutover are still required. Do
not restart the existing CRM service, overwrite its 50 founder
release drop-in, or use the canonical repository version as a full
replacement. No new database schema or role is required.

Once privately deployed, the actual authenticated Founder CRM session
can view whether any of the six companies already appears in
the correctly scoped CRM prospect list. The result is a deduplication
lead, not a buyer or contact identity. The next genuine reply is still
subject to content, sender, suppression and canonical original lineage
review before CRM promotion.
