# Empire AI Agency — Client-Configurable WordPress Branding V4

23 October 2026 | Premium agency product build | Isolated original agency feature branch

## Real product built

The original `empire-yard-atelier` React/Three.js WordPress child theme now includes a **WordPress-native Appearance → Showroom Branding** settings page for site administrators. They can change the **display brand, strapline, hero eyebrow, headline, highlighted words, description, contact button label and internal contact-page path**, as well as choose among **champagne gold, arctic ice and warm copper** palettes.

Each field is saved through the native WordPress Settings API (`settings_fields` / `options.php`, capability `edit_theme_options`), sanitised on save, length-bounded and escaped on output. The contact path accepts only a short, same-site relative route; attempted external URLs were rejected during real browser testing. The React homepage reads a script tag of `type="application/json"` with JSON hex escaping and renders brand strings as text, not HTML. Settings are not exposed through a new REST API. No brand data is embedded in compiled JS; **changing presentation values does not require rebuilding React**.

The interior `/demo-stock/`, services and standard WordPress pages no longer use hardcoded `ATELIER MOTORS` header/footer text. Their WordPress block-template parts execute two small child-theme shortcodes, which read the **same** sanitised WordPress option and escape values. All styles remain generated from Tailwind CSS v4; the build scans the theme PHP source and does not add custom CSS. The native parent theme, existing inventory plugin and booking/CRM/MCP contracts are unchanged.

## Verified browser result

`scripts/premium_wp_v1/run_react_wordpress_design_v4.sh` created a disposable WordPress 6.8.11 + PHP 8.5.4 + MariaDB environment. In Chromium, the administrator logged into the original WordPress back office, opened the branding settings page, changed the fictional `Atelier Motors` concept to **Northstar Concept**, saved the changes using WordPress's actual settings flow, and reloaded the React homepage. The updated name, tagline, hero text, ice palette and contact label were visible. An attempted off-domain `https://malicious.invalid/collect` contact URL was rejected and reset to `/contact/`.

The same test visited the **real stock page after changing the brand** and confirmed the updated brand name, colour, internal contact link, footer and unchanged synthetic inventory. It retained earlier native browser checks covering responsive layouts, Three.js interactive controls and lazy loading, offscreen WebGL suspension/re-entry, staff booking hold/confirm/cancel and complete WordPress/MariaDB backup/restore.

**58/58 Chromium browser checks passed**, with three booking audit records confirmed after restore. The staging site was loopback-only, MariaDB used a private Unix socket and browser external requests were blocked. No live customer data, production deployment, payment, CRM write or outbound action occurred.

- Immutable evidence: `docs/commercial/EMPIRE_CAR_YARD_BRANDING_V4_BROWSER_ACCEPTANCE_20261023.json`
- Screenshots: `docs/commercial/car_yard_react_browser_evidence_v4/`
- Regression: `tests/test_empire_yard_branding_v4_source_receipt_20261023.py`
- Ready-to-review ZIP: `prototypes/agency_wordpress_service_handoff_20261022/dist/empire-yard-atelier-branding-v4-preview.zip`
- ZIP SHA256: `efcd4c55c7de3d4d12ffe6f0830634c164bfaee87e86abdd2172e51db905d063`

## Delivery constraints and next real product work

This is a configurable **fictional WordPress child theme preview**. It needs the existing `empire-local-services` parent theme and `empire-car-yard` plugin. WordPress options in this demo apply to the installed website, not to independent EmpireOS SaaS tenants; multi-client isolation still means separately provisioned WordPress instances and domain/site authority.

No pricing, stock availability, customer booking or conversion claim has been invented. The site has no externally published enquiry form, payment flow or real customer identity. No production server was changed. Existing EmpireDB, Smart CRM, MCP and other agents are unchanged.

**Next commercial website sprint:** visually review the actual desktop/mobile screenshots, improve the original car model and editorial imagery, run Lighthouse / accessibility checks on the real staging pages, and add controlled client-specific media/imagery through existing WordPress media capabilities rather than building a new platform.
