# EmpireOS: Solidifying the Middle of the Revenue Workflow
**26 October 2026 — one original EmpireDB / Smart CRM, strictly read-only integration**

## This is about transitions, not target KPIs
The missing workflow is not a goal statement. Each component must produce a **specific, independently checkable receipt** before the next one can accept the same record. The same business/tenant/order lineage must be preserved. The current runtime's prospect counts, search records, engagement and CRM aggregations cannot establish an end-to-end conversion.

## The critical first two transitions — implemented
### 1. Original prospect → canonical business entity
`empire_os.canonical_prospect_tenant_handoff.review_existing_prospect_entity_tenant` requires:
- An exact prospect UUID and canonical entity UUID, never company-name/domain guesswork.
- **One active** `public.prospect_entity_links` row matching both IDs and a bounded source receipt.
- An acceptable source-verification match method, not score alone or a submitted claim.
- **No open `public.business_entity_conflicts` row** for that exact prospect/entity.
If any predicate fails, raise `ProspectHandoffHold`. A source table name or a forecast is not an entity link.

### 2. Canonical business → authorised tenant in the original Smart CRM
The fixture-only low-level reader verifies:
- Exactly one active, current `public.tenant_business_entity_bindings` row through the **existing** `resolve_tenant_entity_binding` helper.
- The entity and tenant IDs must match the authenticated scoped reader, not an external payload or a mailbox domain.
- The legacy `review_signed_crm_prospect_tenant` accepts injected test cursors only. **CRM040 explicitly refuses direct CRM reader SELECT on global identity/tenant bindings.** Real CRM reads use the new `crm_scoped_lineage_reader.review_signed_scoped_lineage`, which requires an owner-approved tenant-scoped SQL function, the original `SignedCrmTenantVerifier`, restricted login privilege attestation and `public.empire_current_tenant_id()`. That function is HELD, not deployed.
- **RELEASE DEPENDENCY:** the live checkout has an *uncommitted CRM-owner change* adding `CRM_LOGIN_AUTHORITY_SQL`. The clean feature branch does not include that unpublished guard. This module explicitly throws `ORIGINAL_CRM_LOGIN_ATTESTATION_UNRELEASED` and does not connect until the CRM owner publishes the original restricted-login protection. We do **not** copy/overwrite that agent's dirty code.

### Next transitions — still held, not claimed complete
| Transition | Exact evidence the next owner must require | Current engineering truth |
|---|---|---|
| Canonical tenant/source → `gtm_opportunities.id` | Independent opportunity-to-source/identity association, source rights, immutable GTM UUID in original EmpireDB | No verified direct GTM-to-prospect/entity association in observed schema |
| GTM opportunity → prospective buyer | One actual downstream payer, territory, signed buy box, acceptance event, price, verified capacity, source restrictions | No verified commercial capacity |
| Buyer → approved offer/outbound | Original suppressions, accepted exact terms, authorised sender, delivery route, explicit governed approval | No send authority from source or CRM link |
| Accepted event → fulfilment | Exact accepted order ID, attributable lead/call/customer event, confirmed receipt and delivery state | Not independently attested |
| Fulfilment → settled net revenue | Canonical paid receipt, valid refund/dispute windows, exact order linkage and currency | Zero observed verified payments |
| Realised outcome → Economic Memory | Same canonical outcome linked causally to original opportunity, actual realised net margin | No verified outcome-conditioned memory |

**Important:** the new injected-cursor fixture demonstrates that the existing SQL contracts can prove an intermediate identity-to-tenant relationship; it does NOT attest a production tenant session or a paying buyer. Return flags explicitly hold GTM association, buyer acceptance, outbound, funding and payment at FALSE.

## Where the code connects
- The unified `revenue_evidence_workplan` Smart CRM action names the precise **tenant-scoped RPC reader**, with the owner-reviewed SQL function still held.
- The original authenticated CRM service must invoke the helper using its **owner-managed** signed token verifier, dedicated DSN and role-scoped session after the CRM owner's privilege guard is released. No new API route, database, role, service or systemd timer was invented.
- A future separately reviewed execution bridge can enqueue only supported original worker adapters. The existing `DepartmentWorkQueue` must not be fed invented target actions; no work has been added to the live queue by this slice.
- All held financial, migration, mainnet, consent, email and cross-tenant writes remain OFF.

## Verification
`tests/test_canonical_prospect_tenant_handoff_20261026.py` covers exact match, correct active binding, duplicate bindings, unresolved conflicts, source-ref absence, invalid IDs, cross-tenant session mismatch, invalid signed CRM token and missing unpublished privilege guard. It uses synthetic fixture UUIDs only; no real customer data is copied or written.

Next truthful release gate: the CRM owner publishes the dedicated-login attestation contract; then run the restricted owner-credential read-only smoke test against one **actual authorised** prospect/entity/tenant association. Only after that should the original GTM Opportunity linkage be designed from real observed schema evidence.


## Original pre-order and post-order GTM continuity — now implemented as READ ONLY checks
EmpireDB migration 002 **already** places `opportunity_id`, `prospect_id`, and `entity_id` on `commercial_events` and `fulfilment_orders`. A new relation table is unnecessary for checking **existing** immutable events or order rows. Do NOT insert an event/order to make the check succeed.

### 3A. Before a fulfilment order exists
`canonical_order_lineage_review.review_existing_commercial_event_lineage` requires:
- Exact UUID of one **existing** `commercial_events` row, and an exact existing `gtm_opportunities.id`.
- Matching, non-null opportunity/prospect/entity UUIDs from the original existing immutable event.
- The original same-cursor prospect/entity receipt, absence of unresolved identity conflicts, and exact authenticated tenant binding.
- Return `EXISTING_EVENT_LINEAGE_OBSERVED_NO_ORDER_AUTHORITY`, never buyer acceptance, an order, payment, lead delivery or economic memory permission.
This permits a **source-bound pre-order evidence handoff**, but an arbitrary event type doesn't prove its underlying business claim or authorised source rights.

### 3B. When an existing fulfilment order can be independently named
`canonical_order_lineage_review.review_existing_order_opportunity_lineage` requires:
- Exact existing `gtm_opportunities.id` and `fulfilment_orders.id` rows; the order must reference the **same** opportunity/prospect/entity.
- Exact original source+tenant scope, checked in the same restricted read-only cursor.
- Returns `EXACT_EXISTING_ORDER_SOURCE_LINEAGE_OBSERVED_REVIEW_ONLY`. This is identity continuity, not proof of a buyer contract or delivered and paid service.
- Order state `paid` or `settled` is **not** cash finality. Buyer acceptance, delivery/attribution, independent settled transaction, refunds and Economic Memory require the original downstream attestations.

### Trust and release boundary
The **fixture-only low-level checker** accepts at most one `event_id` or `order_id` paired with an exact `opportunity_id`; it cannot run on the real CRM reader's restricted raw-table privileges. The production-oriented `review_signed_scoped_lineage` instead takes one exact receipt kind (`event` or `order`) and uses only the **held** tenant-safe RPC, in the original signed-member, role-scoped READ ONLY transaction. Incomplete pairs, both receipt types, cross-company links, guessed IDs, ambiguous source binding or revoked tenant authority fail closed. Tests using an injected cursor explicitly report `INJECTED_CONNECTOR_RESEARCH_ONLY`; they are not evidence of a real production DB session.

The CRM owner's as-yet-unreleased `CRM_LOGIN_AUTHORITY_SQL` hardening remains a **hard dependency**. No protected production file, running timer, EmpireDB schema, outbound queue, funds, commercial price or revenue accounting was modified by this release candidate. The read-only checker cannot produce real opportunities without existing authentic records.


## V5 tenant-safe RPC correction (26 October) — explicit release blocker
A fresh review of original `migrations/empiredb/040_revenue_crm_tenant_reader_views.sql`
established that `empire_revenue_crm_reader` **must not** have raw SELECT
on `prospect_entity_links` or `tenant_business_entity_bindings`.
Original `018_tenant_context_foundation.sql` also restricts event/order
rows by buyer tenant under its separate tenant-reader role.
Therefore, a raw-table SQL SELECT through the CRM reader was a **test-only**
capability, never a safe live implementation. The low-level checker now
fails closed for any non-injected connection.

**Proposed owner-approved implementation, not applied:**
`docs/architecture/CRM_SCOPED_LINEAGE_RPC_HELD_20261026.sql` is a held,
guarded SQL DESIGN for `public.empire_crm_exact_lineage(uuid,uuid,uuid,text)`.
It returns exactly one safe, UUID-only tuple after original login-bound
tenant, source identity, unresolved-conflict, exact GTM, existing event/order,
and optional buyer-tenant checks. It does not grant raw table rights to the
CRM reader. The new adapter `empire_os/crm_scoped_lineage_reader.py` will
read **only** that scoped function via a signed CRM read-only session;
before calling it, it checks the original LOGIN privilege envelope,
the trusted database tenant, and the function's SECURITY DEFINER,
STABLE, migrator-owned, locked search_path provenance.

The staged function is not deployed. Its SQL requires CRM-owner review,
fixture security tests (including cross-tenant denial and revoked access),
explicit founder migration approval, rollback evidence, and exact live role
privilege reconciliation. No privileged database query was used to claim
that matching production events/orders exist; an attempted privileged
read-only check was disallowed by the server command policy.
Zero live customer handoffs, buyer contracts, payments, or revenue are
established by these fixture tests.
