# EmpireOS car-yard V0.3 — native WordPress + MariaDB browser and restore acceptance

**22 October 2026 | Isolated development branch | No live client launch**

## Authoritative new result

The existing native WordPress 6.8.11 theme and V0.3 car-yard plugin were installed together into a **fresh, disposable, user-owned WordPress/PHP 8.5.4/MariaDB 11.8.x environment**. Unlike previous separate WordPress Playground/SQLite and standalone MariaDB tests, this test exercised the **same WordPress application against real InnoDB**.

The staging runner used official WordPress 6.8.11 files, temporary extracted PHP/MariaDB distributions, a **MariaDB Unix socket with --skip-networking**, and a PHP HTTP listener bound explicitly to **127.0.0.1 only**. Chromium/Puppeteer interacted only with loopback. All external browser network requests were intercepted and blocked. WordPress remote HTTP was disabled. All test users, stock, appointments and site content were synthetic.

### Observed evidence

The structured receipt is **docs/commercial/EMPIRE_CAR_YARD_V03_NATIVE_WP_MYSQL_BROWSER_RESTORE_20261022.json**, checked against screenshots and source hashes.

- Native WordPress installation succeeded; V0.3 plugin activated; original block theme activated.
- Six test pages created (Home, Services, About, Areas, Contact and Synthetic Stock).
- One synthetic vehicle saved, metadata persisted, synthetic image attached and rendered.
- Actual browser checked home desktop width 1440 and mobile width 390: no horizontal overflow.
- Staff administrator logged in and submitted a nonce-guarded synthetic hold, then confirmed and cancelled it.
- The **22/22 browser assertions** passed, including desktop/mobile page loads, image display, keyboard focus, permitted staff controls, booking status receipts and absence of server HTTP 5xx.
- WordPress attempted six external browser requests; **all six were intercepted/blocked** and none was allowed through the test browser.
- Full source tree archived as a tarball and real MariaDB data exported as SQL. Both restored into new temporary locations. A separate WordPress/PHP read-back verified the active theme, WordPress pages, vehicle metadata and restored image, plus **one historical booking and three booking audit events**.
- Source tree, screenshot PNG hashes, SQL backup hash and website archive hash were recorded. The temporary stage, database, credentials and listener were deleted at the end; no residual test directory was found.

The browser screenshots are in the adjacent **docs/commercial/car_yard_v03_browser_evidence/** folder:
home-desktop.png, home-mobile.png, stock-mobile.png, staff-desktop.png.

### Visual QA judgement

The screenshots show the existing theme is clear, responsive and functionally navigable but **visually minimal**: plain text-led blocks, sparse brand styling, WordPress-standard staff forms and explicitly fictional copy. This is proof of delivery capability, **not** a premium branded car-yard product or a client-ready website. The staff interface is private and staging-flagged. No public repair booking, notifications or payment route is enabled.

### Repeat safely

The one-shot rootless integration runner is:

  bash scripts/native_wp_v03/run_disposable_native_wp.sh

It refuses a different branch/user, uses a unique protected temporary directory, generates synthetic credentials, binds the HTTP listener to loopback, uses a private MariaDB socket with TCP disabled and tears down both child processes on exit. It refuses to overwrite an evidence receipt or screenshots. Only run on an authorised development host with the cited disposable package dependencies, never on a client or EmpireOS production service. A rerun needs a fresh versioned evidence destination rather than overwriting historical evidence.

The run does **not** modify EmpireDB, the production public website, tenant Smart CRM, buyer inbox, outbound, payments, DNS, firewall or systemd. No customer data or payments were processed.

## Remaining before any commercial delivery

Independently verify client scope/rights and a real buyer. Replace demo text/imagery with licensed client assets, build approved public repair-intake with consent/privacy/retention and anti-abuse controls, refine premium visual branding, verify Site Editor and real user onboarding, complete WCAG/accessibility and live hosting/TLS/upgrades/rollback/handover QA, and receive client acceptance. No marketplace bid, warranty, delivery promise or payment settlement is authorised by these development tests.
