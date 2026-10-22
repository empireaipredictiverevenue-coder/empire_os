# EmpireOS — WordPress runtime and private car-yard inventory/booking continuation

**22 October 2026 · Isolated development release · Real runtime smoke, NOT client/production release**

## Business purpose and existing owner contract

This is continuation of the existing agency website build at commit `687fb887b`,
not a new website platform, CRM, customer-intake backend or scheduling agent.

Two original service requests motivated the code:
- A marketplace car-yard WordPress redesign listing with stock/booking scope.
- A US web agency seeking reusable WordPress local-service websites.

Neither original post has an independently established legal buyer identity,
signed order, agreed scope or guaranteed payment. **No bid or reply was sent.**
The 32,899 archived EmpireDB prospects, buyer records and public federal
procurements are unrelated to this test.

## Real disposable WordPress/PHP environment now verified

A nonprivileged `npx --offline @wp-playground/cli@3.1.60` invocation used
the **existing local npm cache**, not `sudo`, Docker privileges, global
PHP package installation or live web-host changes. Official WordPress
Playground CLI ran WordPress **6.8**, PHP **8.3**, internal SQLite and a
`127.0.0.1` only test server.

Original fixture:
`prototypes/agency_wordpress_service_handoff_20261022/playground-local-integration-blueprint.json`.

It mounted the existing `empire-local-services` WordPress theme and the
new `empire-car-yard-internal` plugin in a disposable WordPress site.
External networking in the Blueprint was disabled; test pages contained
fictional content only.

**Actual PHP/WordPress smoke receipt**:
`docs/commercial/JEV_CAR_YARD_PLAYGROUND_RUNTIME_SMOKE_20261022.json`.

- **Five** WordPress page URLs returned HTTP 200 with expected source-theme
  markup and demo text: Home, Services, About, Areas and Contact.
- WordPress registered the admin-only `empire_vehicle` custom post type.
- Anonymous GET and POST to internal booking routes, cancellation POST, and
  anonymous vehicle creation all returned **HTTP 401**.
- Contact form collection, booking and payment remained disabled.
- The smoke runner initially failed with an invalid empty POST body and an
  early readiness race; these checks were corrected to use a valid fictional
  payload **after** Playground printed `Ready!`. The final recorded
  run completed successfully. No unauthorised write was performed.
- The local server was terminated after the bounded test; no public URL,
  Cloudflare route or production site was changed.

## Vehicle inventory: PHP CRUD exercised in WordPress runtime

A **second disposable Playground** used
`playground-local-crud-blueprint.json`, created **one fictional vehicle**,
round-tripped status/year/make/price metadata, read it, updated its title,
then permanently deleted the fictional record.

Proof:
`docs/commercial/JEV_CAR_YARD_PLAYGROUND_INVENTORY_CRUD_20261022.json`.

Confirmed true:
- site administrator access
- custom administrator vehicle capability
- private vehicle post type exists
- WordPress PHP fictional create/read/update/delete and metadata roundtrip
- **zero** fictional stock records left after the test

This is real WordPress/PHP **admin-context API CRUD on SQLite**. It is
**not** a browser walkthrough of the WP Site Editor, user-role penetration
test, actual vehicle listings, MySQL integration or production delivery.

## Private car-yard plugin source implemented

Location:
`prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard-internal/`.

- Admin-only private `empire_vehicle` post type with WP REST-backed stock
  status (draft, available, reserved, sold, archived), model year, make/model,
  stock code, mileage and AUD display price.
- No public stock archive. No customer contact fields, card payments,
  WooCommerce, live enquiry intake or external message sends.
- Staff-only internal booking REST routes **disabled by default** via
  `EMPIRE_CAR_YARD_ENABLE_INTERNAL_BOOKINGS=false`.
- Even when separately enabled in an approved test sandbox, REST actions
  require `manage_options` and valid WordPress authentication.
- UTC-only, strict 30-minute slots with a 30–120-minute reservation length
  and a 90-day horizon. Slot claims use a unique
  `(resource_key,slot_utc)` database key. A failed claim rolls back
  the booking and slot inserts together. Cancellation releases slots but
  retains a cancelled booking audit record.
- PHP sources **require** InnoDB for the booking tables. That deliberately
  blocks booking actions in the tested SQLite environment instead of
  pretending transactional MySQL behaviour was tested.
- Only a synthetic SQLite reference canary tested the intended collision,
  rollback, multi-bay and cancellation invariants; that is **not**
  execution of the WordPress booking transaction in PHP.

The code is packaged in a deterministic, upload-shaped **internal source
ZIP** at:
`prototypes/agency_wordpress_service_handoff_20261022/dist/empire-car-yard-internal-prototype-0.1.0.zip`.

Verified release receipts:
`docs/commercial/JEV_CAR_YARD_PRIVATE_PLUGIN_CAPABILITY_20261022.json`.

## Feature/authority matrix

| Gate | Current evidence |
|---|---|
| WordPress 6.8 / PHP 8.3 user-space sandbox | **Executed successfully** |
| Theme Home/Services/About/Areas/Contact render | **Five real HTTP 200 checks passed** |
| WordPress plugin mounted and PHP loaded | **Yes, private CPT registered** |
| Anonymous admin-write and booking protection | **Four HTTP 401 checks passed** |
| Admin-context synthetic inventory CRUD | **WordPress API run passed; fictional record deleted** |
| Block-theme mobile and accessibility | Static styling tested; browser/device audit still needed |
| WP-admin Site Editor walkthrough, handover | **NOT TESTED** |
| Actual vehicle catalogue and front-end filter pages | **NOT IMPLEMENTED** |
| Admin booking SQL transaction against MySQL/InnoDB | **NOT TESTED** |
| Operating hours, local zone/DST, double-booking under concurrency | **NOT TESTED on real booking backend** |
| Live visitor booking, email, privacy, retention, spam/rate limits | **DISABLED / NOT REVIEWED** |
| Signed customer scope, delivery acceptance, payment | **0 verified** |
| Production/CRM/database writes, outbound, bids | **NONE** |

The WordPress internal SQLite runtime is **not** canonical EmpireDB
PostgreSQL and does not replace or migrate EmpireDB. Never run the plugin
against EmpireOS production DB or export EmpireDB prospect contacts into it.

## Next existing-owner implementation gates

1. Website engineering / Infrastructure: in a founder-authorised disposable
   **MySQL 8/InnoDB** WordPress test, verify `dbDelta` table structures,
   index uniqueness, two simultaneous staff slot requests, rollback of the
   loser, cancellation, read consistency, user permissions and safe
   activation/migration/restore. Do not bypass Docker or root access.
2. WordPress owner: test the admin vehicle editor and REST capabilities for
   administrator versus lesser roles; test uploads, status transitions,
   drafts/revisions, page front-end listings, image/legal asset rights and
   responsive mobile preview.
3. Booking/privacy owner: define real business opening hours, jurisdiction
   timezone and DST, public visitor consent, cancellation, customer identity,
   rate limits, abuse controls, retention, and permissioned delivery receipts
   **before** any public booking route can be authorised.
4. QA/security: instrument PHP test coverage, WordPress coding standards,
   static and dynamic vulnerability checks, backups and rollback. The source
   static tests alone are not a security certification.
5. Research / Buyer Scout / Founder: reconfirm the direct public requests
   and legal buyer, true availability, budget, exact written deliverable,
   milestones, and allowed application channel. Seek a separately approved
   proposal only after demonstrable fulfilment and source-rights verification.

**No production changes, no WordPress customer installation, no public
appointments, no emails, no orders, no money movement and no paid traffic.**
