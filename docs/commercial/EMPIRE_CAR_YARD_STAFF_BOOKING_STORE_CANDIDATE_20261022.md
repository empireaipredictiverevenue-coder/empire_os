# EmpireOS car-yard — staff-only booking persistence candidate

**22 October 2026 | Isolated feature branch | Not deployed**

This is a source-only addition to the existing WordPress car-yard plugin. No database table has been created or modified, no booking submitted, and no WordPress/PHP runtime verified on EmpireOS.

## Included

- Dormant WordPress-compatible booking store with administrator-authorised holds and status changes.
- Explicit InnoDB schema preview for bookings, append-only audit events, and **unique (bay, slot_utc)** 15-minute occupancy records. The preview is **not run automatically**.
- Per-bay MySQL advisory locking, transactional writes, conflict checks and rollback on failures; database uniqueness guards overlaps even if the advisory lock is lost.
- Configurable opening hours, blackout dates and existing IANA/DST conversion rules; no hours configured means bookings denied.
- Synthetic staff user IDs for internal audit only; no public booking interface, customer details, notifications, marketplace bids, payments or CRM updates.

## Verification boundary

Offline PHP syntax checks and a PHP **fake-database harness** exercise permissions, overlap denial, cancellations, unique-slot collision and audit failures. Python source checks run on the connected EmpireOS worktree. Neither type of test verifies WordPress, actual MySQL concurrency, schema migration, Site Editor or the browser.

Do **not** install the plugin or execute its DDL on production. Next gate: separately authorised disposable WordPress/PHP/MySQL (InnoDB) environment; validate WordPress admin inventory, schema compatibility and two real concurrent MySQL sessions, then implement a protected staff-only booking UI, backup/restore, retention and client acceptance. The live Empire AI site remains unchanged.
