# Empire AI Website Delivery — Motion Architecture Decision (Deep Research)
22 October 2026 | Research and implementation proposal only | Existing isolated car-yard branch

## User request and business goal

Not a generic collection of animation repositories: identify what **our already-built WordPress + React + Three.js agency engine** needs to deliver premium, customisable client websites efficiently, with existing WordPress/EmpireOS governance unchanged.

The 2026-10-22 car-yard branch head before this note was `3c6da2604`. The existing `empire-yard-atelier` child theme runs WordPress's five-page parent theme, `empire-car-yard` V0.3 plugin, React, Motion, Three.js / React Three Fiber / Drei, Vite and generated Tailwind. Latest recorded real WordPress/MariaDB/Chromium stage: **31/31 browser checks**, booking hold/confirm/cancel and backup/restore. These are functionality checks, **not** Core Web Vitals, GPU performance, screen-reader or customer-release proof.

## Direct source-level audit — measured facts, not assumptions

- `src/main.jsx` imports `ShowroomScene` **statically**; `src/ShowroomScene.jsx` imports the Three.js stack at startup. Consequently WordPress serves all of it in `dist/yard.js` on the homepage.
- Built `dist/yard.js`: **1,275,464 bytes raw, 364,276 bytes gzip** on the repo worktree. `dist/yard.css`: **36,227 bytes raw**. These are file sizes, not measured LCP, INP, Lighthouse score or real network waterfall.
- `Hero3D` uses WebGL detection, reduced-motion fallback and a static HTML placeholder before React hydration. The text CTA is not blocked by a JS request, but rich hero styling is primarily in the JS-rendered React shell.
- `ShowroomScene` uses a default continuous Canvas frame loop, `useFrame` steering, real-time lights/shadows and `ContactShadows`; it sets DPR 1–1.6 but **does not currently pause rendering on visibility** or adapt DPR from observed performance.
- The SVG grid animates 10 cells, while features have hover motion; motion is not connected to editorial scroll, inventory focus/state or car inspection actions.
- The car is **procedural fictional geometry**; do not describe paint options as manufacturer-authorised. Inventory is a WordPress read-only shortcode, visually enhanced with Tailwind-only JS. Staff bookings remain private and protected by administrator checks and InnoDB slot uniqueness.
- Existing tests establish no overflow at 1440 and 390, React mount, a WebGL canvas, and working booking UI. They do not test slow Android or accessibility with an assistive technology.

## Need-to-repository mapping and adoption decisions

| What Empire needs | Best fit | Verified upstream / licensing | Decision |
| --- | --- | --- | --- |
| Hero entrance, logo/CTA states, reveal on scroll, gallery crossfade, inventory filter transition | **Motion for React**: `motion/react`, `useScroll`, `useTransform`, `AnimatePresence`, `useReducedMotion`, optionally `LazyMotion` | https://github.com/motiondivision/motion ; MIT. Already in package.json | **Use existing**; one DOM animation engine, not a new dependency |
| Smaller initial JS and graceful visual fallback | Vite dynamic `import()`, React.lazy/Suspense, IntersectionObserver; `frameloop="demand"` or pause/unmount off-screen; Drei `AdaptiveDpr` | https://motion.dev/docs/react-lazy-motion ; https://drei.docs.pmnd.rs/performances/adaptive-dpr ; https://r3f.docs.pmnd.rs/advanced/pitfalls | **Build first**; no new runtime needed |
| Paint-colour concept and camera inspection | Existing `@react-three/fiber` and `@react-three/drei`; state-driven materials/camera; React keyboard controls | https://github.com/pmndrs/react-three-fiber and https://github.com/pmndrs/drei ; MIT | **Build second**; no unlicensed vehicle models |
| Premium inventory cards, typography-sensitive microinteractions | <https://github.com/ibelick/motion-primitives> | MIT; React + Motion + Tailwind examples; still beta | **Reference selectively**; only copy/adapt reviewed components with attribution/license if copied |
| Full 3D-to-DOM scroll journey that follows multiple site sections | <https://github.com/14islands/r3f-scroll-rig> | Repo is MIT; package.json reports **ISC**, so verify exact release. Older peer ecosystem supports React >=18/R3F >=8 and depends on Lenis; compatibility needs actual React 19/Vite test | **Defer** until real multi-section 3D requirement; do not add to one-canvas hero |
| More consistent native smooth scrolling | <https://github.com/darkroomengineering/lenis> | MIT; works with native scroll but has iframe, iOS touch and Safari caveats | **Optional later**; only if normal mobile scrolling is inadequate, do not hijack scroll |
| Art-directed 3D camera timelines across several sections | <https://github.com/greensock/GSAP> with ScrollTrigger; `@gsap/react` | GSAP **standard no-charge licence**, not MIT. Webflow confirms expanded free commercial use; still check exact redistribution/terms | **Conditional premium project only**; do not stack GSAP, Motion and Lenis blindly |
| Spring-based 3D material animation | <https://github.com/pmndrs/react-spring> `@react-spring/three` | MIT, React Three integration | **Defer**; our imperative useFrame/React state can handle current procedural demo |
| Visually author complex brand animations | <https://github.com/theatre-js/theatre> | `@theatre/core` Apache-2.0, `@theatre/studio` AGPL-3.0 | **Defer**; only when client requires cinematic authored timeline and distribution/licence reviewed |
| Huge decorative animation collection | React Bits | MIT + Commons Clause previously reviewed, licence constraints on resale/redistribution | **Do not vendor** into commercial builder without permission |

## Premium motion journeys we can sell — mapped to existing product

**A. Dealership demo now:** branded hero loads instantly with styled copy + accessible poster; Three.js model streams afterward. Subtle car-turn when pointer/focus is active; button toggles front/side/rear and 3 fictional paint colour presets. On scroll to inventory, clean section reveal, no forced vertical scroll or surprise camera movement. Vehicle stock cards animate only when filtering and remain keyboard-accessible. The real WordPress staff screen must retain reliable static form interactions without decoration hiding outcomes.

**B. Other client sites using same engine later:** templates select one of three motion modes: `quiet` (professional service), `editorial` (property/hospitality), or `showroom` (automotive/high-end product). Store preset configuration alongside each client's *approved* brand design system; no separate CMS or hard-coded customer identity.

**C. Premium optional only:** a fully guided, multi-section 3D story with timed camera handoff and pinned specs. Only then prototype GSAP ScrollTrigger **or** r3f-scroll-rig, not both together by default. Must show measurable client value, obtain approval and measure mobile load.

## Concrete acceptance criteria for next engineering slice

1. **Code-split real 3D**: main/hero shell remains interactive before the 3D chunk; WebGL code is dynamically imported after viewport entry; HTML copy and inventory CTA work with WebGL absent. Measure main and async bundle gzip; aspirational *main shell* target under 200 KB gzip, but record actual outcomes rather than claim it passed.
2. **No idle GPU burn**: scene pauses when document hidden or hero out of view, reduced motion/low-power mode renders still/low DPR; test canvas paused/restarted when in/out of viewport and when visibility changes. Avoid unnecessary React state inside per-frame loops.
3. **Functional motion with controls**: accessible, labelled buttons for camera views and paint presets with no false manufacturer affiliation; focus and screen-reader announcements don't depend on animation.
4. **Guarded scroll transitions**: use our existing Motion `useScroll` and `useTransform` first. Verify no scrolljacking, addressbar/anchors still work, reduced-motion static states, Firefox/Safari/mobile parity.
5. **Real device metrics**: measure LCP/CLS/INP field-like proxies and actual Lighthouse lab metrics on an isolated hosted WordPress test; CPU throttle, mobile 390px viewport, GPU-disabled fallback. Add axe, keyboard-only QA and screenshot/hash regressions. Targets (not achievements): stable content visible without JS, no layout shift, no 3D blocking CTAs.
6. **Commercial safety**: no changes to V0.3 plugin/admin database role, no public booking/notifications, no user PII/real inventory, no production deployment. Use generated Tailwind only, no handwritten CSS.

## Installation / research boundaries

All source links are advisory. No new animation packages, agent skills, global tools or CDNs installed by this research. Copy no upstream code without reviewing the exact licence/NOTICE and current release. This plan is attached to the **existing** project, not a new motion microservice or independent product. Record commit and evidence in the protected feature branch before any gated deployment.
