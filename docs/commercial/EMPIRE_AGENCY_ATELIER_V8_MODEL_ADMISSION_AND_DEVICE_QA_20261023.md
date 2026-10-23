# Empire AI Agency — Atelier Motors V8 GLB Admission and Device-Aware High-Detail Delivery

**23 October 2026 | Original isolated WordPress agency branch | Private staging only | Production release HOLD**

## What we implemented in the actual website

This V8 continues **the existing `empire-yard-atelier` WordPress child theme**—no duplicate CMS, model platform or CRM.

- Original small procedural GT remains the default interactive scene and the fallback for an unsupported high-detail GLB.
- The 9.3 MB third-party **Khronos CarConcept CC BY 4.0 derivative** is still loaded **only** after a deliberate `Load Studio PBR` click, from the current WordPress origin.
- A low-memory/Data Saver device adds a second positive user confirmation. Trigger: browser-reported `navigator.connection.saveData === true` OR `navigator.deviceMemory <= 2` GB (when a value is available). Neither attribute is reliable on every browser; their absence is NOT a claim that a device is fast. The user receives a clear size warning before a high-detail fetch.
- The Studio control is disabled until the WebGL view is active, preventing a misleading inert control on mobile before `Explore in 3D`. Reduced-motion visitors retain the static fallback.
- When the Studio 3D component throws, a React error boundary attempts to reset the original concept and provides accessible status text; this reset mechanism is source-reviewed but **has not been authenticated as a complete browser failure-injection test**.

No new runtime npm packages were installed. No third-party GPU beacon, analytics transmission, external model CDN, customer identity, CRM writes, live booking or payment activity was introduced.

## Actual synthetic WordPress/MariaDB browser proof

Fresh WordPress 6.8.11 / PHP 8.5.4 / MariaDB via Unix socket, HTTP strictly loopback, synthetic inventory and staff bookings. Chromium + SwiftShader browser test executed the native admin, mobile and desktop, photography, actual GLB load after opt-in, camera, paints and synthetic staff hold/confirm/cancel, and restore of three booking audit records. **96/96 Chromium checks passed**, including additional real browser checks that:

1. The high-detail model control remains disabled on mobile before the visitor opts into WebGL.
2. A browser simulating Data Saver does **not fetch** the GLB after its first Studio click, and changes the control to request a second confirmation.
3. A 45-interval `requestAnimationFrame` lab observation can be collected after the model has been loaded.

The original full V7 website was preserved and the V8 receipt records **96/96**, synthetic data only, no production actions. Receipt: `docs/commercial/EMPIRE_CAR_YARD_DEVICE_GATE_V8_BROWSER_ACCEPTANCE_20261023.json`. Local screenshots: `docs/commercial/car_yard_react_browser_evidence_v8/`.

### Performance measurements and their precise limitations

| Browser-stage metric | Observed |
| --- | --- |
| Browser renderer | **SwiftShader software backend** |
| High-detail GLB local uncompressed transfer | **9,338,828 bytes** |
| GLB resource timing on loopback | 39 ms |
| Number of requestAnimationFrame intervals sampled | 45 |
| Mean / P50 / P95 browser frame-callback interval | 16.66 / 16.7 / 16.7 ms |
| Inferred browser callback frequency | 60 callbacks/sec |
| Staging mobile FCP (390 px, 1.6Mbps, 4x CPU) | 1,252 ms |
| Staging mobile LCP candidate | 4,596 ms |
| GLB requested automatically on mobile | **No** |

**Important:** `requestAnimationFrame` callbacks are not GPU render-frame completion, GPU time, actual 3D interaction throughput, or physical mobile FPS. This view uses a demand-based render loop and may generate browser animation callbacks without repainting the GPU. The 60 callbacks/sec **must not be marketed as “60 FPS 3D”**. The 39 ms transfer is localhost, **not** customer network download time. This runner cannot validate an actual iPhone/Android GPU, battery/thermal throttling, pixel quality, screen-reader journey, remote production compression/CDN or Core Web Vitals.

For a real device release, record GPU/compositor frames, power/thermal behaviour, model load and user interactions on multiple actual phones and desktop GPUs, with verified customer staging permission. Do not waive that gate based on this receipt.

## Client-owned GLB technical admission, separated from release authority

New **read-only** Python preflight: `scripts/premium_wp_v1/check_client_glb_admission_v8.py`.

The tool inspects binary bytes offline without invoking or importing any model code. It validates glTF 2.0 header/length, JSON chunk, exact SHA256 vs the provenance manifest, URL-less embedded assets, allowed required GLTF extensions, triangle geometry, file and complexity budgets, and origin/author/licence claims. Budgets for this preview path are: at most 12,000,000 bytes, 280,000 triangle-equivalents, 160 nodes, 120 meshes, 45 materials, 20 textures, 20 images and 850 accessors. External/data URIs, unknown required extensions and hash-mismatch candidates are rejected. All technical rejections preserve the original procedural concept as fallback.

The current third-party demo model passed with 213,195 triangles, 95 meshes, 28 materials, 14 textures and SHA256 `b28b5e697dcbd8d699dad802a1415db1eb0a364d8f05aba004176d776940cdeb`. Evidence: `docs/commercial/EMPIRE_CAR_YARD_GLTF_V8_TECHNICAL_ADMISSION_20261023.json`.

**Crucial approval boundary:** This is *never* client ownership, manufacturer trademark, customer consent, site-grant, agency signing-authority or production permission. The output always sets `commercial_release_eligible:false` and `release_status:HOLD_CANONICAL_SITE_GRANT_IP_RIGHTS_AND_PHYSICAL_DEVICE_TEST`, even for a technically valid GLB. Any future real-client model must be independently sourced and rights cleared; metadata claims alone do not verify intellectual-property permission.

## Verifications and release decision

Native WordPress/MariaDB restored and original owner components unchanged. Exact code and asset hashes recorded in V8 acceptance. Unit tests include both genuine third-party GLB verification and deliberately synthetic malformed/foreign-URL/unknown-extension/oversize/mismatched-hash cases. ZIP: `prototypes/agency_wordpress_service_handoff_20261022/dist/empire-yard-atelier-device-gate-v8-preview.zip` (7,613,065 bytes), SHA256 `eaa7f07a41536a66e41c088e54195fd04f7293c3dc13a4f83249533602e9bc62`.

**Release decision remains HOLD** until the existing owner confirms real site authority, the specific client's signed media/model rights, real-device GPU QA, security/a11y approval and the exact production release/rollback. The original public WordPress site, EmpireDB, Smart CRM, canonical tenant/MCP, outbound, live bookings and payments are unaffected.

**Next actual product milestone:** Run this instrumented demo on 2–3 physical target devices using authorised private staging, capture real GPU/compositor traces under camera/paint interaction, and replace the third-party trademark-sensitive sample with a rights-cleared client-owned asset when available.
