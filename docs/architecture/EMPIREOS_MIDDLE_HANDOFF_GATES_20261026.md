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


## V6 isolated PostgreSQL proof of tenant isolation
The HELD scoped RPC in `docs/architecture/CRM_SCOPED_LINEAGE_RPC_HELD_20261026.sql`
now **requires a non-null exact buyer ID and matching buyer.org_id** for
either an existing event or an existing order. This is intentional: a
buyerless event tied only to a globally shared business entity cannot be
safely disclosed to a CRM tenant. Such early intelligence remains upstream
until separately verified tenant custody can be represented by an authorised
source-specific receipt. A buyer ID is only an identity-scoping predicate,
**not buyer acceptance, capacity or payment proof**.

The isolated, disposable PostgreSQL 18 fixture in
`tests/crm_scoped_lineage_isolated_fixture.sql` and
`tests/test_crm_scoped_lineage_sql_ephemeral.py` executes the **actual
held SQL** in an ephemeral Unix-socket-only test database. It verifies:
- Two separately authenticated tenant logins share the SAME canonical entity
  but can retrieve only event/order IDs associated with their OWN buyers.
- Buyerless events/orders and buyer IDs for another tenant return no row.
- A CRM login with reader-role membership but NO tenant session binding sees
  no receipt.
- Direct raw-table SELECTs are rejected for the restricted CRM role.
- Revoking a previously valid tenant binding immediately hides its receipt.
- Any unresolved identity conflict, duplicate active tenant binding or
  invalid source-matching method prevents receipt promotion.
- Missing opportunity/prospect, an unsupported receipt kind and an
  unauthorised receipt fail closed.

This proves SQL security behavior **in an isolated test environment only**.
It does not establish that the proposed CRM function exists in original
EmpireDB, that a matching actual revenue record exists, or that the original
CRM owner's unreleased login attestation can pass against production.
The SQL is held; no production database migration, role/grant, money or
outbound authority was executed.


### V6.1 exact event → order continuity
If an existing `commercial_events` row references a `fulfilment_order_id`,
the tenant-scoped held RPC now requires that exact order to reference the
**same** GTM opportunity, source prospect, canonical business entity **and**
tenant-owned buyer. An event tied to another tenant's order fails even if
the underlying company is shared. An event with no order reference can
still qualify as a pre-order event **only if it already has a named buyer
owned by the authenticated tenant**. Disposable PostgreSQL fixture tests
exercise both the mismatched and correctly matched order case.


## V7 — Same-buyer acceptance evidence after exact scoped order identity
The HELD tenant-safe `empire_crm_exact_lineage` SQL and
`crm_scoped_lineage_reader.review_signed_scoped_lineage` now return the
actual **buyer UUID** linked to the exact existing event or order. This
result is explicitly tenant-owned via the original buyer's `org_id`.
The receipt still cannot confer terms/acceptance, route, settlement or
fulfilment authority by itself.

`empire_os/canonical_buyer_acceptance_handoff.py` now verifies the
next intermediate handoff against the **same** signed-tenant order:
- Original verified prospect, canonical company, GTM opportunity, tenant,
  exact fulfilment order and buyer identities must agree.
- Reuses, rather than duplicates, original
  `commercial_terms_materializer.build_persisted_terms_stage`, which
  checks the original approved terms review, installed price/hash/currency,
  ordered approved and accepted events, acceptance kind/actor/source ref
  and non-future timestamps. A proposed offer or approved terms alone
  does not qualify as buyer acceptance.
- Any mismatch, changed buyer, another order, duplicate acceptance event,
  wrong terms SHA/price, forecast evidence, expired terms or unsupported
  source timestamp fails closed.
- **Test-injected** source evidence yields
  `INJECTED_ACCEPTANCE_COHERENCE_TEST_ONLY`; it is never an actual
  customer acceptance, payer capacity, fulfilment, settlement or revenue.
  The production path still requires the original scoped RPC to be
  released and the buyer-facing acceptance source independently verified
  by its original authorised owner.

The separate original buyer capacity/readiness, route/compliance, order,
payment and Economic Memory stages remain untouched. The existing
`revenue_evidence_workplan` now names the exact persisted-terms receipt
validation step for the Buyer Acquisition and Smart CRM owners. **No
new sales, emails, database mutations, services, timers or queues
have been created.** The SQL remains held pending CRM-owner review.
