# EmpireOS Car-Yard — React / Three.js Premium Showroom v0.2

22 October 2026 | Isolated WordPress child theme | Fictional concept; no commercial activation

## Product decision

The original reusable five-page Empire Local Services WordPress theme and the V0.3 car-yard plugin remain unchanged. A separate optional child theme was created at prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier/. It does not create another CRM or activate public booking.

The fictional Atelier Motors showroom uses bundled React 19, Three.js, React Three Fiber, Drei, Motion and Lucide, plus a local Magic UI-inspired animated SVG grid. The grid is not an upstream Magic UI registry installation. No remote car models, fonts, runtime CDNs or real vehicle records are used.

**No handwritten CSS rules are present in the child theme.** WordPress requires a style.css header, which contains theme metadata comments only. The src/tailwind.css file contains Tailwind directives only. Vite/Tailwind generate dist/yard.css based on utility classes in React, WordPress templates and the locally bundled inventory enhancement.

The responsive home page has a procedural WebGL vehicle, accessible fallback when WebGL is unavailable or motion is reduced, mobile navigation, grid and entrance animation, functional local links, and honest fictional branding. The original public read-only stock shortcode remains backed by the existing plugin; a local non-submitting JavaScript enhancement applies Tailwind classes to its filters and cards.

## Native browser / MariaDB acceptance

A fully disposable rootless test loaded WordPress 6.8.11, PHP 8.5.4, the original plugin and the new child theme against a disposable MariaDB InnoDB database. PHP HTTP was bound to 127.0.0.1 and MariaDB was restricted to a private Unix socket with networking disabled. External requests from Chromium were blocked.

- Initial proof: 27 browser assertions and independent backup+restore verification. This historical receipt remains retained.
- **Final v2 proof: 31 browser assertions passed**, including React hydration, generated Tailwind styles, a real Three.js WebGL canvas, animated SVG grid, no viewport overflow on desktop 1440px or mobile 390px, enhanced inventory, staff login, hold → confirm → cancel and no unexpected HTTP 5xx.
- The website files and database were backed up and restored into distinct temporary locations. WordPress verified the active child theme, seven stored pages, one synthetic vehicle, restored image, one cancelled booking and three audit events.
- Four screenshots from actual Chromium rendering are in docs/commercial/car_yard_react_browser_evidence_v2/. The first staging run's four screenshots are stored separately.
- The final immutable receipt is docs/commercial/EMPIRE_CAR_YARD_REACT_THREE_DESIGN_V2_ACCEPTANCE_20261022.json and contains hashes for the exact React sources, generated JS/CSS, package-lock, testing scripts and screenshots.
- All temporary directories, credentials and test listeners were shut down and removed. No production deployment, EmpireDB/CRM writes, emails or financial actions occurred.

## Remaining gates

The 3D vehicle is procedural fictional geometry, not a licensed manufacturer car model. Atelier Motors is not an authorised dealership identity. There are no real vehicle prices, real testimonials, live appointments, mail destinations or public booking/payment routes.

Client approval remains necessary for brand, inventory rights, content, legal/privacy/retention, roles, accessibility review with assistive technology, mobile-performance assessment on slow hardware, TLS/hosting, upgrades and formal handover. The private staff booking screen remains guarded by its explicit staging feature flag.

## Deployment boundary

This optional child theme requires the existing empire-local-services parent theme. A generated local ZIP is an offline capability artefact, not authority to install it on a production/client site. The car-yard plugin remains separately versioned. Keep production, CRM, outbound and payment gates closed.
