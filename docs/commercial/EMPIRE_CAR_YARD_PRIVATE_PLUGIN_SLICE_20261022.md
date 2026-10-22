# EmpireOS — car-yard inventory plugin + booking rules (isolated candidate)

**22 October 2026 | Private prototype, no live customer fulfilment**

## Reused release

Base commit `687fb887b`, existing five-page local-services block theme unchanged. This increment is a **separate WordPress plugin source**, not a new website engine, CRM or orchestration stack.

## Implemented

- Administrator-only `empire_vehicle` custom post type, metadata fields (make, model, year, odometer, fuel/specification, inventory status), core WP editor title/body/featured-image support, classic metabox, nonce and capability-guarded saves.
- Fail-closed visibility: vehicle CPT is **not** directly publicly queryable, indexed or exposed to WP REST. The explicitly installed `[empire_car_yard_inventory]` shortcode provides a limited, escaped public listing with make/search filters, pagination and a same-page virtual detail view. Archived or unpublished vehicles are not displayed. Output labels all data fictional.
- **Pure PHP, non-persistent booking-rules module**: IANA timezone conversion, reject nonexistent/repeated daylight-saving local times, 15–480-minute durations, half-open interval conflict checks by workshop bay, and valid held/confirmed/cancelled/completed transitions. No booking collection endpoints.
- Deterministic offline ZIP builder with SHA-256 output, never overwrites existing ZIP.

## Limits that must not be misrepresented

WordPress/PHP/database runtime installation on the production server remains **unverified**: target host has no `php` or `wp` CLI, and Docker daemon access was denied at last check. PHP CLI lint and unit tests can run in an independent development sandbox; shimmed WordPress functions are **not** a WordPress runtime test.

**Not yet delivered:** WordPress Site Editor integration, authenticated live CRUD, responsive browser testing, backup/restore, live vehicle-image upload QA, booking persistence, conflict-safe concurrent database writes, working opening-hours/blackouts, public booking/notifications, customer privacy policy, acceptance/handover and verified commercial agreement. Booking is a rule-engine only; do not claim a customer-booking system.

**Operational controls:** no customer PII, public appointment submission, sends, payments, CRM changes, tenant writes, marketplace bids, production deployment, domain changes or unapproved capability grants. `manage_options` gates this demo to existing admins; no additional role is created.

## Next independently verifiable gate

1. Obtain an authorised disposable WordPress + PHP + DB runtime; install **existing theme ZIP** and **this private plugin ZIP**.
2. Confirm admin-only vehicle CRUD, featured-image role restrictions, permalink/read-only shortcode behaviour, search/pagination, status hiding and cross-theme compatibility in a real browser.
3. Implement staff-only booking persistence behind a serialised/concurrency-safe database constraint or transaction, with retained audit events, opening hours, blackouts and configured IANA zone; conduct concurrency and accessibility tests.
4. Only then prepare client handover evidence; separately verify original public buyer opportunities and seek approval before sending proposals.
