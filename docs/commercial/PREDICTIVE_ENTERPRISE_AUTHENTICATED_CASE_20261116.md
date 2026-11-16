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

The existing focused CRM transport, API and diagnostic HTTP checks passed in the isolated source worktree before the page and release wrapper were added (60 passed). They exercise the original repository’s tenant and login checks with test doubles. They are not production customer observations.

Production CRM deployment remains on the existing pinned release until the founder approves this exact CRM entrypoint activation. The live CRM service has not been restarted for this integration. The known production forecast registry remains empty, and the user has stated that Empire AI has no sales yet. No customer forecast, recognized revenue, calibration result or source completeness is claimed.
