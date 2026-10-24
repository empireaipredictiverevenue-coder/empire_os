# Empire AI Agency — Atelier Motors V10: Model Failure Recovery and WCAG Audit

**24 October 2026 | Original WordPress child theme | Isolated agency feature branch | PRODUCTION HOLD**

## Actual engineering delivered

This release hardens the original WordPress/React/Three.js premium automotive agency demo, **not** a second platform or WordPress installation. The existing procedural model, meshopt-compressed high-detail 2.83 MB Khronos CC BY 4.0 derivative, three camera choices, paint swatches, photographer-credited WordPress Media Library imagery, client-editable branding and synthetic staff booking module are preserved.

**Failed Studio GLB recovery:** React's existing error boundary now returns from an unsupported/missing Studio asset to the original procedural concept, exposes an accessible status message, and disables further Studio attempts until a page reload. This avoids spinning on a corrupt source. No real customer model was used.

**Actual fault-injection proof:** `scripts/premium_wp_v1/browser_acceptance_v10.cjs` operates a fresh private browser tab against the genuine disposable WordPress 6.8.11 / PHP 8.5.4 / MariaDB stage, deliberately replacing the high-detail GLB HTTP request with a synthetic **503**. It verifies that the original concept is restored, the failed button becomes disabled, and only one GLB request occurs. All non-stage external requests are aborted and counted. The actual requests to Gravatar came from WordPress administration, not the agency model; **1 attempted / 1 blocked** in each of the fault and WCAG browser sessions. The failure is created only by request interception in an isolated browser, not by modifying the WordPress server or the actual GLB file.

## Accessibility findings and applied improvements

Bundled **axe-core 4.10.3** runs only inside `scripts/premium_wp_v1/vendor/` test tools (with the MPL 2.0 licence retained). It is **not** included in the WordPress theme ZIP, used as production JavaScript, or downloaded from a third-party runtime CDN.

A real automated WCAG 2 A/AA, 2.1 A/AA and 2.2 AA tagged run on the *390 px reduced-motion homepage* initially detected:

- Six low-contrast text nodes: two editorial section eyebrows, three feature-card index labels and one photo/IP disclosure line.
- Three landmark issues: the WordPress-generated duplicate skip link, the React skip link and the design-preview notice.

All six text styles were darkened using static Tailwind CSS v4 utilities (no custom CSS), the React skip link and design notice were moved into the existing header landmark, and the **duplicated WordPress skip link is suppressed only on the React homepage**, where the React header retains its own accessible skip link. WordPress's native link remains on interior WordPress pages.

**Final axe run: 27 assessed tagged rules, 26 passing, 0 confirmed automated violations.** One rule was incomplete: **38 colour-contrast nodes require manual assessment**, mainly over image/gradient backgrounds; these have **not** been falsely marked compliant. The scan did **not** cover WordPress admin, inventory, desktop 3D interactions, screen readers, dynamic focus order, browser zoom, real keyboard/touch devices, or full WCAG 2.2 certification.

## WordPress runtime receipts

- `docs/commercial/EMPIRE_CAR_YARD_FAILURE_A11Y_V10_BROWSER_ACCEPTANCE_20261024.json` — **105/105 Chromium assertions passed** on an actual isolated WordPress/MariaDB environment.
- Three synthetic booking events survived full database and files backup/restore. No customer bookings, outbound, payment, CRM or database changes to production.
- Includes all original V9 proof: 2.83 MB local Meshopt GLB only after visitor opt-in, Data Saver double-confirmation, model cameras/paint, V6 editorial photography, admin editable branding and safe contact route.
- `docs/commercial/car_yard_react_browser_evidence_v10/` — six SHA256-verified browser screenshots.
- `tests/test_empire_yard_failure_accessibility_v10_20261024.py` — source and receipt integrity tests.
- Archived V2–V9 receipts remain tied to their original historical Git revisions, not overwritten by this release.
- New preview ZIP: `prototypes/agency_wordpress_service_handoff_20261022/dist/empire-yard-atelier-resilience-v10-preview.zip`; **2,865,623 bytes**; SHA256 `c048ee40edcd800350cf68fab1232276146740e8a4a539f0e285b23733cef879`.

## Remaining authority and product gates

**No real-client release approval.** The actual physical iOS/Android GPU tests remain unavailable on connected EmpireOS (Matrox G200eR2 only); the read-only physical Chrome test runner from V9 is available but has never produced authenticated phone measurements. Khronos demo asset origin and CC BY licence are documented, but **the separate manufacturer trademark and actual client use rights have not been independently cleared**. Canonical site-grant/owner signing, managed secrets, security-owner approval and exact deployment rollback also remain outstanding.

Next deliverable is a real physical-device acceptance receipt plus signed model/media rights for one permitted non-customer test site, alongside manual a11y review of the 38 ambiguous contrast nodes and dynamic 3D controls. **Production stays HOLD**. No public deployments, live bookings, customer processing, CRM writes, revenue movements or outbound actions were made.

**One EmpireOS, one Smart CRM, one premium WordPress agency engine.**
