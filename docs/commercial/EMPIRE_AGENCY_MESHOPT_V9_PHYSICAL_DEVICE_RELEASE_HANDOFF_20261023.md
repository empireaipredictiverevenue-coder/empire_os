# Empire AI Agency — Atelier Motors V9 | Progressive 3D Delivery and Physical-Device Acceptance

**23 October 2026 | Original isolated feature/agency-wp-car-yard-private-20261022 | Production HOLD**

## Actual product changes

The existing premium WordPress child theme retains the original React/Three.js showroom, procedural fallback, WordPress branding/Media Library photography and synthetic inventory/booking plugin. Its explicit **Studio PBR** mode now loads a **Meshopt-optimised** copy of the licensed Khronos CarConcept asset, instead of delivering 9.34 MB of geometry/textures.

| Exact local binary measurement | V8 | V9 |
| --- | ---: | ---: |
| High-detail GLB file | 9,338,828 bytes | **2,825,112 bytes** |
| Reduction | — | **69.75%** |
| Private WordPress theme ZIP | 7,613,065 bytes | **2,865,383 bytes** |
| Original car geometry (triangle equivalents) | 213,195 | **213,195** |
| Materials and textures | 28 materials, 14 textures | **28 materials, 14 textures** |

V9 uses `EXT_meshopt_compression`, `KHR_mesh_quantization` and `EXT_texture_webp`. Its decoder is already included in the existing Drei/Three.js distribution. The `useGLTF(modelUrl,false,true)` call **disables any remote Draco-decoder path** and enables bundled Meshopt support. The optimised GLB is locally served by the same WordPress child theme, does not automatically load on desktop or mobile and still requires a deliberate Studio click after mobile WebGL opt-in. The saved model attribution and the original gallery remain unchanged.

The GitHub upstream model and attribution are identical to V7, as are the limitations: third-party CC BY 4.0 model by Eric Chadwick / Darmstadt Graphics Group GmbH, not an Empire AI original, not real manufacturer stock and no manufacturer endorsement. Steer-emblem/plate meshes removed previously. **Removing two visible markings does not constitute trademark/IP clearance.**

- V9 optimised GLB: `assets/models/car-concept-studio-meshopt.glb`
- Independent derivative provenance: `assets/models/MODEL_PROVENANCE_MESHOPT_V9.json`
- Exact SHA256 of V9 GLB: `f690ee5ac4763c656adf3233596a85973d16b134124fb5caf0b1a1e3f2467159`
- Existing V8 source GLB remains checked into the isolated worktree for historical replay only; the **V9 installable ZIP excludes it entirely**.
- glTF-Transform 4.2.1 reported one validator warning: its validator does not itself interpret `EXT_meshopt_compression`. This warning is **not evidence that the Meshopt geometry is invalid**. The real WordPress Chromium runtime successfully decoded/rendered the new GLB and exercised cameras/paint.

## Actual real WordPress and browser verification

`scripts/premium_wp_v1/run_react_wordpress_design_v9.sh` provisioned genuine isolated WordPress **6.8.11 / PHP 8.5.4 / MariaDB** with the original child theme and booking plugin. **98/98 Chromium browser checks passed**: the optimised model was not fetched before the visitor requested Studio PBR, was downloaded from WordPress as 2,825,112 encoded bytes and rendered successfully, with camera, paint, concept return, mobile opt-in and Data Saver confirmation preserved. Also passed: WP native branding, Media Library editorial imagery, WordPress admin and synthetic staff booking hold/confirm/cancel, with **three audit events restored** after SQL/files backup. The temporary staging site was removed.

Evidence: `docs/commercial/EMPIRE_CAR_YARD_MESHOPT_V9_BROWSER_ACCEPTANCE_20261023.json`. Visual proof: `docs/commercial/car_yard_react_browser_evidence_v9/home-pbr-model-desktop-v9.png`. The Chrome test remains **SwiftShader software rendering**, **not a real phone GPU, GPU frame-time, battery test or field Core Web Vitals**. Its staging network timings are not representative of production.

## Technical admission and source controls

`scripts/premium_wp_v1/check_client_glb_admission_v9.py` is read-only and fail-closed: it validates SHA256, original author/source/licence claims, glTF 2.0 structure, embedded assets only, required Meshopt/quantisation/WebP extensions, geometry budget, and rejects oversized or malformed candidate assets. V9 compressed-delivery budget is **5,000,000 bytes** and **280,000 triangle equivalents**, for this specific private preview profile. Exact receipt: `docs/commercial/EMPIRE_CAR_YARD_MESHOPT_V9_TECHNICAL_ADMISSION_20261023.json`.

Even after technical validation, the result states `commercial_release_eligible=false`, `rights_owner_verified=false`, `site_grant_verified=false`, `model_brand_trademarks_cleared=false`, and `device_gpu_test_verified=false`. Metadata and a permissive model licence cannot substitute for independently validated real client rights.

## Physical browser QA: implemented, **not yet executed on hardware**

`scripts/premium_wp_v1/physical_device_studio_probe_v9.cjs` is a read-only QA harness for an **already-authorised real Chrome browser** accessed through a **loopback-only Chrome DevTools Protocol forward**. It requires all of these inputs and refuses mismatches:

- Explicit operator acknowledgement `AUTHORISE_SYNTHETIC_STAGING_READ_ONLY`
- Exact allowed private HTTPS staging origin, with visible *fictional design* banner
- Locally forwarded Chrome DevTools endpoint `http://127.0.0.1:9222`
- A create-only private JSON evidence path (never overwritten)
- Non-headless/non-WebDriver browser and WebGL hardware renderer string not matching SwiftShader, llvmpipe or known software/virtual GPU engines

It then tests that the optimised model was not automatically fetched, explicitly activates the original WebGL if needed, loads Studio, tests three views and three paint choices, and records the actual device/browser's GPU renderer identity, WebGL extensions, local model network bytes and load-to-ready duration, Chrome main-thread task/heap metrics and errors. It **does not claim to measure GPU completion times or independent physical device identity**. An owner must review a receipt plus live hardware/device provenance. All outbound browser resources other than the approved stage origin and data/blob URLs are blocked.

The host currently connected to ChatGPT is EmpireOS with an old **Matrox G200eR2** basic display adapter. No usable real mobile hardware or Android bridge was available and `apexengine` was offline when checked. **We did not produce physical-phone GPU proof or invoke this probe on a real device.**

### Example approved Android/Chrome browser run — only when a real device is available

1. Connect an authorised Android handset to a trusted workstation, enable developer access and explicitly authorise the USB debugging connection. Establish the private HTTPS synthetic WordPress staging endpoint with access controlled by the existing site owner.
2. On that workstation, with `adb`, `node`, and a test-only local `puppeteer-core` install:

```bash
adb devices -l
adb forward tcp:9222 localabstract:chrome_devtools_remote

export EMPIRE_DEVICE_QA_ACK=AUTHORISE_SYNTHETIC_STAGING_READ_ONLY
export EMPIRE_DEVICE_QA_SITE=https://approved-private-stage.example.test/
export EMPIRE_DEVICE_QA_ALLOWED_SITE=https://approved-private-stage.example.test/
export EMPIRE_DEVICE_QA_CDP=http://127.0.0.1:9222
export EMPIRE_DEVICE_QA_DEVICE_CLASS=android-physical-chrome
export EMPIRE_DEVICE_QA_RECEIPT=/tmp/empire-agency-device-qa-android-01.json

node scripts/premium_wp_v1/physical_device_studio_probe_v9.cjs
```

The hostname above is **an example, not an active server URL**. iOS Safari requires a separate Web Inspector/manual physical-device trace; this Chrome CDP script is **not** an iOS GPU test. The executable unit tests prove only input/device-backend refusals, not that actual hardware is currently connected.

### Owner-controlled release gate

Remain on **HOLD** until ALL are separately evidenced and approved: a genuinely authorised canonical tenant/site grant; specific client ownership of the uploaded model, photo rights, and independent manufacturer/trademark clearance; genuine physical Android/iPhone or equivalent GPU/compositor profiling; security and accessibility review; and owner-approved exact release + rollback. No client deployment, CRM write, payments, outbound or live booking activation.

**One EmpireOS, one existing agency WordPress product. No new CMS, CRM or customer connector.**
