# EmpireOS Smart CRM — Multi-motion pipeline enhancement
12 November 2026 | Owner: existing Smart CRM and GTM | COO oversight

## Founder objective
Use Pipedrive-style visual workflows for genuinely distinct commercial motions without creating another CRM, service or scheduler. Industry and geography are filters within a sales motion. The previously approved six functional pipelines and twelve commercial revenue categories remain the original sources of truth.

## Ten sales motions in the existing tenant CRM
1. B2B Services / Revenue Leak Check / SEO, AEO, GEO and consultancy.
2. SaaS subscriptions / EmpireOS, Predictive Cloud, AI reception and CommerceOS.
3. Enterprise procurement / NHS, tenders and corporate contracts.
4. Lead and call buyers / UK and US, calls, forms, appointments, bookings.
5. Publisher supply / source rights, supply contracts and acceptance.
6. Owned consumer acquisition / home services, National Storm Hub and consented jobs.
7. Rank and rent / local microsites and contractor leases.
8. Data, API and licensing / property, permit and predictive intelligence.
9. Affiliate referrals / approved partners and attributable commissions.
10. Commerce partners / sellers, wholesale and supplier onboarding.

An eleventh UNASSIGNED review lane retains prospects whose commercial role and pipeline are not yet independently verified.

## Original-system implementation
- Existing tenant-aware Revenue CRM API: three authenticated GET routes at /v1/revenue-crm/pipelines/board, /pipelines/view and /pipelines/board.js.
- New read-only server projection in empire_os/revenue_crm_multi_pipeline.py.
- Responsive interactive board HTML and JS in the original empire_os/static folder.
- Canonical tenant prospect and buyer view reads only; no new database, tenant identities, auto sends, stages written, commissions or claimed money.
- Buyer accounts show as accounts and never imply signed buy-boxes, paid lead events or closed sales.
- Prospect pipeline_id must be explicit in the trusted canonical record to assign it. Existing revenue_crm_prospects does not expose that field, so records stay UNASSIGNED rather than being assigned from niche, postcode or name.
- Activity indicators use actual lifecycle timestamps. Without a verified timestamp or due task, the UI says unknown, not overdue.
- Multi-pipeline counts are not combined with source-research candidates or GSC traffic to create synthetic leads.

## Verification and controlled release
Source and tenant-isolation automated tests, existing authenticated CRM tests, and isolated live-browser desktop/mobile UX checks are required. The current production CRM service is on a separately pinned first-party login/tenant release. Source availability does not mean the active release has loaded the new routes.

Next: the original CRM release owner validates the route pin/rollback, then conducts a private controlled activation. A persisted drag-and-drop stage transition additionally needs the existing audited CRM sales journal and a DBA-reviewed canonical pipeline binding. Do not enable a new writer, database migration or public route by inference.

## CEO / COO actual status
ASTRA's active executive source remains in OBSERVE with 14 departments, eight eligible planned steps, zero validated opportunities and blocked independent evaluation. COO leadership GET is staged in its original October worktree and not mounted in the active Founder API. COO responsibility is sales-motion owner allocation and evidence review, not a new parallel scheduler or CRM.
