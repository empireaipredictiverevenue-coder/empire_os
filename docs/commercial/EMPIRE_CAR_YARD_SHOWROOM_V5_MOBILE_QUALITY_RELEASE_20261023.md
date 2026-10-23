# Empire AI Agency — Atelier Motors V5 Showroom Quality and Mobile Audit

23 October 2026 | Actual original WordPress child-theme build | Feature branch only, production unchanged

## Product built

The existing React 19 + React Three Fiber/Three.js showroom has an upgraded **original procedural fictional GT**: seven-spoke alloy rims, glass side panels and pillars, sloping windscreen, bonnet detail, door handles, wing mirrors, chrome shoulder/sill trim, eight-element grille, slim headlamp DRLs, rear light strip and restrained studio lighting. The three camera options and three selectable finishes remain operational. No third-party vehicle mesh, branded manufacturer artwork, new animation framework, license-unclear stock photo, customer claim, payment or production service was introduced.

On smaller touch-screen viewports (640 px and under with coarse pointer), the site now displays a lightweight but interactive-looking CSS/Tailwind preview containing an accessible **Explore in 3D** control. React lazy-imports the real Three.js canvas **only after the visitor actively chooses 3D**. This saves an initial heavy JavaScript download and GPU startup for ordinary mobile visitors seeking inventory. Desktop remains interactive on entry, with viewport-based suspension when offscreen. Reduced-motion users keep the static preview and download no optional 3D chunk.

Visual QA exposed an actual initial-opacity problem in the mobile hero: headline and preview were initially invisible during the motion entrance, making a captured mobile page look blank. We changed mobile hero motion to **render text and 3D entry control visibly on React mount** while retaining desktop entrance motion. The final screenshot was inspected after this change.

## Real WordPress/MariaDB acceptance

The V5 stage was recreated using the **original WordPress 6.8.11 PHP 8.5.4 child theme + existing car-yard plugin + MariaDB**. All content was fictional, Chrome HTTP was loopback-only, and MariaDB used its private Unix socket. **71/71 browser checks passed**: desktop procedural canvas, side/front/three-quarter and paint selections, offscreen canvas release and resume, mobile hero visibility, 3D-on-tap, read-only synthetic inventory, admin WordPress branding updates and same-site contact destination, private staff hold/confirm/cancel, and restoring the original WordPress/MariaDB database and files with three booking audit events.

The existing WordPress, CRM, payment, outbound, MCP and database authority owners were not changed. No real customer bookings or production deployment occurred.

- V5 acceptance: `docs/commercial/EMPIRE_CAR_YARD_SHOWROOM_V5_MOBILE_A11Y_ACCEPTANCE_20261023.json`
- Original eager-loading control run: `docs/commercial/EMPIRE_CAR_YARD_SHOWROOM_V5_MOBILE_EAGER_BASELINE_20261023.json`
- V5 Chromium/screenshots: `docs/commercial/car_yard_react_browser_evidence_v5/`
- Runner: `scripts/premium_wp_v1/run_react_wordpress_design_v5.sh`
- Preview ZIP: `prototypes/agency_wordpress_service_handoff_20261022/dist/empire-yard-atelier-showroom-v5-preview.zip`
- ZIP SHA256: `a188379119dda9b96858c65b1938d1b4646fa7ec395fcb144b035c8b636ad204`

## Actual mobile lab results (do not reinterpret as live performance)

**Method:** one Chromium run per configuration, 390 px simulated touch/mobile, devicePixelRatio 2, 1.6 Mbps down, 150 ms simulated latency, CPU throttled 4x, cold cache, localhost WordPress/PHP server. Measurements used the browser Navigation Timing, Paint Timing, PerformanceObserver LCP candidate and resource timing. Neither run is a Lighthouse or WebPageTest audit, nor field Core Web Vitals. The unoptimised test server did not gzip JavaScript responses; the recorded `encoded_bytes` values are *uncompressed transfer sizes*, not a production-compressed delivery prediction.

| Measurement | V5 before mobile opt-in (eager scene) | V5 after mobile opt-in (preview, before tap) |
| --- | ---: | ---: |
| First Contentful Paint | 1,280 ms | 1,260 ms |
| LCP candidate after hydration/ready state | 5,604 ms | 4,812 ms |
| DOMContentLoaded | 4,124 ms | 4,100 ms |
| 3D scene requested during initial visit | Yes | **No** |
| Real 3D canvas active on initial visit | Yes | **No** |
| Initial heavy Three.js resource | 1,594,913 encoded bytes | **0 bytes / no request** |
| 3D requested and canvas ready after explicit tap | not tested separately | **Yes**, 8,139 ms scene-request duration in same simulated network |
| Mobile horizontal overflow | None | None |

This comparison is an observed *pair of single-run staging measurements*, not proof of a durable ~792 ms LCP gain. The measurable priority is to avoid downloading 1,594,913 bytes of optional code before consent to an interactive 3D experience on mobile. Real deployments must use appropriate cache/compression/CDN strategies and be measured on actual devices and network conditions before making performance promises.

## Targeted accessibility findings

The Chromium accessibility tree had zero unnamed non-ignored button/link nodes. Programmatic checks found one H1, one main landmark, named interactive controls and links, a skip link, live status messaging, and pressed-state semantics for finish selection. Computed hero text/solid-background contrast was **17.57:1** for main text and **12.37:1** for the highlighted text (well above 4.5:1). The reduced-motion browser produced no canvas or 3D scene request. The mobile hero display check verifies that headline and 3D opt-in are genuinely visible before screenshot.

This is a **targeted native Chromium audit**, not a certified WCAG 2.2 audit; professional axe-core/Lighthouse, screen-reader, focus-order, zoom and actual touch-device QA are still needed.

## Honest creative status

The improved car is still visibly a **stylised, procedural concept**, not a physically faithful premium OEM vehicle model. The collection panels are still graphic placeholders rather than independently licensed automotive photography. This V5 release improved the scene and made the mobile experience more practical, but **premium photographic imagery and professionally art-directed production car assets remain unfulfilled**.

Next website work: obtain an appropriate owned/rights-cleared photographic or 3D asset direction, add client-approved images through existing WordPress Media Library, further refine staging hero art direction, and perform Lighthouse/axe plus manual screen-reader/device QA. Keep the existing agency platform and original owner gates. No new CRM or integration stack.
