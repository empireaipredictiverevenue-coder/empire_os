# EmpireOS TAM recovery and enhancement — 10 October 2026

**Owner:** Existing TAM Market Intelligence + Revenue Completion Supervisor. **Mode:** OBSERVE. **No replacement agent, new timer, uncontrolled LLM retry, DB migration, service restart, outbound, payment or invented market sizes.**

## Live investigation and exact root causes

1. **Old LLM planning attempt failed 2 October, not today:** private job `runtime/coder_tam_lane/jobs/failed/coder_job_7f74cbe209d34dfa8734e4cc340b4231.json` ended at `2026-10-02T19:20:37Z`, attempts=3, error class `RuntimeError:ollama_request_failed:TimeoutError:max_attempts_exhausted`. This is model-plan history; it is not the canonical TAM market reader or evidence of ongoing production TAM request failures.
2. **The existing `empire-tam-coder-plan.timer` is enabled but idles:** natural systemd runs on 10 October reported `status=idle`, process exit 0; pending/running/completed queues are empty, one terminal failed job remains. Another job must not be blindly enqueued; no repeat inference and no extra worker/timer needed.
3. **Canonical runtime actually missing:** `runtime/tam_market_intelligence/latest.json` does not exist. The canonical implementation is already `empire_os/tam_market_runtime.py` → `public.get_tam_market_observations(integer)` under `empire_intelligence_materializer` → TAM Market Intelligence → optional research-only Radar input. Historic model job cannot substitute for this read.
4. **No visible TAM scope/DB reader injection into the ubuntu worker:** `EMPIRE_TAM_TENANT_ID`, `EMPIRE_TAM_ACTIVE_INDUSTRIES`, `EMPIRE_TAM_ACTIVE_COUNTRIES` and `EMPIRE_INTELLIGENCE_MATERIALIZER_DSN` were not exported into the inspected non-root process. The root-owned `/etc/empire_os.env` and `/etc/empiredb.env` are mode `0600`; their protected contents were **not readable** by that process, so their hidden contents have *not* been asserted empty. The existing TAM worker unit exports only PYTHONPATH and runs the idle model planner, not the deterministic TAM data reader. An explicit scoped read deployment is still needed.
5. **Database authority remains a separate gate:** migration `028_tam_country_evidence_restricted_reader.sql` is held per `docs/TAM_COUNTRY_EVIDENCE_READER_ARCHITECTURE_DELTA_V1.md`. A root PostgreSQL catalog probe was not permitted by the remote command policy during this check; no successful live restricted SQL function/role/grants readback has been established. Do **not** treat the migration file's existence or the generic materializer DSN as sufficient proof.

## Delivered and tested in the existing modules

- `tam_status()` now identifies `IDLE_HISTORIC_TERMINAL_FAILURE` versus genuinely `ACTIVE_PLAN_JOB`, preserves last terminal failure reason/date, and prioritises actual pending/running jobs over older completion/failure artefacts. It does not requeue old jobs.
- The existing Revenue Completion Supervisor now requires **canonical schema, restricted source identity, OBSERVE-only authority, explicit platform-research scope, actual generation timestamp and freshness (72h), validated market-count structure and negative commercial flags** before calling TAM available. A fabricated, stale, unsafe, future-dated or incomplete JSON is evidence unavailable, not TAM.
- Historical Ollama timeouts appear as **diagnostic history**, not a recurring market-data failure or blocker on an independently verified canonical TAM snapshot.
- Missing TAM runtime is reported with precise **configuration keys** and a protected reader/migration verification task. DSN values, tenant names and passwords are never printed.
- Canonical TAM builder adds UTC `generated_at`, retains source row counts, explicitly marks `PLATFORM_MARKET_RESEARCH_ONLY` and `tenant_source_scope_verified=false`. The current SQL reader is a platform company-market roster without a customer-tenant predicate; binding output to a research tenant must **never** imply customer login/RLS authority.
- Canonical TAM snapshot writes as owner-private `0600` and refuses unsafe destination symlinks.
- A source row bearing another tenant ID cannot be silently rebound. A contradictory company identity within one TAM scope fails closed, and a “verified” TAM market count must be a bounded, nonboolean integer, not a string/float.
- Observed companies remain **observed coverage**, never automatically promoted to Total Addressable Market, buyer intent, demand, offers, territory rights, allocation, payments or realised revenue.

## Exact remaining engineering/activation order

| Gate | Current result | Safe next proof |
| --- | --- | --- |
| Historic model timeout | **DIAGNOSED, TERMINAL** | Do not retry unchanged; keep event for review |
| Deterministic TAM code and tests | **PATCHED and tested** | Cross-module regression and current supervisor readback |
| Canonical TAM source function migration 028 and EXECUTE grant | **LIVE AUTHORITY UNVERIFIED / FOUNDER-GATED** | Approved DBA catalog preflight under read-only transaction; if migration missing, obtain explicit separate deployment approval, preserve backups and audit |
| Dedicated materializer service environment | **NOT PROVEN CONFIGURED FOR WORKER** | Authorised administrator verifies `empire_intelligence_materializer_login` DSN and explicit correct research-tenant/industries/countries configuration through protected systemd environment (never expose the values in chat or source) |
| Read canonical entities, legal territories and industry provenance | **MISSING RUNTIME EVIDENCE** | One bounded authorised restricted-role read via `tam_market_runtime.py --refresh`; confirm source row count, no mixed tenant, no invalid locale inference and 0600 snapshot |
| Downstream Opportunity Radar linkage | **NOT LIVE VERIFIED** | Supply the now-valid TAM snapshot to existing Radar as research-only opportunity classes; prove no customer demand or outbound authority inferred |
| Verified Total Addressable Market estimates by country and vertical | **UNKNOWN** | Separate genuinely verified industry/company population evidence with specific sector/country/methodology/observed date; never substitute our known company roster count |

**No actuation now:** no migration applied, no protected credentials read or changed, no model plan job requeued, no service restart/disable, no market totals invented, no outbound/payment/recognised revenue.

## Product-level success criteria

For solar, roofing, insurance/carriers, legal, SaaS, search and enterprise, TAM should provide a *separate* per-industry/country observed canonical-entity count, provenance/freshness, a genuinely verified independently sourced market denominator **where present**, observed coverage ratio only with valid denominator, and a research priority for real qualification. It should use our same buyer relationship/offer/payment pipeline to graduate to revenue; a market opportunity class alone does not become a buyer or a commercial forecast.

When the migration and scoped read credentials are approved and proved, finish the existing reader and Radar handoff—not an Ollama job retry.
