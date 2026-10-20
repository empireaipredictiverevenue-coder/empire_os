# Predictive Revenue — original unscoped outcome quarantine (20 Oct 2026)

## Original source finding

The running `empire-predictive-intelligence.timer` invokes `/srv/empire_os/scripts/build_predictive_intelligence.py` every five minutes. Its `refresh_predictive_intelligence()` uses `get_commercial_outcome_feedback(p_limit)` via the canonical EmpireDB gateway, then previously generated a product-estimate snapshot with `tenant_id=None`.

Source DDL: `migrations/empiredb/036_runtime_causal_lineage_continuity.sql` defines this RPC with only `p_limit` and `SECURITY INVOKER`, joining `public.fulfilment_orders`, `public.commercial_outcomes` and `public.commercial_events`. The joined JSON includes a *reported* tenant ID derived from order causal lineage, but this argument-free RPC cannot, by itself, prove a trusted session tenant authorization or independent source issuer. Treating its returned rows as verified tenant outcome data would be a forecast isolation failure.

## Isolated branch patch

1. `empire_os/predictive_intelligence.py:refresh_predictive_intelligence()` always withholds rows from the existing global RPC. It produces zero eligible outcome/product forecast rows, exact count of quarantined raw source rows, and `GLOBAL_UNSCOPED_OUTCOMES_QUARANTINED` or `GLOBAL_SOURCE_EMPTY_BUT_ISSUER_UNVERIFIED`. It does NOT export rows, contact fields, identifiers or purported tenant claims. Original issuer, tenant and immutable forecast registration flags remain false.
2. Cached nonzero/tenant-bearing product snapshots from the unscoped refresh path are ineligible for reuse. They cause fresh source acquisition and quarantine rather than bypassing the guard. A clean zero-cohort OBSERVE cache may be reused for the previous maximum of 300 seconds.
3. `predictive_product_science_readiness.py` requires counts, source status, tenant nullity, no estimates, and explicit non-authenticated flags to agree before reporting the quarantine; `predictive_product_scientific_agent_review.py` recognizes this quarantine as a scientific source blocker, not eligible research.
4. Tests cover 50 spoofed global wins, no private-field persistence, cached unsafe forecast bypass attempts, empty source, contradictory custody claims, and scientific source handoff. **The tests are local fixtures, not original customer outcomes.**

## Exact original production writer drift (read-only verified)

`empire-predictive-observe source-gates` now compares the active source path declared by the original systemd service against the immutable release candidate. The checked original `/srv/empire_os/empire_os/predictive_intelligence.py` is a group-writable shared source file (mode `664` at this review) and its bytes differ from the isolated, tested quarantine implementation. This explains `source_scope_admission_status=null` from the old running snapshot. The diagnostic does not infer live systemd drop-ins are resolved nor that source-code equality would grant forecast or database authority.

`source-gates` supplies original/candidate SHA-256 digests and group-writable custody status, returns `ORIGINAL_SOURCE_OWNER_DEPLOYMENT_STILL_REQUIRED`, and never reads customer rows, mutates the production unit or edits source code. Production source-owner review should choose the exact commit `104338e68867` or its tested successor and install under an owner-controlled immutable service artifact; do not copy directly into a concurrent dirty shared checkout.

## Important deployment distinction

The patch is currently committed **only on the isolated Predictive feature branch** and included in its immutable OBSERVE review/release. The production timer is still pointed at the existing shared `/srv/empire_os` source; this patch does not modify that dirty checkout, systemd services or the canonical database. Accordingly this does NOT claim production refresh service is protected until the original owner separately reviews and integrates the patch or safely updates the service to exact tested bytes.

## Dedicated tenant-reader policy preflight (OBSERVE)

New `empire-predictive-observe tenant-evidence` runs the policy-only review in `predictive_tenant_outcome_reader_preflight.py`. No privileged fallback, no raw commercial SELECT, and no caller-asserted tenant context. It uses a dedicated connection **only when the owner has independently configured** the `EMPIREDB_TENANT_OUTCOME_READER_DSN` environment variable. The DSN must never be pasted into chat, checked into Git or written to logs.

Within a single read-only transaction the connection sets the `empiredb_tenant_reader` role and inspects authenticated PostgreSQL `session_user`, `public.empire_current_tenant_id()`, login and reader role capabilities, FORCE RLS, table SELECT rights and expected tenant SELECT policies for buyers, fulfilment orders, commercial events and commercial outcomes. Results contain only flags and missing prerequisites. Any full metadata match remains **review readiness only**—not verified RLS semantics, original outcome authenticity, settlement, tenant-access rights, registry freeze, or revenue.

The 018 migration currently provisions tenant-reader policies for `buyers`, `fulfilment_orders`, `commercial_events` and `commercial_evidence_registry`, but does not provision the equivalent policy for `commercial_outcomes` in that migration. The actual production metadata must be assessed separately; migration presence/absence alone cannot certify deployed DB state. No ALTER/GRANT/CREATE or policy changes are authorized by this read-only phase.

As run without a dedicated credential the correct status is `HELD_DEDICATED_TENANT_OUTCOME_READER_CREDENTIAL_MISSING`. Existing personal, owner or superuser credentials must NOT be substituted. The production DBA needs to perform an independent policy/grant/security review and authorize an existing least-privilege reader before any live metadata probe.

## Real, separately owned tenant reader required

- Existing DB/CRM owner must provide a dedicated least-privilege reader whose **authenticated session identity** binds one tenant and whose DB rows obey tenant policies. A caller-provided tenant ID, JSON `tenant_id` or digest is not sufficient. Reject cross-tenant orders and duplicates before any statistics.
- Verify original product id and catalog-version map, terminal win/loss authenticity, independent payment/fulfilment evidence for wins, exact outcome available-at timestamp and no retrospectively supplied labels.
- Existing Quant/Forecast Registry owner must provide original immutable **pre-outcome** conversion prediction registration/readback independently of the subsequent outcome. The existing `public.predictive_forecasts` registry metric `recognized_revenue_cents` must NOT be represented as a registered conversion-probability forecast.
- Only then can the existing Scientific Research Agent evaluate 20+ resolved past outcomes and 12+ true out-of-sample forecast/actual evaluations. Synthetic agent benchmarking remains research only.
- Existing owners must independently prove real customer identity, rights, commercial terms, settlement, actual costs and access entitlement before customer forecast delivery or Economic Memory promotion.

No payment, outbound, database DDL, role provision, automatic scientific training or production activation authorized.
