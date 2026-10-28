# Chicago evidence photographs — V17 original ASTRA owner review

**27 October 2026 · Private review only · Original ASTRA website integration PR #148**

The founder requested **one specific, photographic image for each of the five evidence notes**, instead of plain placeholder treatments. This update is implemented in the original site's **isolated** first-party owner worktree, not a mockup, second publisher or production deployment.

## Actual distinct media / evidence pairing

| Original evidence note (official citation retained unchanged) | Actual image on page | Image rights/source |
| --- | --- | --- |
| 1. City of Chicago Express Permit reroofing criteria | Real roofers at work, photographic *illustration* | [Roofing contractors, Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Roofing_contractors.jpg), Public Domain Images / worldwide PD grant |
| 2. Chicago building permit instructions | Actual photo of Chicago City Hall entrance | [Photo by ajay_suresh, Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Chicago_City_Hall_(51575574600).jpg), [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/) |
| 3. Chicago permit-application status lookup | Real construction site in Eugene, Oregon; **illustrative, not an actual Chicago permit record** | [Photo by Visitor7, Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Construction_Site.jpg), [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) |
| 4. Illinois IDFPR licence lookup | Roofer installing shingles in Indiana; **illustrative, not proof of licence** | [Photo by Paul West, Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Shingle-roof-contractor.jpg), [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| 5. Census ZIP/ZCTA and Chicago jurisdiction | Actual aerial view of the Chicago West Lawn neighbourhood; **illustrative, not a jurisdiction map** | [Photo by Alfred Twu, Wikimedia Commons](https://commons.wikimedia.org/wiki/File:08-chicago-westlawn-s-pulaski-ave.jpg), [CC0](https://creativecommons.org/publicdomain/zero/1.0/) |

Every individual evidence card has an actual image, responsive 16:9 presentation, appropriate descriptive alt text, a visible credit/link to the original file and licence, and an explicit statement that the picture is not the official evidence. The research claim text and the existing five **original official source links** are unchanged. Creative Commons photos were cropped and transcoded, with adaptation disclosed beside the licence and source. Source JPEG thumbnails and original rights metadata remain in **private, uncommitted** EmpireOS release directories; code alone is submitted to GitHub.

## Actual review receipts

- Input is exactly the V16 site owner QA HTML: SHA-256 `93c9f75a56b93cf4fde40656d177d734bf2814afd39ffe84bfd4d71555b15275`.
- **New V17 bounded standalone page**: SHA-256 `b2993348d21d0d30669b04280007201e0946b25fea148acd5c6247cd995c0102`, **347,831 bytes**, smaller than the original site owner's strict 400,000-byte QA cap. Retains the original embedded orbital-A PNG, both original photographic heroes but recompresses their offline review variants to make room for five embedded WebP evidence images.
- Private stage: `/home/ubuntu/empire_releases/chicago_original_owner_evidence_photo_v17_20261027/`, `microsite_c4c5a13b626d293fe15c.preview.html` and `five_image_provenance_receipt.json` with source URLs, licence URLs, compressed image byte hashes.
- Actual Chromium `BROWSER_QA_PASS`: desktop 1440×900, mobile 390×844. Single H1, single main, no horizontal overflow, original logo loaded, accessible 51.59px CTA, no lead form, robots `noindex,nofollow,noarchive`, **zero external image/network requests**.
- Separate native 3840×2160 owner photo review (`chicago_evidence_actual_native4k_review.html`) restores the original full 4K city and roofing masters and 1280-wide evidence photographs. Its own SHA is `12a9097adb7469d15878c477156a39c3698872de9430ff6c3010cc65d2ade4d3`; `NATIVE_4K_QA_PASS`: five source cards, two hero images, five checklist steps, 4K background, zero external requests.
- **128 original-gateway and current evidence/photo source regression tests passed**, one pre-existing AnyIO warning.
- Original five released research campaigns, production repo, original SEO worktree, checkout, CRM, domain routing and original first-party deployment controls **unchanged**.

## Publication remains separately controlled

This patch **does not grant final image rights or publish the page**. The existing original ASTRA site/SEO/media owners must still approve the exact photo reuse under these specific licence terms, actual Chicago research, orbital-A brand distribution, and deployed page. PR #148 remains **draft and unmerged**, and source file/photo transfers are not public media upload permission. No invented leads, traffic, buyer acceptance, revenue or live URL.

## V17 image integrity / final-quality addendum (same original owner workflow)

The original source photo files from Wikimedia Commons are now **SHA-256 pinned in the first-party build**, so reusing an old credit with swapped or altered source bytes makes the build fail. A dedicated adversarial test intentionally supplies an incorrect photograph checksum and verifies a hard failure before any page output. The attribution of the public-domain roofers image was corrected from a source-site label to **"Creator uncredited (Public Domain Images)"**, matching the upstream Commons metadata rather than inventing the creator.

The repeated small diamond placeholders formerly printed underneath the actual photographs are now suppressed. Evidence photographs have sharper **570px / WebP 27** offline rendering, with larger readable captions. The existing strict **400,000-byte** first-party QA ceiling is preserved.

**Current recommended exact owner-review candidate (supersedes V17 initial image candidate for visual review only):**

- Source reviewed V16 site export remains SHA-256 `93c9f75a56b93cf4fde40656d177d734bf2814afd39ffe84bfd4d71555b15275`; original brand image/official source claims unchanged.
- Final V17 HTML SHA-256 `1ed1e468a51db0de0f633d955f86b6283b396924db71219816dd9c379dd25c88`; **387,684 bytes**. Source photos all validated against individually pinned SHA-256 values.
- Original site owner private stage: `/home/ubuntu/empire_releases/chicago_original_owner_evidence_final_review_20261027/`.
- Desktop **1440x900** and mobile **390x844** Chromium `BROWSER_QA_PASS`, no overflow, no input forms, noindex, original logo loaded, zero external network requests.
- Separate native 3840x2160 source/photo review `NATIVE_4K_QA_PASS`: five source notes, two photographic hero panels, five decision steps; SHA-256 `7d7b864877c9a40c49e483f8717d2c121b8afb6d90e54b3e197f1357a41cf916`, no production writes.
- **130** combined focused original gateway/visual/photo/release tests passed, one existing AnyIO deprecation warning.
- The new image cryptographic pins verify **identity of reviewed bytes**, not underlying copyright ownership. Creative Commons Attribution-ShareAlike assets require suitable attribution, change disclosure and potentially sharing adaptations under the same terms. The current captions link each source and applicable licence, credit the creator and state that images were cropped; the original brand/media rights owner must still verify release compliance. Neither the captions nor these tests constitute public-asset clearance.
- Existing five published site campaigns remain protected. Draft PR #148 unmerged. No paid traffic, search indexing, consumer lead capture or revenue claimed.
