# Empire AI Agency — Atelier Motors V11 | WebGL Context Resilience and Keyboard Reflow

**24 October 2026 | Original isolated WordPress agency branch | Private staging only | Production release HOLD**

## Actual product changes

V11 hardens the original Atelier Motors premium React/Three Fiber **WordPress child theme**. It does not fork the Smart CRM, EmpireDB, MCP server, booking plugin, payment code, or create a new CMS.

**WebGL context loss**: A dedicated `RenderContextMonitor` inside the existing Three Fiber canvas registers a genuine `webglcontextlost` event listener on the mounted canvas. It calls `preventDefault()` and notifies the outer Hero3D state. If the GPU context disappears, React tears down interactive WebGL, shows the original static fallback and exposes a keyboard/screen-reader accessible status explaining that 3D is unavailable until a deliberate reload. The Studio control is disabled rather than re-fetching the GLB or trying a repeated GPU restart. This differs from the already-proven V10 synthetic GLB HTTP 503 fallback and protects the other failure class.

**320px mobile reflow**: The existing hero and commercial CTA had minimum-content widths exceeding 320px because of long words and fixed mobile font sizing. Their grid children now explicitly allow shrinkage, their large headings wrap when needed and the CTA headline uses a smaller responsive minimum. This was verified against real Chromium layout, not hidden by clipping overflow on the body.

**Keyboard interaction**: The existing camera-angle and paint-finish controls retain native buttons and `aria-pressed`. Tests now drive `Space` and `Enter` with the browser's keyboard and wait for React's committed `aria-pressed` changes. The React header's visible-on-focus “Skip to main content” link is confirmed functional in the 320px reduced-motion view.

## Native WordPress runtime acceptance

Run: `scripts/premium_wp_v1/run_react_wordpress_design_v11.sh`.

A new isolated, rootless WordPress **6.8.11**, PHP **8.5.4**, MariaDB (Unix socket) installation loaded the same original child theme and original WordPress booking plugin. The browser:

- Completed the previous **105/105** WordPress/browser tests from V10: real opt-in 2.83 MB first-party Meshopt car model, paint finishes, camera controls, WordPress Media Library images, branding, synthetic vehicle stock, private staff hold-confirm-cancel and full database/files backup restore.
- Activated the real mounted canvas `WEBGL_lose_context` extension and explicitly called `loseContext()`, then observed context loss, canvas removal, the static preview, visible status, no automatic 3D reactivation and blocked external requests.
- Activated front view via keyboard Space and silver paint via keyboard Enter, and checked actual button state.
- Tested 320px viewport with reduced motion: **320px scroll width for 320px viewport**, one H1, focusable visible skip link, main target, static graphic, no automatic GLB request.
- Retained test-only axe-core 4.10.3 audit: **0 confirmed automated WCAG 2.x violations** on the 390px reduced-motion homepage. **38 manually incomplete colour-contrast nodes remain** (gradients/photos); still not an accessibility certification.
- Verified the production theme ZIP carries neither axe nor test-only browser scripts.

**Result: 115/115 Chromium checks passed.** Native WordPress/MariaDB backup+restore recovered exactly three synthetic booking audit records. No real customer processing or production service activation occurred.

Evidence: `docs/commercial/EMPIRE_CAR_YARD_CONTEXT_KEYBOARD_V11_BROWSER_ACCEPTANCE_20261024.json`. The six SHA-pinned Chromium screenshots are stored under `docs/commercial/car_yard_react_browser_evidence_v11/`.

Installable private preview: `prototypes/agency_wordpress_service_handoff_20261022/dist/empire-yard-atelier-context-qa-v11-preview.zip`, **2,865,857 bytes**, SHA256 `31710b559ed2b331eda51cfc992d1b1164080bead0c0482f98fd3bd6901f01ee`.

## What this does NOT establish

The source context-loss simulation is a real Chrome WebGL event but was driven on the EmpireOS **software-rendered SwiftShader** staging browser. It does not prove real-phone hardware GPU recovery, power/thermal performance, iOS Safari, Android Chrome, manufacturer asset rights, or a physical 400% browser zoom journey. The 320px viewport is a valuable *reflow proxy*, not a fully zoomed physical device.

The high-detail car remains a third-party Khronos CC BY 4.0 demonstration asset. Removal of upstream branding meshes does not automatically clear manufacturer trademarks, external client use, actual customer site authority or copyrighted client-specific photography. Site grant, signing key, tenant permission, payment and outbound gates remain separately controlled.

**Release decision: HOLD**, pending real device QA, owner-approved site grant, client-owned licence/trademark clearance, manual screen-reader/keyboard and unresolved contrast review and exact production rollback.

One EmpireOS. One Smart CRM. One reusable premium WordPress agency delivery engine.
