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
The same reader verifies:
- Exactly one active, current `public.tenant_business_entity_bindings` row through the **existing** `resolve_tenant_entity_binding` helper.
- The entity and tenant IDs must match the authenticated scoped reader, not an external payload or a mailbox domain.
- `review_signed_crm_prospect_tenant` consumes the original **`SignedCrmTenantVerifier`** and verifies active membership; the restricted original PostgreSQL session is required to pass the CRM-login privilege check and `public.empire_current_tenant_id()`. The transaction is `READ ONLY` with an explicit four-second timeout.
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
- The original unified `revenue_evidence_workplan` Smart CRM action names the precise signed read-only review function as its next required proof.
- The original authenticated CRM service must invoke the helper using its **owner-managed** signed token verifier, dedicated DSN and role-scoped session after the CRM owner's privilege guard is released. No new API route, database, role, service or systemd timer was invented.
- A future separately reviewed execution bridge can enqueue only supported original worker adapters. The existing `DepartmentWorkQueue` must not be fed invented target actions; no work has been added to the live queue by this slice.
- All held financial, migration, mainnet, consent, email and cross-tenant writes remain OFF.

## Verification
`tests/test_canonical_prospect_tenant_handoff_20261026.py` covers exact match, correct active binding, duplicate bindings, unresolved conflicts, source-ref absence, invalid IDs, cross-tenant session mismatch, invalid signed CRM token and missing unpublished privilege guard. It uses synthetic fixture UUIDs only; no real customer data is copied or written.

Next truthful release gate: the CRM owner publishes the dedicated-login attestation contract; then run the restricted owner-credential read-only smoke test against one **actual authorised** prospect/entity/tenant association. Only after that should the original GTM Opportunity linkage be designed from real observed schema evidence.
