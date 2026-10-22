# Empire AI Smart CRM — single owner, cross-chat integration handoff
**22 October 2026 | OWNER: existing unified Smart CRM build | No duplicate CRM, no new deployment in this handoff**

## Founder decision (binding)
All CRM work done in separate conversations must converge into **one branded Empire AI Smart CRM**, preserving the original founder sign-in, tenant-scoped **EmpireDB PostgreSQL**, existing CRM modules and commercial evidence. The other active Smart CRM design/integration chat is the feature owner. Do **not** spin up another CRM service, database, website or agent. Do not overwrite the other chat's staged design or migration work.

Canonical commercial workflow: **Company / Contact → Opportunity → Evidence → Sales Action → Conversation → Commercial Offer → Accepted / Fulfilled Order → Verified Settlement / Realised Revenue**. Startup Revenue Intelligence can propose opportunities, not silently create verified leads.

## Two parallel CRM workstreams identified on the same repository

**A. Branded unified design (other chat; preserve as visual direction)**
- Existing design commits **`7a1166b61`, `14d9d9b28`, `08a5f95f7`**. Branch **`feature/founder-acquisition-us-uk-20261022`**.
- Branded HTML source: `release_candidates/smart_crm_unified/revenue_crm_action_console.html` *at* `08a5f95f7`. Its proprietary brand system and official Empire AI mark/blue-and-gold styling are important and should be retained.
- This design candidate is **not an independently verified authenticated runtime**. It lacks the new `kanban-status` / `kanban-results` and five-stage workspace section contracts now present in B. **Do not drop the other chat's HTML wholesale over the active CRM.** Merge visuals into the authenticated shell after test/diff review.

**B. Authenticated tenant-data CRM workspace (this chat; preserve as functional base)**
- Source commits **`3d42b47fa`, `e8ab91b6e`**, branch `feature/smart-crm-authenticated-workspace-20261022`.
- Current **ACTIVE private CRM service**: `empire-revenue-crm-pilot.service` with working directory
  `/opt/empire-ai/crm-pilot-releases/smart-crm-auth-workspace-20261022v1`.
- Previous production rollback root: `/opt/empire-ai/crm-pilot-releases/agent-kanban-crm-20261022v1`. The new active root was installed as an exact **2-asset update** on top of 2,371 files: HTML + JS; all other 2,369 files preserved.
- Actual authenticated route is existing private `/v1/revenue-crm/review-console`. Existing signed tenant-protected `/prospects`, `/buyers`, `/department-kanban` API reads returned **HTTP 401 anonymously** on post-release checks. CRM health **HTTP 200**, service active.
- Candidate source: `release_candidates/smart_crm_authenticated/revenue_crm_action_console.html` and `.js`. Signed login and bearer in memory (no localStorage/sessionStorage), tenant-scoped buyer organisations, prospect review, per-prospect action review, original-source conversations, and six-lane agent Kanban. Revenue and Startup opportunity panels intentionally **evidence held**.
- The functional UI was Chromium-tested at 390/1440 with synthetic tenant data, denial of forged tenant board, and signout wiping rendered sensitive data. **Real founder sign-in and full actual authenticated browser flow after production switch remain unverified**; 401 alone is not proof of a successful founder session.

**C. CRM intake migration 057 (other active chat; separate approvals)**
- Independently staged CRM 057 / Founder intake candidate, including `8efb79e6b` isolated PostgreSQL fixture work, `/home/ubuntu/empire_releases/crm_057_exact_receipt_20261022_v1` (reported in other chat).
- That chat is correcting a **PostgreSQL catalog / locked `search_path` attestation mismatch** before considering any staging installation.
- Keep this a **separately gated data release**. No production EmpireDB migration, permission grant or CRM reader activation may be inferred from the UI-only deployment.

## Integration ownership and exact next tasks
1. **Single UI owner:** incorporate the newer official logo/blue-and-gold premium design from A into B's currently authenticated shell. Preserve all functional DOM IDs, `workspace-nav`, form fields, existing modules, JS request paths, login, six exact Kanban lane names, 401 signout, CSP/protected ingress and responsive mobile layout. No client-side hard-coded tenant ID.
2. **Contacts/Companies and Opportunities:** connect only current `/v1/revenue-crm/buyers` (buyer organisations) and `/prospects` (tenant prospects). These do not yet constitute a complete person/contact directory. Enhance existing company/person links only after canonical EmpireDB tenant mappings and permissions are verified.
3. **Sales Actions, Conversations, Offers:** retain per-prospect `commercial-action-review`, original inbox/conversation evidence, win plans and founder review queue. A recommendation, imported email or scout candidate is not an accepted buyer opportunity, and none can authorise send.
4. **Startup Revenue, Research, Jev, ASTRA, Buyer Scout:** connect verified evidence as tenant-scoped **read-only** proposal/inspection cards first. Candidate research stays candidate research. Specialist inference, queue, Kanban and source systems retain their own owners.
5. **Revenue:** no numeric realised revenue or accepted-order claim without canonical linked order, fulfilment, acceptance, settlement and verified payment receipts. Checkout remains read-only, payment activation OFF, no cash movement.
6. **Integration tests:** compare current live 2,371-file release against next candidate; preserve current module endpoints. Run existing authenticated CRM tenant isolation regression tests, modified shell tests, and browser tests at 390px / desktop. Separately test *real* founder signed session through the approved private ingress, contacts→opportunities→actions→conversation, while holding unavailable revenue data.
7. **Release sequencing:** UI/branding is a small overlay + one guarded `empire-revenue-crm-pilot.service` restart only after exact approval; migration 057 and other new authenticated data joins are **different release gates** after independent DBA/schema/security review. Do not combine these into a blind deployment.
8. **Cross-chat continuity:** this file and the existing design/authenticated commits are the integration handoff. Other chat should treat the live B runtime as the current starting point and A as the UI/brand source. Do not create more CRM worktrees for unrelated features or delete existing versions.

## Verified status at handoff
- Private Smart CRM B **live**, signed tenant-protected reads checked anonymous HTTP 401, CRM active; **other branded candidate A not live**.
- Both branches use the **same canonical EmpireOS Git repository**; they are not different CRMs.
- Original founder login and canonical EmpireDB unchanged by this handoff. No emails, CRM writes, database migrations, payment authority, agent execution or further production restart.
- **Outstanding:** branded merged candidate, real founder authenticated acceptance, independently verified canonical contact/opportunity/conversation joins, migration 057 schema attestation, verified economic settlement feed.

**Priority:** one login, one branded commercial control centre, one canonical tenant truth. Preserve specialised Research, Jev and ASTRA capabilities behind it. No competing CRMs.
