# Empire AI Agency — Atelier Motors V12 | Keyboard Navigation, Responsive Text and Contrast Review

**24 October 2026 | Original isolated WordPress agency branch | Private staging only | Production HOLD**

## Engineering delivered in the ORIGINAL WordPress theme

V12 improves the existing premium React/Three.js **Atelier Motors** child theme, not a new CRM, CMS, connector or demo application.

**Keyboard-accessible mobile navigation.** The original WordPress/React nav's mobile disclosure now has a stable `aria-controls="agency-navigation-links"` relationship, native pressed-state/expanded disclosure, visible focus rings, an explicit 44px minimum touch button and full-height mobile menu links. Space opens the menu, Tab reaches the first menu item, Escape closes it and returns focus to the trigger, and Enter activates an in-page navigation destination and closes the menu. All behaviour stays client-side and does not change WordPress menu data or routes.

**200% root-text enlargement reflow.** The browser uncovered real minimum-content overflow in the collection headline, experience heading, feature cards and enquiry CTA when the site's root font was raised from 16px to **32px**. The changed elements now use narrow-grid minimum width, word wrapping and bounded CTA width in the existing Tailwind utility design system. The same build preserves the natural desktop appearance and the 2.83 MB on-demand 3D model.

**Accurate responsive evidence.** The V12 browser tests 320, 360, 390, 640, 768 and 1024px CSS viewport widths, and separately tests a 390px viewport with root font size increased to 32px. Both are local Chromium layout checks—not a physical browser's 400% zoom setting, pinch zoom or a WCAG certification. A forced `html { zoom: 400% }` pilot was explicitly **rejected** as an invalid browser-zoom proxy because it failed to recalculate responsive media queries as real browser zoom would.

**Manual contrast review preserved.** The private local axe-core 4.10.3 runner now records each incomplete colour-contrast node with selector, text, foreground colour, font size/weight, bounding box and up to five background/gradient ancestor layers. Every unresolved item carries **`MANUAL_REVIEW_NOT_GRANTED`**. This produces a practical inspection queue plus its matching reduced-motion full-page screenshot, rather than turning axe `incomplete` into a misleading pass. The QA library stays outside the WordPress distribution ZIP.

## Real WordPress and browser acceptance

Source: `scripts/premium_wp_v1/run_react_wordpress_design_v12.sh`

Actual rootless, isolated WordPress 6.8.11 / PHP 8.5.4 / MariaDB with the same original child theme and plugin; real Chromium mobile/desktop tests, WordPress admin session, theme media picker, source-pinned photo assets, on-demand Meshopt PBR car, Data Saver constraints, intentional high-detail GLB 503 recovery, genuine WebGL context-loss and keyboard navigation. Includes end-to-end staff-only synthetic booking hold, confirm and cancel, backup and restore.

Receipts:

- `docs/commercial/EMPIRE_CAR_YARD_FOCUS_CONTRAST_V12_BROWSER_ACCEPTANCE_20261024.json` — all browser check outcomes, source hashes, six older screenshot scenarios and two new audit screenshots, mobile menu keyboard proof, text layout measurements, axe unresolved contrast audit.
- `docs/commercial/car_yard_react_browser_evidence_v12/home-manual-contrast-v12.png` — reduced-motion mobile visual paired with manual contrast data.
- `docs/commercial/car_yard_react_browser_evidence_v12/home-200pct-root-text-v12.png` — 390px 32px-root enlarged text preview.
- `tests/test_empire_yard_focus_contrast_v12_20261024.py` — exact source/bytes/screenshots and fail-closed release assertions.

The source-integrity receipts for historical V2–V11 remain immutable and pinned to the original corresponding commits; the original booking WordPress plugin, tenant/MCP foundations, canonical EmpireDB and CRM are not modified.

## Rights, accessibility and release boundaries

The licensed Khronos glTF demonstration vehicle remains third-party CC BY 4.0 imagery with separate manufacturer/trademark rights unresolved, not a client vehicle or Empire-original mesh. The original site remains private. The visual gallery stays clearly labelled as editorial reference rather than actual stock.

The automation can demonstrate keyboard sequence and no horizontal scroll in its precise tested scenarios; it cannot establish full WCAG compliance, 400% physical-browser zoom, human screen-reader quality, contrast across all photo/gradient states, actual iPhone/Android GPU/thermal characteristics, independent IP rights, site-grant authority or client approval.

**Release decision: HOLD.** No production deployment, public booking, real customer data, canonical DB migration, CRM changes, sender activation, outbound or payment occurred. Continue one EmpireOS, one Smart CRM, one reusable premium WordPress agency engine.

## Final private-stage verification

- **125/125** genuine WordPress/MariaDB Chromium checks passed, including 3 synthetic booking audit events recovered after restore.
- **225 Python passed, 2 skipped; 11 Node MCP passed; 4 physical-device probe guard tests passed.** One pre-existing Starlette/AnyIO deprecation warning.
- **38** axe-core incomplete colour-contrast nodes are recorded individually; none is owner-approved. Automated reported violations in the tested scope: **zero**. Manual contrast, keyboard/screen reader, rights and physical GPU certification remain outstanding.
- A screenshot-only isolated browser tab eagerly decodes photos, including the **640px synthetic WordPress image selected by the admin test**. This does not alter the original frontend lazy-loading or model.
- V12 WordPress preview ZIP: **2,866,059 bytes**, SHA256 `6b76f675977f0c62064095fe3fbdd3e7c224d48cd20f3db2d3794fbae3e4aa75`.
- Exact local root staging directory removed. No production deployment, owner approval, client data, live booking, CRM write, outbound or payment. **Release: HOLD.**
