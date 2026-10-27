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
