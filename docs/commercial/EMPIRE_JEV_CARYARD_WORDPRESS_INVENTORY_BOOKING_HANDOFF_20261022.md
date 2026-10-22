# Jev / Website Engineering — car-yard WordPress inventory and repair-slot proof

**22 October 2026 · Isolated dev branch · Security/default mode: DISABLED FOR CUSTOMER USE**

## Existing commercial trigger

Empire Research identified a public request for an Australian car-yard
WordPress redesign with vehicle stock listings and repair booking:
https://www.freelancer.com/projects/web-design/vibrant-car-yard-web-site

The publicly advertised budget (A$250–750) is not a signed contract,
project award, validated company identity or guaranteed payment. The
original post's current availability, asset ownership, specific booking
rules and consent requirements are unverified. No application or proposal
was submitted. This work also does not establish a previous WordPress
client-delivery case study.

## Reuse rather than rebuilding

The earlier website-owner branch `feature/agency-wp-handoff-capability-20261022`
provided a **13-file WordPress local-service block-theme source** and
offline ZIP, but never ran PHP, WordPress or client handover.

The current increment adds a **separate inventory + administrator-only
repair slot source plugin**, rather than reusing EmpireDB CRM or the
33k historical prospect reservoir.

Plugin directory:
`prototypes/agency_wordpress_service_handoff_20261022/plugins/empire-caryard-gated/`

Plugin offline package:
`prototypes/agency_wordpress_service_handoff_20261022/dist/empire-caryard-gated-demo-plugin-0.1.0.zip`

## Inventory source prototype

- Registers `eacy_vehicle` custom post type, editable only through normal
  WordPress post/editor capabilities; public **demo** listings include
  a prominent unverified inventory caveat.
- Editor metadata fields: integer model year, integer AUD asking price and
  unverified/available/reserved/sold dealer-supplied status.
- Source code bounds prices/year, rejects invalid/negative values, and
  escapes links, titles, dynamic content and labels.
- WordPress shortcode `[empire_demo_vehicles]` lists at most 12 **published**
  vehicle posts. No checkout, financing, test drive, sales lead collection,
  real dealer stock feed or price-verification API.

This source was statically validated but **not executed in WordPress**.
No real vehicle was added or shown to an actual customer. Inventory-feed
authenticity, uploads, permissions, search/filtering, status consistency
and public REST visibility remain untested.

## Repair booking source prototype: purposely non-customer-facing

- Plugin activation on a **separately authorised disposable WP instance**
  would create a prefixed `eacy_repair_slot_locks` table, with a **unique
  `slot_start_utc` key**. **No migration was run on EmpireOS.**
- An administrator-only test route accepts a strict UTC 30-minute
  fictional start slot within 14 days, limited to 09:00–16:30 UTC.
- The route is **off by default**, and requires explicit demo-only
  constant `EACY_DEMO_ADMIN_SLOT_TEST_ENABLED === true`,
  `manage_options` permissions and authenticated WordPress REST.
- The atomic `INSERT IGNORE` plus unique key is intended to reject
  duplicate slot holds (HTTP 409); no SELECT-before-INSERT race.
- A separate, similarly admin-gated route reports only aggregate test
  slot counts. It does **not** store customer names, phone numbers or
  emails; no contact route, calendar sharing, marketing or fulfilment.
- No real opening hours, customer timezone, venue availability, staff
  allocation, notifications, personal-data consent, spam limits or
  public booking UI have been implemented. This **cannot** be offered as
  a complete online booking feature.

## Tests and what they prove

The new read-only source auditor checks the admin-only routes, disabled
public gate, vehicle editor metadata/shortcode constraints, output
escaping, and unique-slot DDL/insertion intentions.

An **independent disposable SQLite reference model** executes concurrent
attempts for one fictional slot: 10 attempted inserts -> 1 recorded
hold, 9 rejected. The model represents the database uniqueness property,
**not WordPress PHP or MySQL runtime execution**.

The immutable audit receipt is:
`docs/commercial/JEV_CARYARD_INVENTORY_BOOKING_STATIC_PREFLIGHT_20261022.json`.
It pins SHA-256 digests of the original plugin source files and the
parent WordPress theme preflight. Packaging the plugin is deterministic
and refuses overwrites.

**Runtime truth at this milestone:** PHP CLI, wp-cli and an accessible
Docker daemon were unavailable to the `ubuntu` execution context on the
EmpireOS server. We have not installed WordPress, enabled Docker access,
installed PHP/plug-ins, activated database migrations, linted the PHP on
that server, exercised wp-admin, tested the native MySQL unique index,
rendered a customer browser session or run a true booked repair.

## Owner's next executable integration test — needs authorised sandbox

1. Use an **authorised disposable** WordPress 6.5+ PHP 8.1+ MySQL instance;
   do not repurpose `/srv/empire_os` or the production public site.
2. Run **PHP lint** on all three source PHP files, then install the
   WordPress theme ZIP and the new plugin ZIP in that environment.
3. With the demo gate **disabled**, verify the routes are forbidden to all
   roles, including administrator; inspect the plugin activation schema and
   unique index. Track any tables created in that sandbox.
4. With a separately approved test constant, authenticate as admin and
   send valid future UTC slots. Verify invalid, past, out-of-hours, crossed
   horizon, duplicate, parallel and DB-unavailable outcomes; confirm
   expected 201/400/409/403/503 responses.
5. Test vehicle post editor/REST permissions across administrator/editor/
   subscriber roles, metadata sanitization, the 12-item listing cap,
   WordPress image upload and the logged-out view at mobile sizes.
6. Test integration with the theme, sitemap/SEO, wp-admin Site Editor,
   performance and keyboard/screenreader usability.
7. Obtain independently verified car-yard venue booking requirements,
   timezone, availability, customer-consent/privacy/retention, notification
   destination, refund/cancellation rules, staff calendar and real stock
   feed before writing any public repair-booking intake.
8. Require a real business counterpart, open buyer request, exact
   specifications and approved contract/payment terms before founder
   approves an application or delivery promise.

**Protected:** canonical EmpireDB, buyer CRM, existing agents, systemd,
Gmail, website production, financial gates and the unrelated government
procurement lane remained unchanged. No external paid traffic, outreach,
client deliverable, actual bookings or funds moved.

**Decision:** WordPress source + isolated SQL-reference test advance the
engineering capability. **Client runtime, public booking and commercial
proposal remain HOLD.**
