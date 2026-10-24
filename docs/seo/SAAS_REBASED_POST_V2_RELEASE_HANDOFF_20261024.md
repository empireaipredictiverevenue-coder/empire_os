# EmpireOS SaaS guide — re-staged after the verified V2 industry enquiry release

24 October 2026 | Existing SEO + Website & Growth owner | PRIVATE POST-V2 RELEASE CANDIDATE ONLY

## Production publication now verified

The existing founder-approved Industry Enquiry V2 publisher returned `EXACT_APPROVED_INDUSTRY_ENQUIRY_V2_PUBLISHED_AND_GET_VERIFIED`, observed 2026-10-24T10:35:51.033663+00:00. It reports a fresh read-back-verified **653-file root backup**, 10 exactly replaced page files, 6 new content-addressed assets, 643 preserved originals and **659** live files. Founder-provided root backup SHA-256: `fcd9fc837eeda38fc57673fbc1cf20608ff8b5d2ffbcb983d90ff43fcdf65e04`. The approved V2 manifest SHA-256 is `d41167d3e2413dbfe914bf8f0527ef0da26da3df0723aff8eaa3c1b9f86065aa`.

An independent read-only server observation checked the live static tree has exactly 659 files and all 10 released V2 page payloads and six added hashed assets match the manifest. Local served HTTP GETs also independently verified the exact approved HTML hashes for `/commercial`, `/industries/roofing`, `/industries/solar`, `/industries/hvac`, `/industries/property`; the existing `/`, `/buy`, `/predictive-revenue`, `/privacy` returned 200. This verification used no publishing call, DB write, form submission, customer send or payment.

## New private SaaS candidate, explicitly NOT LIVE

The earlier 23 October SaaS content source commit `54601ed54` and original eight-step research guide remain the intended edit. **Do not apply the old private 653-file overlay** over today's live V2 site. The new private overlay was built by copying today's exact SHA-verified 659-file live tree, then adding only the two old staged SaaS page payloads and three collision-free hashed assets, with all 10 released V2 page files and six assets preserved byte-for-byte. There were no collisions.

- Candidate path: `/home/ubuntu/empire_releases/seo_saas_20261024_after_v2/out`.
- Complete baseline-and-candidate SHA manifest: `/home/ubuntu/empire_releases/seo_saas_20261024_after_v2/REBASED_CANDIDATE_RECEIPT.json`, SHA-256 `f8d377850a508f0ecef2d1a15c43f70bc25b1c8fe40e2c34c2ea4996509b84a0`.
- Existing files to replace: `predictive-revenue.html`, `predictive-revenue.txt`.
- Exactly three new static assets: `_next/static/chunks/app/layout-35080f83a6c7396a.js`, `_next/static/chunks/app/predictive-revenue/page-8a641c1798fea86e.js`, `_next/static/css/1e15dd81fb46e134.css`.
- Result, when separately authorised: 659 → **662** site files; 657 of the existing 659 files remain byte-for-byte unchanged.
- The existing single required-consent form survives on both `/predictive-revenue` and V2 `/commercial`. The guide retains first-party links to `#deployment-request` and `/commercial#commercial-enquiry`; the commercial anchor is present. No new form, tracker, ad or backend.

## Fresh post-V2 private verification

Adapted the existing website owner's GET-only local Chromium smoke in the private release folder, not in production source. Verified Predictive Revenue and the **newly published V2 roofing page** at 320, 390, 820 and 1440 pixels, with 8 passed route checks, 2 passed `/commercial` navigation checks, zero browser errors, zero missing assets, zero external requests, zero non-GET requests, zero form submissions and no overflow. Evidence path `BROWSER_SAAS_AFTER_V2_QA.json`, SHA-256 `e96b3d46da57233fd9988970f6b9cdbc1a7875ace066cf52999fb76a72d9bc09`.

Ran two full isolated site-copy transactional rehearsals using the existing exact atomic copy/swap helper. The success path reproduced all **662** candidate hashes; an intentional post-write verification failure triggered rollback and restored all **659** original V2 file hashes. Both cases preserved the published V2 pages. Evidence file `SAAS_AFTER_V2_PRIVATE_ROLLBACK_QA.json`, SHA-256 `2940a21d4edc68b52b2e4e2b634faaa26a1a93853607a18bd2f8a4d1bac56a3a`.

## Remaining gates — no inferred release authority

1. The original Website & Growth founder/owner reviews the exact new **659→662** candidate and authorises ONLY its two Predictive Revenue payloads and three new hashed assets. Earlier V2 approval is not this separate approval.
2. Authorised root website owner takes and fully verifies a **fresh current 659-file protected rollback** under the original release process. The V2 prepublication 653-file backup cannot restore this newer baseline.
3. Existing owner stages an exact lock-serialised release against the 659-file pinned manifest; fail closed on any concurrent public file change, test/lock/receipt collision or unapproved asset. Do not run the V2 publisher a second time or do a full Next.js export sync.
4. Independently verify receipt, exact served page bytes, assets, canonical, consent, `/commercial` and `/privacy` after the owner's release. Only authentic visitor submissions with specific consent and canonical EmpireDB/Smart CRM receipt can become qualified enquiries. No simulated submissions or inferred SEO-derived revenue.

**Production status:** Industry Enquiry V2 is live and independently validated. The new SaaS guide remains **private, tested, not approved for public release**. No live site changes occurred during this re-stage. The latest observed original GTM snapshot (2026-10-24T10:36:17.878585+00:00) recorded zero canonical first-party sales enquiries, with no outbound or payment.
