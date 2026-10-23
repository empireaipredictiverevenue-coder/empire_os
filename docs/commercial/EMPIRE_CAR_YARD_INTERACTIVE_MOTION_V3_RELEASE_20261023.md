# Empire AI Agency — Atelier Motors Interactive Motion V3

23 October 2026 | Implemented on original `feature/agency-wp-car-yard-private-20261022` branch | Production not deployed

## Website product improvements actually built

The existing Empire AI premium reusable WordPress child theme `empire-yard-atelier` now has a genuinely usable **React Three Fiber showroom configurator** with three camera views (three-quarter / side / front) and three fictional paint presets (ocean teal / champagne gold / arctic silver). Existing procedural car geometry, original brand concept and WordPress plugin are preserved. The vehicle is fictional; no manufacturer models, stock prices or customer claims.

The show controls are actual touch/keyboard accessible buttons with `aria-pressed`, named view/finish groups, focus styles and a screen-reader status announcement. Their state drives the materials and in-frame car rotation via the existing Drei/Three.js runtime, with **no added animation libraries or handwritten CSS**.

The hero now uses `React.lazy` / `Suspense` for the Three.js scene; the Vite library output is **native ES modules** with a separate scene chunk. WordPress 6.8 registers the entry through `wp_enqueue_script_module`; no external CDNs. The fallback renders while loading or when WebGL is unavailable, and reduced-motion preferences retain a static fallback. When the hero leaves the viewport, IntersectionObserver unmounts the WebGL canvas rather than burning GPU cycles; the scene returns on re-entry. Tab visibility also pauses the scene. All state remains within the existing WordPress child theme—**one product, not a standalone builder**.

## Measured build output — files, not user performance scores

| Bundle | Raw bytes | gzip bytes | Observed purpose |
| --- | ---: | ---: | --- |
| Historical V2 single IIFE JS (pinned at commit 9135648ca0) | 1,275,464 | 364,276 | Old eager-loaded React + Three scene |
| V3 module entry `dist/yard.js` | 34 | 54 | Imports main chunk |
| V3 main UI JS `dist/yard-main-4k6xnr3_.js` | 566,609 | 139,244 | Page React/Motion shell |
| V3 lazy 3D JS `dist/yard-ShowroomScene-DpibJcrU.js` | 1,588,915 | 341,609 | Loaded after in-view/React hydration and WebGL check |
| V3 Tailwind-generated `dist/yard.css` | 37,826 | 7,361 | Tailwind CSS only |

Initial module entry + UI JavaScript is approximately **139.3 KB gzip** rather than the previous **364.3 KB gzip** monolithic file; it removes the 3D bundle from the initial JS dependency chain, **not** necessarily from the page's total eventual downloads when the hero is on-screen. This is a build-output comparison, **not** a claimed measured LCP/INP/Core Web Vitals gain. Subsequent CDN/cache/server measurements and mobile Lighthouse runs are still needed.

## Real WordPress/MariaDB/browser acceptance

Executed `scripts/premium_wp_v1/run_react_wordpress_design_v3.sh` using disposable loopback WordPress **6.8.11**, PHP **8.5.4** and Unix-socket MariaDB. Chrome validated **40/40** checks, including React hydration, WordPress-native module loading, loading of the separate WebGL chunk, functional camera/paint controls, mobile no-overflow layout, hiding/unmounting the scene when offscreen, restoring it after scrolling, synthetic inventory cards/images, WordPress administrator login, booking hold/confirm/cancel and three audit records.

The same run backed up the isolated WordPress database and files and restored them successfully. All external browser requests were blocked. The original V2 **31-check acceptance** is retained separately as an immutable historical record pinned to commit `9135648ca0`; historical tests now compare its archived Git content instead of incorrectly asserting that our updated theme must remain unchanged forever.

**Receipt:** `docs/commercial/EMPIRE_CAR_YARD_REACT_MOTION_V3_BROWSER_ACCEPTANCE_20261023.json`. Four versioned visual screenshots reside in `docs/commercial/car_yard_react_browser_evidence_v3/`. New v3 tests are in `tests/test_empire_yard_motion_v3_source_receipt_20261023.py`.

## Scope and release boundary

The existing `empire-car-yard` booking plugin V0.3, synthetic inventory data, WordPress parent theme and canonical EmpireDB/Smart CRM/MCP owners are unchanged. No production deployment, genuine customer vehicle feed, live bookings, CRM write, public payment or outbound action. The design remains a client-agnostic internal demo, **not a completed customer brand**.

**Actual next website work:** screen-by-screen editorial visual QA against premium reference, device performance measurements, and a safe owner-approved WordPress theme design-setting interface to change client branding without editing JSX. Do not spend another cycle inventing MCP approvals when the website itself needs commercial polish.

## Installation preview (not a production release)

A self-contained WordPress child-theme ZIP has been packaged at \`prototypes/agency_wordpress_service_handoff_20261022/dist/empire-yard-atelier-motion-v3-preview.zip\`. It contains the WordPress child-theme files, generated Tailwind styles, entry module, main React module, lazy Three.js module and the existing inventory-enhancement script. It deliberately excludes Node dependencies, build-time source and any credentials. SHA256: \`6efc0d008f1743c13752d8abb91e6c1470105f8264afa0e101ef41ebc6299bbf\`.

This preview requires the existing \`empire-local-services\` parent WordPress theme and \`empire-car-yard\` plugin. Its installability and behaviour were proven by the isolated real WordPress browser staging test; it is **not** authorised for public deployment or offered as a branded customer site yet.
