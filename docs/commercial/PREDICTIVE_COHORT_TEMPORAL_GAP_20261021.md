# Predictive Revenue — temporal and per-product cohort safeguards

21 October 2026. Isolated OBSERVE branch only. No changes to production source/service, canonical EmpireDB, reader roles, customer checkout, outbound, Economic Memory or scientific model weights.

## Source defect addressed

Previously the tenant terminal source reader used the time bound for each commercial outcome but counted a linked `revenue_recognized` event regardless of its independent occurrence/ingestion timestamps. This could let an event created after the forecast evaluation as-of time establish a historical winning order.

`CANDIDATE_SQL` now requires each recognized event's `occurred_at` **and** `created_at` to be between the original order creation time and a parameterized, timezone-aware `as_of` bound. Only the existing restricted, tenant-bound read-only database transaction can execute the query. The SQL receives the same `as_of` twice as bound parameters; it never uses a caller-supplied tenant identity for authorization. A won outcome with no event known by the evaluation as-of time is held as unverified.

This is a candidate-source temporal guard, not authenticated economic proof. Revenue ledger provenance and finality remain the original Finance owner's responsibility.

## Product cohorts, not pooled lead signals

The source reader now groups its at-most-200 candidate rows **in memory** by original `product_id`, then returns only `candidate_products_observed`, `largest_candidate_product_terminal_cohort`, and `candidate_product_cohorts_reaching_20`. These are anonymous operational coverage counts, not per-customer or per-product forecast probabilities. Order, product, buyer, tenant, revenue or evidence identifiers are not exported. When the 200-row bound is reached, coverage counts are `null`, not misleading partial cohorts.

The minimum 20-sample threshold is only a **research planning indicator**. It is not evidence of product-version consistency, independent terminal attestation, prospective registration or out-of-sample Brier performance. A product with 20 candidate outcomes is not eligible for commercial forecasts.

## Test proof and remaining deployment gates

Unit tests exercise strict as-of SQL placeholders, distinct per-product aggregation, 20-candidate threshold behavior, retention of scientific source holds, and no identifiers exported. The earlier PostgreSQL 18 test exists, but the actual disposable PG18 rerun for this amended SQL still needs successful execution and readback. Production source and the pinned OBSERVE launch release must be checked against the exact commit before promotion.

The original reader credential `EMPIREDB_TENANT_OUTCOME_READER_DSN` was not configured in the execution shell; do not supply a superuser or app fallback. The authenticated original DB owner must validate 056 deployment and tenant RLS, and Finance/Quant must independently attest evidence and immutable pre-outcome conversion forecast registration. This change does not bridge raw outcomes into the Scientific Agent.
