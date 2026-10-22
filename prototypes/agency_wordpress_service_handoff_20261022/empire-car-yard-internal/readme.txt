=== Empire Car Yard Internal Prototype ===
Contributors: empire-os-internal
Tags: internal, private-inventory, research-only
Requires at least: 6.5
Requires PHP: 8.1
Stable tag: 0.1.0
License: Proprietary internal capability prototype

CAUTION: This is an INTERNAL SOURCE PROTOTYPE, not a verified WordPress runtime,
public booking interface, customer site, payment integration or client handover.

== Description ==

The plugin defines a PRIVATE administrator-managed vehicle inventory post type
(empire_vehicle) with year, make, model, stock code, mileage, AU display price
and draft/available/reserved/sold/archived status metadata.

Staff-only WordPress REST booking routes exist but are disabled by default.
There is NO public booking, NO customer form, NO emails, NO consumer personal
data collection and NO payments. The booking model creates INTERNAL fictional
service-bay holds in 30-minute UTC slots; pending full WordPress, MySQL/InnoDB,
permissions, opening-hour/timezone and transaction-integration testing.

== Source deployment gates ==

1. Verify the plugin source ZIP and hashes from the reviewed worktree.
2. Provision a founder-authorised, disposable WordPress 6.5+/PHP 8.1+
   development environment. DO NOT install this on Empire AI production.
3. Back up the sandbox; install plugin, review granted administrator roles,
   check dbDelta creates the two InnoDB tables and unique slot index.
4. Validate actual wp-admin CRUD, private WordPress REST data visibility,
   capability and nonce/cookie/application-password authorisation.
5. Verify 2 competing staff reservations for the same bay/time: exactly one
   must succeed, the other must return a conflict, with no orphan rows.
6. Verify UTC daylight-saving interpretation, 30-minute slot alignment,
   future/past rejection, cancellation audit and different bays.
7. Only for an approved disposable test, temporarily define:
   define('EMPIRE_CAR_YARD_ENABLE_INTERNAL_BOOKINGS', true);
   in the sandbox wp-config.php. The feature must remain false elsewhere.
8. Test activation/migration/rollback and remove all synthetic records through
   an approved sandbox disposal process. No automatic production table drop.
9. Before ANY public booking: add real customer consent/data minimisation,
   retention, spam protection, operating hours, local timezone conversions,
   cancellation policy, notification delivery receipts, staff permissions,
   and independent security/privacy review.
10. Before ANY customer bid or commercial promise: verify buyer identity,
    current project scope, budget, WordPress proof, performance and handover.

== WordPress internal API (disabled until authorised) ==

GET  /wp-json/empire-yard/v1/internal/reservations
POST /wp-json/empire-yard/v1/internal/reservations
POST /wp-json/empire-yard/v1/internal/reservations/{id}/cancel

All routes require administrator manage_options AND explicit sandbox opt-in.
No unauthenticated route exists. No public vehicle-listing page exists.

Example of a purely synthetic INTERNAL booking body (not real customer data):
{
  "resource_key": "bay-1",
  "service_code": "inspection",
  "starts_at_utc": "2026-12-20T09:00:00Z",
  "duration_minutes": 60,
  "vehicle_id": 0
}

Source-level safety checks are not equivalent to PHP lint, runtime activation,
manual browser QA, SEO, public inventory delivery or production readiness.
