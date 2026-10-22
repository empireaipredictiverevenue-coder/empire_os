# EmpireOS V0.3 — verified WordPress and MariaDB evidence

22 October 2026 | Isolated engineering branch | No production deployment.

Base branch: feature/agency-wp-car-yard-private-20261022. Existing five-page empire-local-services theme and empire-car-yard plugin preserved. This work adds runtime evidence and reproducible tests, not another plugin.

## Evidence A — genuine WordPress integration

Official WordPress Playground CLI 3.1.60 booted WordPress 6.8.11 / PHP 8.3.33, installed and activated the actual V0.3 plugin using WordPress's activate_plugin API, and activated the original block theme. The disposable SQLite-backed WordPress instance passed 29 of 29 PHP checks.

- Nonpublic vehicle custom post type and restricted REST/search visibility.
- Administrator allowed; synthetic Editor and anonymous user denied inventory writes.
- Fictional vehicle created; year and status persisted through native WordPress metadata.
- Anonymous fictional demo-stock listing and detail displayed, archived vehicle hidden.
- Staging-only staff handler registration, public submission absence.
- With no InnoDB tables, staff page displayed changes disabled, withheld the hold form and avoided querying booking tables.

Original source hashes and results: docs/commercial/EMPIRE_CAR_YARD_V03_PLAYGROUND_RUNTIME_20261022.json.

## Evidence B — real simultaneous MariaDB bookings

User-scoped MariaDB 11.8.6 / InnoDB used a protected Unix socket with networking disabled, no sudo, no global packages and no Docker privileges. Native PHP 8.5.4 executed the actual Empire_Yard_Booking_Store implementation through a WPDB-shaped adapter; two separate PHP processes were synchronised at a filesystem barrier.

- Attempt A accepted booking ID 1. Attempt B rejected the conflicting same-bay same-time request.
- The real database contained exactly one booking, four quarter-hour occupied slots and one audit event.
- Cancelling freed the slots; a new booking for the same interval succeeded.
- After cancellation/rebooking: two historical booking rows, four active slots, three audit events.

Original source hashes and results: docs/commercial/EMPIRE_CAR_YARD_V03_MARIADB_CONCURRENCY_20261022.json.

The test was rerun using the create-only, user-scoped runner in scripts/run_empire_yard_disposable_mysql_v03_20261022.sh. Its temporary database was verified removed afterward; no MySQL TCP listener was left behind. Do not run under elevated privileges or connect to EmpireDB.

## Acceptance boundary

These proofs are separate and complementary. WordPress ran on disposable SQLite, while the true concurrent booking-store test ran against real MariaDB. The complete WordPress-on-MySQL staff UI has NOT been browser-tested or deployed.

Still pending: full native WordPress/PHP/MySQL integration on approved isolated hosting; rendered desktop/mobile/keyboard and Site Editor verification; client-like admin/staff sessions; image upload testing; full WordPress site and database backup/export and restore with parity; real stock feeds, consent/privacy policies, handover and client acceptance.

No EmpireDB or Smart CRM writes, no production site deployment, real customer bookings, outbound, payments or marketplace bids. No paid or settled customer is implied.
