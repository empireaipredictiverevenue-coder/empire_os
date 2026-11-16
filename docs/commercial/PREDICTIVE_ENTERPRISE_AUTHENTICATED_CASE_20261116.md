# Authenticated CRM revenue diagnostic

The existing enterprise diagnostic now has an additive path from the original signed CRM reader. A signed-in CRM member can open `/v1/revenue-crm/predictive-diagnostic/app`; the page uses the existing CRM login endpoint, keeps the short-lived bearer only in page memory, and calls the diagnostic JSON route with that bearer.

The request reuses the current `crm_search_additive_20261109.entrypoint.resolver`, `AuthenticatedRevenueCrmRead`, the existing dedicated tenant PostgreSQL login, and `PostgresRevenueCrmRepository`. PostgreSQL rechecks the tenant binding and read-only role. The bounded view is capped at 500 CRM prospect records and reports aggregate link, price and probability coverage. It omits row details and tenant identifiers. Empty and truncated snapshots remain explicit source-coverage holds.

The route also builds the existing enterprise diagnostic report and passes the result through the original enterprise HTTP guard for JSON, HTML and Markdown. That guard continues to enforce the internal unverified-draft status, zero verified findings and disabled customer delivery. CRM rows do not establish financial finality, forecast calibration, conversion rates or release authority.

## Routes

- `GET /v1/revenue-crm/predictive-diagnostic/app` — authenticated CRM diagnostic page shell.
- `GET /v1/revenue-crm/predictive-diagnostic/app.js` — browser code; the access token is held in memory only.
- `GET /v1/revenue-crm/predictive-diagnostic?limit=500` — tenant-scoped diagnostic report JSON.
- `GET /v1/revenue-crm/predictive-diagnostic/preview?limit=500` — original guarded HTML report.
- `GET /v1/revenue-crm/predictive-diagnostic/markdown?limit=500` — original guarded Markdown report.

The proposed entrypoint wrapper preserves the currently active Data Cloud browser overlay, CRM app, signed resolver, systemd credentials, package paths and loopback listener. It adds these routes to the same process. The proposed unit drop-in changes only the existing CRM `ExecStart` to the reviewed versioned overlay. It does not add a database role, service, listener, schema or scheduler.

## Verification and production state

The focused CRM API, tenant transport and diagnostic checks passed on the established PR branch (46 passed). Changed Python modules compile, and `git diff --check` is clean. The tests exercise the original repository checks with isolated fixtures; they are not production customer observations.

At 2026-11-16 19:26 UTC, the original dedicated CRM database login authenticated and its tenant-bound, read-only repository returned zero prospect records. The adapter reports `CRM_SOURCE_EMPTY_UNKNOWN_COVERAGE_HOLD`; it does not treat the empty view as a full tenant census. The source cannot establish financial finality or customer release. This is consistent with the founder's statement that Empire AI has no sales; it does not prove whether customers have records outside this CRM view.

The reviewed release was staged inactive at `/opt/empire-ai/predictive-enterprise-crm-20261116-v1` from commit `bbc5a57b9e5c992c0fb271420181521bd8f05be4`. Under the current CRM process mount and environment, the staged app imported successfully; the page and script returned 200, and anonymous plus forged-tenant report requests returned 401 before database access. This was an isolated app-process check, not a live service route or authenticated customer report.

The live CRM service remains on its existing pinned release. No unit file was installed and no CRM service restart was performed. The native forecast registry remains empty. No customer forecast, recognized revenue, calibration result or source completeness is claimed.
