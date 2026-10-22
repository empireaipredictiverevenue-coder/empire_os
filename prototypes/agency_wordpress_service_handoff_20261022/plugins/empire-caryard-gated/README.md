# Empire Car-Yard Capability Demo (development plugin)

**Do not install in production.** This plugin is an isolated source prototype
for a potential Australian car-yard WordPress project. It is not a paid
customer engagement, a verified client case study, or a production booking
service. No installation or runtime activation has been carried out.

## Features implemented in source

- `eacy_vehicle` custom post type with WordPress editor, public **demo**
  listings, title, optional image, year, integer AUD asking-price field,
  and status (unverified/available/reserved/sold). All display has an
  explicit *unverified demo stock* notice.
- `[empire_demo_vehicles]` shortcode renders at most 12 published,
  escaped inventory entries. No sales, payment or checkout.
- An admin-only demo repair-slot endpoint:
  `POST /wp-json/empire-caryard-demo/v1/admin-slot-hold`
  with `slot_start_utc` as `YYYY-MM-DD HH:MM:SS`.
  A unique database key on the UTC start time prevents duplicate holds.
- The admin-only `GET /wp-json/empire-caryard-demo/v1/admin-slot-count`
  reports **only the aggregate count** of test slots. Neither endpoint
  accepts personal/contact data.

## Permissions and safe activation

All REST routes require an authenticated administrator with
`manage_options`. The repair-slot routes also require the **explicit,
disabled-by-default** configuration constant below in a *disposable,
authorised WordPress development environment*:

```php
define( 'EACY_DEMO_ADMIN_SLOT_TEST_ENABLED', true );
```

Do **not** set this on the Empire AI production server or any public
customer instance. A valid WordPress REST nonce and administrator
session are still required. The plugin's activation hook runs a database
migration that creates an isolated, prefixed demo slot table; it has
**not** been activated or run here.

The schedule is strictly fictional and UTC-only, bounded to 09:00–16:30
and 14 days, with 30-minute test increments. It is **not** a customer
service-time calendar, repairs intake, staff allocator or evidence of
business opening hours. It has no real customer booking route or
confirmation email.

## WordPress owner acceptance checklist

Only after separate authorised test infrastructure is available:

1. Install the plugin ZIP in a disposable WordPress 6.5+ / PHP 8.1+
   instance and verify activation/schema migration with `dbDelta`.
   Preserve installation logs, plugin and WP versions.
2. As an editor, create **fictional** vehicles, update metadata, test
   image uploads, listing limits, REST visibility, invalid negative
   years/prices, and permissions. Test logged-out listing and responsive
   output with the independent WordPress theme.
3. Attempt admin slot holds with the gate **disabled** and confirm
   403/permission denial. Verify anonymous, subscriber and editor roles
   cannot access admin-only routes.
4. In an authorised **test-only** configuration, enable the constant,
   authenticate as admin, and submit valid UTC slots using a REST nonce.
   Confirm invalid dates, past dates, out-of-hours, 14-day horizon,
   duplicated slots, rollback and concurrent reservation collisions.
5. Inspect DB table indexes and backup/restore; test MySQL concurrency,
   WordPress updates, timezone handling, admin activation errors and
   uninstall/data-retention behaviour.
6. **Before any customer booking**: confirm buyer identity and scope,
   live venue timezone/hours, slot ownership, public form consent,
   accessibility, privacy, spam/abuse limits, customer notification
   transport, secure PII handling, retention/deletion, opt-outs and
   response/booking-state semantics. None is implemented here.
7. Independently implement and validate real vehicle feed import,
   inventory ownership, image rights, status updates, search/filtering,
   checkout restrictions, dealer approvals and handover. No live
   inventory-feed integration exists.

**A plugin source package is not proof of a working WordPress installation.**
The separate Python/SQLite reference test confirms how unique-slot SQL
constraints behave under concurrent inserts; it does not execute the PHP
module or MySQL `dbDelta` schema. No production, buyer, CRM, network
marketing, billing or payment changes occurred.
