# Original conversion prediction registry — staged implementation

Date: 18 October 2026
Branch: `feature/predictive-decision-control-20261018`
Owner: Predictive Revenue + EmpireDB database owner

**Mission:** ensure a prospective original prediction can eventually be
compared with a canonical verified terminal commercial outcome without
reconstructing the prediction after the fact.

## Existing infrastructure reused

- `empire_os/predictive_calibration.py`: original conversion probability
  preflight and canonical `review_commercial_prediction` outcome scoring
- `empire_os/outcome_feedback.py`: validated tenant-specific commercial outcome
  and independent payment/fulfilment proof
- `empire_os/economic_memory.py`: verified outcome-conditioned learning
- `empire_os/lead_shadow_calibration_benchmark.py`: chronological validation,
  Brier and prequential historical baseline.
- Existing EmpireDB `empire_current_tenant_id()` authenticated session
  identity; no Supabase database or second data plane.

The **existing** `predictive_forecasts` registry is for directional time
series and must NOT be used for buyer conversion-probability predictions.
The existing Quant opportunity `prediction_ref` likewise does not mean an
original conversion-probability forecast has been durably recorded.

## What is built, but not deployed

`empire_os/original_conversion_registry.py` verifies the explicit
prospective conversion prediction, bounded source IDs, model identity,
probability and original horizon; hashes are reproducible. It constructs a
non-authoritative registration request and checks whether externally supplied
receipt/readback structures agree. **Matching objects are still not trusted
DB proof.** A client-supplied timestamp, hash or dict has no custody authority.

`empire_os/original_conversion_registry_transport.py` provides disabled-by-
default, separate-role, parametrised read and write transport adapters:
`empire_original_conversion_prediction_writer` and
`empire_original_conversion_prediction_reader`. They connect only when
explicitly enabled and separately supplied with tenant-bound credentials.
No credentials, systemd service, scheduler, API route or automatic DB write
are part of this release.

`docs/commercial/STAGED_ORIGINAL_CONVERSION_REGISTRY_20261018.sql` is a
**STAGED-ONLY DDL draft**, intentionally outside automated migration paths.
It describes:
- a dedicated original-conversion registry with unique tenant+prediction ref
- RLS enabled and forced, canonical authenticated tenant-bound functions
- database-origin `recorded_at` (not a client-supplied registration clock)
- append-only protection and collision hold for changed same-ID payloads
- no table grants, NOLOGIN non-inheriting capability roles, no memberships
- bounded prospective windows and evidence fields
- separate least-privilege writer and reader functions.

**SQL has not been executed or independently parsed against PostgreSQL.**
The DBA must review syntax, RLS, privilege and transaction semantics in an
isolated database using migration and role grants appropriate to the existing
production configuration. This is not approved for deployment.

The preflight's older
`must_store_in_existing_canonical_prediction_registry` flag is now
`false`; its explicit `requires_dedicated_original_conversion_registry`
flag is `true`. This prevents accidental routing into the older directional
time-series forecast registry.

## What a real registered prediction will require

1. Resolve the authenticated tenant from the *actual* EmpireDB session, not
   the request payload.
2. Have verified, real, timestamped opportunity evidence and an original
   conversion probability and horizon **before** the eventual outcome.
3. Commit one append-only canonical record; receive the database-generated
   `recorded_at` and enforce idempotent immutable identity.
4. Independently read back the same tenant/record using a separate constrained
   read role; verify all model/probability/evidence fields.
5. Prove that custody/source clocks, tenant membership and read role are
   authoritative. A matching in-memory dict is insufficient.
6. Only then pass registered provenance and the independent canonical
   commercial outcome into the existing calibration and Economic Memory gate.
7. Keep model training/weights, outbound, payments and accounting separately
   permissioned. A registry record is evidence, not a customer or an order.

## Production truth as of last read-only inspection

- 11 Quant opportunity candidates, 0 with complete required Quant economics.
- Original conversion-probability registration **not activated**.
- 0 unscoped, verified commercial calibration outcomes in the existing
  Economic Memory snapshot.
- No new sales, revenue or outcome claimed or created.

## Owner release checklist

- Review the staged SQL against the authoritative current EmpireDB schema.
- Confirm authenticated tenant resolver provenance and FORCE RLS behavior.
- Isolated DB test: role denial; cross-tenant denial; future/backdated
  rejection; concurrent duplicate; hash collision; INSERT RETURNING and
  readback; UPDATE/DELETE denial; missing tenant and forged timestamps.
- Founder approval for the exact migration, role assignments, secret custody,
  deployment ordering, rollback and logging. Do not create unrestricted logins.
- Deployment of paired model/backend/Founder Console through coordinated owners.
- Verified independent capture from a **real** future prediction and eventually
  a genuine terminal outcome before calibration is described as effective.

No production database modifications or financial/outbound action were taken.
