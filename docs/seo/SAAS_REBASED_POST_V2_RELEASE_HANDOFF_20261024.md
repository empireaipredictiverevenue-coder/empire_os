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

## 24 October: original website release operator prepared, NOT activated

Created a one-shot **guarded command inside the existing Website & Growth release workflow**: `scripts/publish_saas_guide_after_v2_20261024.py`. This is not a new application, DB, agent or publishing scheduler. It imports and reuses the original website root-protected backup, owner-lock and exact atomic/rollback helpers. Existing V2 source and release receipts remain untouched.

Read-only invocation:

```bash
cd /srv/empire_os
/srv/empire_os/.venv/bin/python -B -m scripts.publish_saas_guide_after_v2_20261024 --preflight
```

Observed status: `SAAS_659_TO_662_PREFLIGHT_PASS_PUBLICATION_NOT_APPROVED`. The command independently SHA-256 verifies all 659 current live files, all 662 private candidate files, the exact two page payload replacements and three immutable additions. It checks the existing commercial and predictive one-form/one-consent semantics, first-party CTA anchors, all hashed references, public GET hashes for protected V2 routes and exact pinned Chromium and private rollback evidence receipts. It fails closed on any source change, asset collision, prior release/backup receipt, altered QA, new external script or missing consent.

The publisher has a **distinct, immutable, exact founder-approval record** gate (`docs/website/release_candidates/SAAS_GUIDE_RELEASE_APPROVAL_20261024.json`) requiring the source-approved SHA-256 to be pinned in the operator. That record has **not been issued**, and `APPROVAL_SHA256` deliberately remains `None`. The previous industry V2 founder approval does NOT authorise this SaaS guide, and a command-line apply flag alone cannot give approval. Both unprivileged attempts and a simulated-root-but-unapproved attempt were confirmed to HOLD without acquiring the owner lock or making an archive.

When the founder separately approves the exact 659→662 scope, the existing release owner—not this read-only build—may prepare the specifically approved, SHA-pinned record and complete final owner review. The authorised root owner will then use the *same* private website lock (including the existing compatibility lock), create a fresh protected **659-file** archive at `/var/backups/empire-website/saas_guide_post_v2_pre_659_20261024.tar`, check every restored hash, apply only the two Predictive Revenue payloads and three new assets, verify the 662-file tree and served `GET` bytes, and write the distinct protected publication receipt. Any post-write failure triggers the existing narrow atomic rollback. No root access workarounds, sudoers changes, full-site export sync, automated outbound or financial actions are part of this scope.

Validation: `26 passed` across `tests/test_publish_saas_guide_after_v2_20261024.py`, `tests/test_publish_industry_enquiry_v2_20261023.py` and `tests/test_release_predictive_roofing_two_page_20261022.py`; Python compile passed. **Live site remains 659 files unchanged.**

## 24 October follow-through: verified actual first-party guide CTA navigation

The original SaaS guide's links were checked as **actual clicks in GET-only Chromium** on the existing 662-file private candidate; no form was submitted and no buyer identity, traffic, outreach or payment was invented.

- Private browser evidence: `/home/ubuntu/empire_releases/seo_saas_20261024_after_v2/BROWSER_SAAS_FIRST_PARTY_CTA_20261024.json`.
- Pinned SHA-256: `9819d069f9b259aa2dc920bba8580e18d522d67e8dacff7beac0fe21480abcdf`.
- At 390px mobile and 1440px desktop, both CTAs were clicked from the guide: `#deployment-request` stays on `/predictive-revenue` and lands on its existing form, while `/commercial#commercial-enquiry` loads the V2 `/commercial` route and lands on its original proposal form.
- Four of four checks passed: one form at each destination, mandatory work email input, one required but initially **unchecked** contact-consent checkbox, valid visible content. Zero browser errors, missing local static assets, external browser requests, non-GET requests and form submissions.
- The exact private evidence hash is now a fourth independent mandatory pin in `scripts/publish_saas_guide_after_v2_20261024.py`. A changed destination, missing/selected consent or corrupt receipt holds the original Website & Growth publisher rather than permitting release. New regression tests verify the fail-closed behavior.

Targeted website-owner and transaction suite: **28 passed**. Updated read-only SaaS preflight again reports `SAAS_659_TO_662_PREFLIGHT_PASS_PUBLICATION_NOT_APPROVED`; it does not issue permission, a root backup or publication.

Commercial attribution boundary: clicking a link or arriving at an anchor does **not** establish organic-search source identity or buyer consent. The original GTM/EmpireDB owner must verify the original buyer-submitted record and correct tenant-bound Smart CRM receipt. Do not infer SEO attribution from a navigation test, claimed entry value or a Search Console impression.

**Release remains held for founder's distinct exact five-file approval and new 659-file root-protected site backup.**
## 24 October 2026: founder EXPLICITLY approved the exact post-V2 SaaS release

The founder answered **'yes i approve'** to this precisely stated approval question: publish the existing verified **659-to-662-file** SaaS guide candidate, limited to two Predictive Revenue existing file payloads and three new hashed static assets, subject to a **fresh fully verified root-owned 659-file backup** and the original guarded owner release checks. This is separate from V2 approval and separate from the pending AEO HVAC candidate. No wider website or financial authority is implied.

The immutable approval record is `docs/website/release_candidates/SAAS_GUIDE_RELEASE_APPROVAL_20261024.json`, SHA-256 `92f241fa47a6844ad1df718a3ed2ce81c4bb201c8831a213d74031857d3c2083`. It is bound to the exact private candidate SHA-256 `f8d377850a508f0ecef2d1a15c43f70bc25b1c8fe40e2c34c2ea4996509b84a0` and the following **five** approved file paths:

1. `predictive-revenue.html`
2. `predictive-revenue.txt`
3. `_next/static/chunks/app/layout-35080f83a6c7396a.js`
4. `_next/static/chunks/app/predictive-revenue/page-8a641c1798fea86e.js`
5. `_next/static/css/1e15dd81fb46e134.css`

The original operator `scripts/publish_saas_guide_after_v2_20261024.py` now pins the approval record SHA and validates its full exact scope plus disallow flags for DB migrations, customer submissions, CRM writes, outbound, payments, full-site sync and unrelated AEO release. Read-only preflight now returns `SAAS_659_TO_662_FOUNDER_APPROVED_FRESH_ROOT_BACKUP_REQUIRED` with `separate_founder_approval_recorded: true`, `verified_root_backup_exists: false`, and `public_site_mutated: false`. The private candidate's historical fields remain explicitly NOT PUBLISHED/NOT LIVE by design; an independent approved record is the source of founder release authority.

**Owner action:** from the founder's existing authorised root-capable website operator terminal (not the constrained Remote Desktop integration), run:

```bash
cd /srv/empire_os
sudo env PYTHONPATH=/srv/empire_os \
  /srv/empire_os/.venv/bin/python -B \
  -m scripts.publish_saas_guide_after_v2_20261024 \
  --apply-founder-approved-saas-guide-after-v2
```

The publisher must hold the original root-private lock and legacy compatibility lock, check every pinned existing source and staged byte, create the fresh current **659-file** protected rollback archive, read back each archived member, perform only the five approved file changes, compare full 662-file live inventory, GET-verify updated `/predictive-revenue`, all new static assets and all protected routes, and write a versioned publication receipt. On any post-write verification failure, the existing narrow atomic transaction rolls back. This is a one-off, never a recurring task. **Do not rerun the already-completed V2 publisher**, manually copy assets, weaken permissions, or execute the stale 653-file SaaS overlay.

After root-owner execution, independently verify the exact receipt status `FOUNDER_APPROVED_SAAS_GUIDE_659_TO_662_PUBLISHED_AND_GET_VERIFIED`, corresponding backup checksum and fresh 659-to-662 file counts. A successful publisher output is necessary before saying the SaaS guide is public. The read-only command is still available:

```bash
cd /srv/empire_os
/srv/empire_os/.venv/bin/python -B -m scripts.publish_saas_guide_after_v2_20261024 --preflight
```

Targeted original website release, rollback and SEO observer suite **45 tests passed**. At the time of this founder approval record, production remains **659 files** and the AEO page remains unchanged; no customer sent a submission, no CRM rows or payments were created and no new outbound was authorised.

## 24 October 2026: founder-authorised public SaaS guide successfully applied

Founder supplied the result of the existing root-owner command, observed 2026-10-24T17:30:27.778848+00:00: `FOUNDER_APPROVED_SAAS_GUIDE_659_TO_662_PUBLISHED_AND_GET_VERIFIED`. It reports precisely two approved page payload replacements, three approved immutable assets, 657 preserved originals, 662 final live files, and a fresh backup of 659 original files with archive SHA-256 `13a91a09e064de6c3a35d0803c4640a3f51cacb45cc62aeb1fde80506c19e527`. Source `54601ed54`, approved candidate `f8d377850a508f0ecef2d1a15c43f70bc25b1c8fe40e2c34c2ea4996509b84a0`, founder approval `92f241fa47a6844ad1df718a3ed2ce81c4bb201c8831a213d74031857d3c2083`.

An **independent unprivileged read-only server observation** after publication confirmed all 662 live static files hash exactly to the approved candidate, all 657 unchanged existing file hashes preserved, both page payloads and all three hashed assets exact. GET /predictive-revenue, /, /commercial, /buy, and /industries/{roofing,solar,hvac,property} all returned the expected released static page SHA-256 with proper canonical URLs. All three new hashed assets served exact hashes. The SaaS guide and both first-party buyer CTAs are present; both original forms retain required work email and unchecked required consent. `/privacy` is separately served by the original website/API routes, returned HTTP 200 and contains the general Empire AI Privacy Policy; it was not part of the new Next static export.

Independent read-only verification receipt: `/home/ubuntu/empire_releases/seo_saas_20261024_after_v2/POST_RELEASE_INDEPENDENT_LIVE_GET_20261024.json` SHA-256 `e0918c8bf4fe7042cf72bcebaf5e3ebc72a8ec1e4950b7a1d779e94d763ff38f`.

**Custody nuance:** the root backup directory `/var/backups/empire-website` is root-owned mode 0700. The constrained unprivileged observer is correctly denied access and therefore cannot independently hash the root-only archive or inspect the publication receipt; `Path.exists()` false under that directory must not be interpreted as proof that the backup is absent. The founder's successful root-owner publisher receipt is the asserted backup evidence. A root owner can separately run read-only `sudo stat`/`sudo sha256sum` and inspect its protected JSON if stronger independent custody evidence is required. Do not weaken permissions.

The first GTM snapshot after release returned `HELD_CANONICAL_ACQUISITION_OWNER_OPS_RECEIPT_REQUIRED`. Buyer/enquiry count is **unknown** at that moment (NOT zero and not inferred revenue). No new form submits, CRM mutations, outbound or payments occurred in the independent GET checks. The SaaS guide is LIVE; no new release needed. Next stage: first genuine opted-in request, canonically reconciled through EmpireDB and original Smart CRM, then a commercially verified buyer reply and accepted scope. The separate DFW HVAC AEO one-link candidate is STILL PRIVATE and needs its own owner approval.

## 24 October — independent root-owner checksum returned, commercial receipt baseline

The founder ran the authorised root-only `sha256sum` over `/var/backups/empire-website/saas_guide_post_v2_pre_659_20261024.tar` and supplied the exact result `13a91a09e064de6c3a35d0803c4640a3f51cacb45cc62aeb1fde80506c19e527`. It exactly matches the backup archive SHA-256 the approved publisher reported. This independently reconciles root-owned archive bytes with the release receipt's hash; the publisher separately reported verifying 659 original files. The protected directory mode 0700 is preserved.

Post-publication `runtime/gtm_pipeline/integration_observer_latest.json` at `2026-10-24T17:39:51.856436+00:00` returned `CANONICAL_COMMERCIAL_SALES_INTAKE_ZERO_OBSERVED` with `source_count_verified:true` and commercial=0, predictive=0, total acquisitions=0. As with all time-dependent observers, subsequent `HELD_*` reads are **unknown**, not zero. No claim of a customer conversation or payment follows from a working website.

The original unprivileged founder CRM sales-visibility probe `scripts.probe_founder_sales_visibility_readonly` returned `NO_TENANT_VISIBLE_SALES_PROSPECTS` with visible commercial=0, predictive=0 and total=0, but it did NOT prove global canonical source count or exact receipt-to-tenant binding. The original privileged source aggregate and cross-lane reconciler correctly returned `BLOCKED` / `HELD_PRIVILEGED_READONLY_OPERATOR_REQUIRED` under the constrained remote session. No DB role change, fake CRM record, contact data read, outbound or payment occurred.

The exact next commercial milestone is one **genuine opted-in enterprise enquiry**, accepted by the existing `/v1/checkout/predictive-revenue/interests` or `/v1/checkout/commercial/interests`, with actual canonical EmpireDB source-evidence and tenant-bound Smart CRM receipt verified before any founder response or proposal. Before any claim of acquisition conversion, require a real buyer identity, evidence of specific-response consent and source/tenant authority; static page clicks, source URL guesses, GSC impressions, testing and outbound intentions are not proof. No simulated form submissions.

Future root-owner if needed, read-only aggregate reconciliation without exposing personal details: `sudo env PYTHONPATH=/srv/empire_os /srv/empire_os/.venv/bin/python -B -m scripts.reconcile_founder_sales_handoff_aggregate_readonly --review-only`. This command is for the original authorised owner and is not a prerequisite for the already-completed website release.
