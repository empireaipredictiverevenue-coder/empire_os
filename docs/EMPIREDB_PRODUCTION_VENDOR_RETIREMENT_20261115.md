# EmpireDB-only production runtime — bounded vendor retirement

**15 November 2026 | Original EmpireOS / Empire Data Cloud | Code reviewed and tested, no service restart or database migration**

## First-party verified state

- Founder ran `scripts.probe_predictive_original_source_catalog_readonly --read-only` on first-party EmpireDB: correct database and tenant resolver are present; REV052 authenticated single-event login and reader exist. `public.predictive_forecasts` **absent**, `empire_predictive_registry_reader` **absent**, FORCE RLS unavailable for that absent table, and `public.read_predictive_revenue_day_v1(date,text)` **absent**. These are first-party catalogue facts, not a zero-row forecast census.
- Existing `runtime/data_cloud/health_latest.json` reported `canonical_backend=empiredb` with explicit environment source. That same snapshot reported `candidate_runtime_healthy=false`, `operational_cutover_ready=false`, and `production_cutover_authority=false`. Do not infer all resilience/failover gates are cleared merely from backend selection.
- September `runtime/data_cloud/cutover_manifest_latest.json` still labels `supabase_legacy`; it is historical and conflicts with the newer explicitly-selected backend snapshot. It is **not** live production backend authority.
- The existing direct vendor-coupling audit found **0 hard direct vendor hits** in business-runtime modules, but **215 compatibility hits**, plus classified historical/recovery exceptions. No claim that all legacy source names or compatibility code have disappeared.
- The legacy Supabase containment timer remained enabled on 15 November; it was **not disabled or restarted**. It is a migration/rollback control, not evidence of Supabase being the canonical business store.

## Bounded correction

`empire_os/canonical_data_gateway.gateway_from_environment()` already defaults to `empiredb`. It previously allowed an explicit `EMPIRE_DATA_BACKEND=supabase_legacy` to construct a live Supabase provider from environment credentials. This unreviewed production fallback is now refused. An explicit **injected** `legacy_provider_factory` remains supported solely so the existing read-only rollback simulation and tests can preserve history without opening a vendor endpoint.

No environment/credential change, DNS action, service restart, payment, outreach, database write, migration or destructive deletion is authorised by this source patch. This is **not** a completed global Supabase retirement: remaining compatibility paths must be reconciled against owners and consumers, not globally string-replaced.

## Direct next owner actions

The canonical Predictive Revenue registry and day-source capability must be designed, reviewed and installed under **EmpireDB PostgreSQL 18**, with trusted session-user tenant binding, force-RLS and independent financial custody. Never apply the old Supabase migration directly to EmpireDB; its `anon`, `authenticated`, `service_role` and default permissions do not match the original EmpireDB authority model. Do not manufacture historical forecasts, backdate original predictions, or infer account settlement from one event. Live schema deployment requires the existing DBA and founder release gates.

Separately, investigate the parked voice-switchboard `canonical_database=supabase` label and private capital `source=canonical_supabase` marker, old PostgREST-shaped adapters, and historical Supabase egress timers through their owning subsystems. Changing labels without verifying their actual source would conceal rather than remove an active dependency.
