# EmpireOS WordPress car-yard — staged staff UI integration

**22 October 2026 | Private branch | Source candidate, not a runtime release**

Builds on the existing five-page WordPress block theme and the dormant vehicle/repair-booking plugin. No new CRM, website framework or orchestrator.

## Change

A protected WordPress administrator workbench has been added to the car-yard plugin. It is completely disabled by default. Its menu and admin-post handlers register only when **EMPIRE_YARD_STAGING_STAFF_UI_ENABLED** is explicitly true on an authorised disposable WordPress staging site. It requires manage_options, an authenticated staff ID, action-specific nonces, validated field types and a same-origin redirect. All holds and status changes use the existing booking store and audit transactions. The workbench shows recent synthetic booking IDs, bays, UTC times, status and valid transitions; no client identifiers, external messaging or payment method.

A supplied **empire_yard_staff_calendar** filter must configure the staging site's IANA timezone, weekday opening hours and blackout dates. Missing calendar configuration or unverified InnoDB tables and exact unique bay/slot index result in a read-only screen; no schema is installed implicitly.

## Validation and limitations

Repository tests cover static WordPress hooks, input handling, table-readiness checks, package integrity and prior regressions. The PHP booking harness contains synthetic-data tests; it is not a real MySQL concurrency test. There is no PHP, WP-CLI, accessible Docker daemon or verified existing WordPress instance in the connected EmpireOS user's environment. A local PHP executable elsewhere does **not** establish WordPress/PHP/MySQL integration on EmpireOS.

**Do not execute schema_sql() on production.** Next gate requires separately authorised disposable WordPress + actual MySQL/InnoDB, with the existing theme installed and two concurrent transactions tested against the bay/slot UNIQUE constraint. Browser validation for editor, inventory shortcode, admin nonce and staff screen, mobile/accessibility and backups is outstanding.

No EmpireDB writes, production deployments, outbound mail, public customer bookings, payments, live leads or marketplace bids.
