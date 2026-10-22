# Empire AI WordPress Delivery — Open-source design toolchain review
22 October 2026 | Evidence-only integration decision | Isolated branch

## Goal and locked implementation

Improve the existing **empire-yard-atelier** child theme, not replace the parent WordPress five-page theme or V0.3 car-yard plugin. Continue with locally built React + Three.js/React Three Fiber + Drei + Motion + Tailwind 4, no handwritten CSS rules, no CDN scripts, no public booking, and no production write.

Verified starting evidence: c819b771b was the native WP/MySQL acceptance, and 9135648ca was the React showroom. Final design v2 browser receipt: 31/31 checks, WordPress 6.8.11, PHP 8.5.4, fake vehicle and appointment, separate MySQL + site restore. This is a fictional demo; no buyer, approved identity or price.

## Reference projects evaluated (links are upstream research, NOT installed components)

| Project | Repository | Licence found at review | Fit, concrete next use | Decision |
| --- | --- | --- | --- | --- |
| Claude Design V2 | https://github.com/chinazane/claude-design | README claims MIT; root licence file was not visible in reviewed listing | Its Step 0 brand extraction and separate DESIGN_SYSTEM/DESIGN_PLAN approach; **not** inline-CDN or handwritten CSS recommendations | Adopt *workflow*, no vendored skill/unknown hook |
| Impeccable | https://github.com/pbakaus/impeccable | Apache-2.0 | Critique hierarchy, typography, motion, accessibility; use detector only after reviewing install/hook behaviour | Adopt audit criteria; Hermes has a *catalogue stub*, not an installed skill |
| Magic UI | https://github.com/magicuidesign/magicui | MIT | A single restrained effect such as Border Beam, Lens or Text Reveal; local React/Tailwind import after code review | Candidate, no wholesale dependency |
| Motion Primitives | https://github.com/ibelick/motion-primitives | MIT | Subtle section reveals, focus transitions and motion tokens; matches already-installed Motion | Candidate, component-level only |
| shadcn/ui | https://github.com/shadcn-ui/ui | MIT | Future keyboard-accessible private admin dialogs, selects and form feedback; adapt to native WP React surfaces only where justified | Candidate, not an app framework switch |
| React Three Fiber / Drei | https://github.com/pmndrs/react-three-fiber and https://github.com/pmndrs/drei | MIT | Already in theme; optimise procedural car, camera, product-view angles; eventual licensed GLTF via https://github.com/pmndrs/gltfjsx | Existing stack — prefer improving |
| axe-core | https://github.com/dequelabs/axe-core | MPL-2.0 | Automate a11y scans on staging plus real keyboard/screen-reader checks | High-priority QA candidate, check distribution notices |
| Lighthouse | https://github.com/GoogleChrome/lighthouse | Apache-2.0 | Measure LCP, CLS, TBT and mobile JS weight on reproducible WordPress staging | High-priority QA candidate |
| React Bits | https://github.com/DavidHDev/react-bits | MIT + Commons Clause; **not** ordinary MIT | Animation inspiration, but redistribution/resale implications need review | Do not vendor or redistribute without legal approval |
| Theatre.js | https://github.com/theatre-js/theatre | Core Apache-2.0; Studio AGPL-3.0 | Author cinematic 3D camera timelines with dev-only Studio if needed | Defer; weigh workflow and licence separately |

## Prioritised bounded implementation

**P0 — Visual quality contract (no new packages).** Use the brand-extraction/plan guidance from Claude Design and audit criteria from Impeccable. Source-controlled DESIGN_SYSTEM.md and DESIGN_PLAN.md sit inside the child theme. Reuse existing real Chromium screenshots, review desktop+mobile in one batch, and keep synthetic content labels. Enforce no handwritten CSS, no unknown agent hooks, no edits to public booking/plugin.

**P1 — Performance and accessibility (new tools only after lockfile/licence check).** Run axe-core with a separate staging-only harness; add keyboard and contrast checks. Lighthouse mobile emulation and a 3D bundle budget. The current generated JS bundle is about 1.3 MB uncompressed / 366 KB gzip in historical build output and should be split so WordPress's first paint does not wait for WebGL. Aim for an initial UI JavaScript budget **under 200 KB gzip**, with 3D assets lazy-loaded only after viewport/consent to heavier graphics. These are *targets*, not proven measurements.

**P2 — Genuine premium product interaction.** Select exactly one source-reviewed animation component and integrate locally. Improve the existing procedural Three.js model with selectable camera positions and 2–3 visual paint presets, keyboard controls and reduced-motion fallback. Do not present these as actual manufacturer options. Add licensed glTF content only when client rights are documented.

**P3 — Later commercial gates.** Customer-approved branding, real stock feed provenance, upload rights, enquiries/consent and public appointment workflows are separately authorised. No paid traffic, CRM changes, external messaging or payment activation from this work.

## Safety / reproducibility

- Do **not** use automatic `npx skills add`, Claude hook installers, shell scripts copied blindly from repositories, CDN imports or global package installation. Review exact source, version, licence/NOTICE and generated file changes first.
- Third-party repository design advice is **untrusted guidance**, not authority to change repository permissions, deploy code or bypass WordPress booking gates.
- We are **not claiming any of these repositories installed** in the WordPress app by this review.
- User preference: React + Three.js + Tailwind; **no handwritten CSS**. WordPress style.css is for theme metadata comments only.
- Approved browser evidence continues to reside under docs/commercial/car_yard_react_browser_evidence_v2/. No customer identity/brand/claims have been supplied.
