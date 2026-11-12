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
- Existing tenant-aware Revenue CRM API: one signed, tenant-bound JSON GET at /v1/revenue-crm/pipelines/board, plus a safe unsigned login shell at /pipelines/view and its static /pipelines/board.js. The shell contains no customer rows.
- New read-only server projection in empire_os/revenue_crm_multi_pipeline.py.
- Responsive interactive board HTML and JS in the original empire_os/static folder.
- Canonical tenant prospect and buyer view reads only; no new database, tenant identities, auto sends, stages written, commissions or claimed money.
- Buyer accounts show as accounts and never imply signed buy-boxes, paid lead events or closed sales.
- Prospect pipeline_id must be explicit in the trusted canonical record to assign it. Existing revenue_crm_prospects does not expose that field, so records stay UNASSIGNED rather than being assigned from niche, postcode or name.
- Activity indicators use actual lifecycle timestamps. Without a verified timestamp or due task, the UI says unknown, not overdue.
- Multi-pipeline counts are not combined with source-research candidates or GSC traffic to create synthetic leads.

## Live private CRM release — verified 12 November 2026
The existing loopback-only EmpireOS CRM service at 127.0.0.1:8783 now serves the new multi-pipeline login page (HTTP 200), its JavaScript (HTTP 200) and a signed-only JSON board endpoint (unsigned HTTP 401). Previous health 200, original unsigned prospects 401, authenticated Journey Designer 401, and original Search evidence 401 were preserved. This is the SAME CRM instance, sign-in, tenant binding, credentials and canonical read-only view.

Deployment: versioned additive source at /opt/empire-ai/crm-multi-pipeline-20261112, selected by a single new root-owned systemd drop-in. Protected release receipt and rollback at /var/backups/empire-crm/multi-pipeline-20261112. Production original CRM files were not overwritten. Source commits cc7ea91e3 and 32cbdca88. Full-chain real-service-environment rehearsal passed. Automated CRM tests passed (161); isolated signed synthetic login/logout desktop/mobile passed; real unsigned private-browser desktop/mobile passed, with no JS errors or private record leakage. A guarded navigation correction points to the existing /v1/revenue-crm/journeys/entry sign-in page (HTTP 200), with its original checksum stored in the protected backup. A final bounded mobile navigation correction preserves the responsive Journey Designer link; both desktop (1440px) and mobile (390px) live browser clicks reached its original existing sign-in (HTTP 200) with no JavaScript errors, no records exposed and no extra service restart.

**Acceptance boundary:** Signed founder login against real tenant records was NOT performed; no production prospect rows were returned in this review, and live deal classification and design approval are not claimed. The running CRM is private and not a new public website route.

**Persisted deal movement remains held.** Read-only production PostgreSQL catalog check: public.empire_crm_sales_action_journal does not exist, the dedicated sales writer NOLOGIN role does not exist, and zero dedicated tenant writer logins exist. The original CRM sales journal/CRM076 migration remains explicitly DBA-gated in /home/ubuntu/empire_worktrees/crm_sales_handoff_20261104. No stage movements, customer creation, scheduled follow-ups, delivery, email or revenue recognition were performed. A future persistence release must be separately reconciled against the existing audited journal, tenant RLS and approvals; never introduce a second CRM writer.

## CEO / COO actual status
ASTRA's active executive source remains in OBSERVE with 14 departments, eight eligible planned steps, zero validated opportunities and blocked independent evaluation. COO leadership GET is staged in its original October worktree and not mounted in the active Founder API. COO responsibility is sales-motion owner allocation and evidence review, not a new parallel scheduler or CRM.
