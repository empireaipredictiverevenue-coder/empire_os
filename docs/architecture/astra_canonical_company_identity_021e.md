# Astra Canonical Company Scope Bridge — 021E

Purpose: remove the missing-company-domain blocker for automatic OKF retrieval,
*only after* first-party identity is independently corroborated against an
already registered canonical prospect. Existing Buyer Scout and Astra Executive
timers are reused; no new service, cloud provider, migration or job loop.

## Evidence join
- Buyer State / Next-Best Action identifies `entity_id`, `prospect_id`,
  recommended action, authority and current approval gates.
- Buyer Scout brings the existing canonical prospect seed identity together
  with a separately fetched first-party website observation.
- A company is eligible for a typed Astra `company_domain` only when all of:
  1. Both NBA and Scout receipts have valid timestamps no older than two hours.
  2. NBA action is one of verify_decision_maker, enrich_identity or
     prepare_buyer_review with explicit internal/observe authority; no founder
     gate or external waiting state.
  3. NBA entity ID and prospect ID are UUIDs; the prospect ID exactly equals
     Scout's `canonical_seed_prospect_id`.
  4. Scout reports canonical identity verified AND canonical-seed/first-party
     site corroboration, with first-party identity source type.
  5. Scout's separately recorded **canonical seed website**, observed site
     website and domain match exactly (www normalisation only).
  6. First-party site business name and canonical prospect business name
     agree; NBA company name agrees as well.
  7. No duplicate/colliding identity candidate or conflicting NBA entity.
- The output is `intelligence_request.company_domain`,
  `canonical_prospect_id`, `company_identity_source` and
  `identity_scope: research_only`. This cannot alter the underlying
  work step's authority, queue permission, success definition or founder
  gate. The earlier OKF auto matcher uses this exact company-domain field.

## Preserve unknown
Search-query coincidence, lookalike URL, company-name similarity, permit
licence registry hit, unresolved personhood and a legacy positive boolean are
not enough. Unknown identity stays unknown. The latest production Scout has
no canonical seed linked to the current NBA prospect IDs; therefore no
automatic company binding is claimed yet. The new snapshot emits aggregate
blockers and matched counts, **not** unverified inferred names.

This adapter is still an internal evidence correlation, not a cryptographically
signed corporate-domain attestation. It does NOT verify a domain's legal owner
beyond the canonical source and observed first-party page, and it does not
prove consent, buyer purchasing demand, person-email binding, payment or revenue.

## Operational boundaries
The existing Astra Executive snapshot reads the latest bounded Scout receipt;
no query backfills, no API writes, no extra timer. Do not manually invoke
production department dispatch for a dry run since that can enqueue work.
Use pure `build_executive_snapshot` or `resolve_company_bindings` against
read-only snapshots. Check `canonical_company_binding_count` and
`canonical_company_binding_blocker_counts` in the Astra Executive output.
No execution authority is attached to this information.

If further verification becomes available via a canonical EmpireDB read-only
role, attach it as additional evidence rather than weakening these conditions.
