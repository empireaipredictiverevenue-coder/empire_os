# Empire AI Agency — Atelier Motors V6 Photographic Editorial and Native WordPress Media

23 October 2026 | **Actual website upgrade** | Existing agency WordPress child theme | No production deployment

## Product delivery

Replaced the three flat gradient/line-icon concept-card mockups on the original **Atelier Motors** WordPress/React homepage with an art-directed photographic editorial gallery. It is a responsive desktop asymmetrical mosaic and a vertical three-image mobile presentation. The images are visually rich, non-animated WebP stills, with accessible alt text, `loading="lazy"`, native browser decoding, legible text/gradient overlay and photographer credits.

The three default photographs are authentic contributor photographs from Unsplash; the images are NOT our original procedural vehicle, not merchandise or stock the fictional dealership sells, and no manufacturer partnership is asserted. The photo credits link to the original photographer work. Files are stored under the child theme `assets/editorial/` and served **locally**; the site makes no runtime requests to Unsplash. The photos collectively occupy well under 400 KB.

### Exact source / licence inventory

| Local image | Photographer | Original page |
| --- | --- | --- |
| `studio-red.webp` | Moses Malik Roldan | https://unsplash.com/photos/a-red-sports-car-parked-in-a-dark-studio-bZRqT3tvryk |
| `studio-silver.webp` | Đào Hiếu | https://unsplash.com/photos/a-sleek-white-sports-car-against-a-dark-background-S5ogDe0Uzp0 |
| `studio-detail.webp` | Serge Kutuzov | https://unsplash.com/photos/black-car-macro-shot-TNybYN-LqJo |

License page: https://unsplash.com/license — permits free downloads and commercial use with attribution appreciated, but **does not grant manufacturer brand/trademark rights or endorsement**. A client deployment requires actual manufacturer/asset clearance, approved owner imagery and source rights confirmation. The file `assets/editorial/PHOTO_PROVENANCE.json` preserves authors, original pages, source identifiers, output dimensions, original licence URL and exact SHA256 of all local derivatives. The initial photo rights are **editorial presentation only**, not a signed permission for actual vehicle advertising.

## Client media editing through the existing WordPress admin

The original `Appearance → Showroom Branding` settings page now has three **Choose WordPress image** controls, backed by the native `wp_enqueue_media` / `wp.media` Media Library dialog. The three image choices are stored in the existing sanitised `empire_yard_brand_v1` WordPress option as *image attachment IDs*; they are not arbitrary URLs. Server-side validation uses `wp_attachment_is_image` and a same-host URL check before passing the selected media URL through `application/json` script data to React. React further checks the URL origin and WordPress uploads path. Empty selections use the credited default photographs.

This reuses the original WordPress CMS. **No duplicate content manager, connector, CRM, secret, public upload form, paid service or extra React framework** was introduced. The native media picker appears only for administrators authorised to edit the theme, and selected images are served through the original site's WordPress uploads.

The selected photo is always marked as a *Media Library selection*, not falsely credited to an Unsplash photographer. The current image uploader **does not verify that the site's customer owns copyright**; production editors must prove rights and consent before using identifiable brands or photos. No licensing claim is manufactured.

## Real native runtime acceptance

Test script: `scripts/premium_wp_v1/run_react_wordpress_design_v6.sh`

A fresh, isolated WordPress 6.8.11 / PHP 8.5.4 / MariaDB site with the original `empire-yard-atelier` child theme and `empire-car-yard` plugin was tested by real Chromium. It checked both the desktop and mobile gallery, complete local asset downloads, image alt/loading properties, photographer attribution, the WordPress administrator's media dialog, replacing one picture with the synthetic WordPress Media Library attachment, and the absence of an incorrect Unsplash credit for that replacement.

The same browser pass retains desktop WebGL viewport and paint controls, lazy mobile 3D activation, reduced-motion fallback, WordPress branding and safe contact-path editing, synthetic inventory, staff-only booking hold/confirm/cancel, successful WordPress/MariaDB backup+restore with three booking audit events, and **no external browser resource requests**.

Evidence: `docs/commercial/EMPIRE_CAR_YARD_EDITORIAL_V6_BROWSER_ACCEPTANCE_20261023.json`. Browser screenshots: `docs/commercial/car_yard_react_browser_evidence_v6/`. Source/asset integrity: `tests/test_empire_yard_editorial_gallery_v6_20261023.py`.

## Exact boundaries

- Production EmpireDB, Smart CRM, payments, public WordPress, MCP security, source authority and outbound remain unchanged. No production publishing or client/customer media upload occurred.
- The existing 3D model remains the previously built **fictional procedural GT**; this release improves surrounding real photographic art direction but does **not** create an original photorealistic licensed 3D vehicle mesh.
- The photos depict identifiable real manufacturer vehicles. Their underlying photography licences don't by themselves clear manufacturer advertising rights; **customer-facing use remains on HOLD** pending brand/IP/rights and commercial approval.
- The WordPress V6 ZIP is an installable **private preview**, not a client licence to reuse the photos as dealership inventory or a verified vehicle advertisement.

## Next actual creative work

For a customer-ready design, use client-owned professional automotive media and a properly licensed photorealistic 3D vehicle asset (or commission an original model). Verify GLB/GLTF origin/rights, file size, mobile progressive delivery, camera framing, lighting, reflected materials and keyboard/motion accessibility. Continue improving the original WordPress/React agency child theme rather than create another CMS or model inference platform.

## Final private-stage release receipts

- Native WordPress/MariaDB Chromium: **84/84** checks passed, with real Media Library image replacement and no external image requests.
- Restore: three synthetic booking audit records; no public service activated.
- Agency regression: **190 Python passed, 2 skipped; 11 Node MCP passed**.
- ZIP size: **780,351 bytes**. SHA256: `14d1dccd0b6b2f9e46f1495ce0e2f04368cbacfde4e4aef2de60ae7c34e06b67`.
- Dedicated desktop WebGL view: `car_yard_react_browser_evidence_v6/home-hero-desktop-v6.png`; mobile photography: `home-mobile-v6.png`.
- No production system, real tenant, SMTP sender, CRM or payment was touched.
