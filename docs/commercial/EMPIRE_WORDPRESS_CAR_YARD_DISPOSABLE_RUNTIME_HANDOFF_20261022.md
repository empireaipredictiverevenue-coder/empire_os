# EmpireOS — real WordPress PHP integration + private car-yard functionality

**22 October 2026 · Isolated development feature branch · production unchanged**

## What was actually run

The previously staged local-service WordPress block theme is no longer
source-only: it was loaded and activated inside an ephemeral, genuine
**WordPress 6.8.11 / PHP 8.3.33** runtime. The execution environment is
the official **WordPress Playground CLI 3.1.60**, hosted by the
user-scoped Node 22 executable using PHP WebAssembly and a disposable SQLite
database. It required **no Docker privileges, no global PHP, no MySQL
password, no EmpireDB access and no access to EmpireOS production services**.

The original theme is located at:

`prototypes/agency_wordpress_service_handoff_20261022/empire-local-services`

New isolated private plugin:

`prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard-private/empire-car-yard-private.php`

The original public buyer-demand review remains a noncontact research
receipt; **no customer, buyer, real vehicle or personal contact data**
was used in the test.

## Real PHP / WordPress runtime proof

The one-shot runner
`scripts/run_wordpress_car_yard_playground_20261022.py`
mounts the local theme, plugin and PHP integration tests to a **new
disposable WordPress instance** and runs 36 real integration checks.
The original evidence is captured at:

`docs/commercial/JEV_WORDPRESS_REAL_PHP_CAR_YARD_RUNTIME_20261022.json`

Major verified checks:

- WordPress core boot and discovery/activation of the actual Empire
  local-service block theme.
- Private `empire_vehicle` and `empire_repair` post types with
  administrator-only capabilities and no public post-type queries.
- Anonymous visitor denied private inventory and booking REST access;
  ordinary Editor user denied both inventory and vehicle-creation access.
- A fictional admin successfully created a WordPress inventory record,
  wrote/read back year and availability status through metadata and the
  admin-only REST endpoint.
- Sydney daylight-saving offset validation, local opening hours,
  minimum duration, invalid calendar date and past appointment rejection.
- A synthetic staff-only bay allocation persists to the disposable WP DB;
  overlapping intervals produce 409; adjacent slots are accepted.
- Admin cancellation persists; previously cancelled time can be
  reallocated; the synthetic single-resource mutex rejects a second
  request while locked.
- The temporary single-resource lock is released and checked after
  the booking test.

A full runtime test discovered two genuine integration errors and the
corrective changes are part of this release:

1. WordPress metadata sanitisation passes multiple hook arguments,
   so direct use of PHP's built-in `floatval()` caused a runtime fatal.
   It has been replaced by the bounded `empire_car_yard_sanitize_price`
   callback.
2. WordPress **meta** capabilities must not be mapped directly to the
   `manage_options` primitive. An initial capability mapping interfered
   with administrative authority. The final mapping retains native meta
   capabilities while binding the relevant primitive post-type
   capabilities to administrators only. Administrator and Editor checks
   now pass in the real runtime.

These are integration findings, not synthetic test assumptions.

## Product limits and execution gates

This is a **synthetic STAFF-ONLY private prototype**. It is **not** an
end-user booking site, online marketplace, booking SaaS, or working
production car-yard deployment.

| Area | Verified now | Still needed for client use |
|---|---|---|
| WordPress/PHP runtime | Boot, theme activation, 36 PHP checks | Stable authorised WP host and full release test |
| Private vehicle records | CPT, metadata, internal REST persistence | Pictures, real stock updates, public search/listings, role/content approval |
| Private repair booking | Staff-only synthetic slot writes, overlap, cancel, local DST | Real availability, multiple bays, holidays, idempotency, concurrency under production MySQL, cancellation policies |
| Privacy/customer intake | No public PII collection or mail | Actual consent, rights, verified owner privacy policy, security, retention |
| Client WordPress pages | Theme recognised/activated | Actual page creation, editor and browser rendering, responsive visual review |
| Hosting/security | Ephemeral WASM + SQLite | SSL, backups and restore, updates, hardened deployment/rollback |
| Commercial offer | No bid or customer contacts | Current buyer identity, eligibility, exact scope, signed payment/acceptance terms |

A `define('EMPIRE_CAR_YARD_SYNTHETIC_TEST', true)` switch exists
**only in the disposable PHP test script**. It is not set by the plugin,
the theme or the public site. Without that switch, booking modification
returns HTTP 403 even to a WordPress administrator.

The existing website/SEO and direct B2B Research owners should continue
towards a **verified client brief**, not use the original public project
listing as authority to submit bids or make delivery claims.

## Important browser-test safety finding

A separate HTTP-server smoke test was briefly attempted through Playground
`server`. The CLI bound its disposable listener to **all interfaces** on
test port 9477, rather than restricting the server to loopback; it
initially returned HTTP 502 while preparing. The listener was
**terminated immediately and confirmed stopped**. No public customer
content, credentials, or real bookings were served, and no test web
server remains active.

**Do not repeat an HTTP test** on this host unless the existing
infrastructure owner authorises and verifies an interface-bound,
firewalled, disposable test environment. The tested `php` command
does not open an HTTP listener.

## To rerun a clean test

The already-published one-shot review receipt is immutable; to obtain
fresh evidence, create a separately reviewed new receipt path/date.
The runner intentionally refuses to overwrite it.

```bash
cd /home/ubuntu/empire_worktrees/agency_wordpress_runtime_inventory_20261022

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m pytest -q tests/test_jev_wordpress_car_yard_playground_20261022.py
```

The one-time PHP-WASM runner used the source-pinned CLI package
`@wp-playground/cli@3.1.60`. The package showed Node-version
compatibility *warnings* for Node 22, but actually executed WordPress
6.8.11 / PHP 8.3.33 successfully. Avoid automatically updating the
runtime to an unreviewed Node/npm or WordPress version in production.

**Final status:** real development runtime and private-synthetic
vehicle/booking proof achieved. Public booking, client handover, visitor
browser rendering and live financial/outbound execution are all held.
EmpireDB, the production website, the customer CRM and payment
infrastructure have not been touched.
