# Atelier Motors — next design plan
Version 0.1 | Not a release order

## Outcome
Move from a working fictional 3D WordPress showroom to a polished, lightweight, accessible and repeatable client-preview template. Preserve the existing WordPress parent theme, plugin booking guarantees and no-handwritten-CSS constraint.

## Existing verified capability
React child theme, Tailwind-generated styling, Magic UI-inspired *local* animated grid, procedural Three.js vehicle, demonstration inventory, mobile+desktop Chromium screenshots, WP admin hold/confirm/cancel and test-site/database restore. The v2 receipt has 31/31 browser assertions. These are functional tests, not a client acceptance or Lighthouse/a11y certification.

## Next single engineering slice (P1)
1. **Split the first-paint JS from Three.js** via dynamic import/Suspense or deferred client mount. Keep static hero copy and primary inventory CTA visible without WebGL or JS.
2. Run reproducible axe-core and Lighthouse on disposable WordPress/MariaDB loopback staging. Record actual mobile payload/LCP/CLS/TBT and no externally loaded assets, then improve only measured issues.
3. Add keyboard-operable 3D controls (front/side/interior-concept camera if appropriate), paint presets and reduced-motion fallback; no manufacturer fidelity claims.
4. Compare actual desktop, mobile and low-performance fallback screenshots in a bounded review. Do not open a second endless redesign loop.

## Candidate source map
- Design planning: https://github.com/chinazane/claude-design (design system/plan method, no raw code vendored).
- Critique: https://github.com/pbakaus/impeccable (standards only until an authorised skill installation review).
- A11y: https://github.com/dequelabs/axe-core
- Performance: https://github.com/GoogleChrome/lighthouse
- One optional motion effect: https://github.com/magicuidesign/magicui or https://github.com/ibelick/motion-primitives
- Existing 3D stack: @react-three/fiber + @react-three/drei; no additional 3D runtime required now.

## Completion gates
Generated Tailwind only; no customer data, invented claims, emails or payments; no production deploy; tests and screenshots attached to exact commit; accessibility and performance metrics independently collected rather than assumed; client sign-off needed before real stock/branding/public bookings.
