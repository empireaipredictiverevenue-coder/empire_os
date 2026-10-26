# ASTRA Website & Growth — current 700-file live reconciliation (26 October 2026)

**Status: 708-file private candidate built, Chrome and private recovery PASS. Release HELD. No public site change in this workstream.**

## Why the earlier approved package cannot be used unchanged

The founder explicitly approved the older **670-file** packet `2d37c7537329914fcecf531b34ff6fbeec42413da7dd42f5d5e4174f1411742b` for ASTRA original website-owner review. That approval remains valid evidence of the earlier specific candidate; it does **not** authorise a different live baseline, changed payload inventory or immediate publication.

At the next read-only owner preflight, the site was no longer on the originally pinned 662-file source. A concurrent **original SEO/AEO commercial page entry-claim release** was already published at `/home/ubuntu/empire_releases/seo_aeo_entry_claim_v2_commercial_public_20261026/release_receipt.json`. Its receipt reports only `/commercial` changed plus 38 new immutable assets, with no other HTML pages, backend, outbound or CRM modifications. The live `commercial.html` SHA became `304605ef015372b24ccbf3274313476a3aa7ec06c32c10337c76f860f609d190`.

**Current observed live inventory:** 700 files, SHA-256 `f6cb9f0f541b041ebd5ca397c3c87268d89a70e086e26a16c1d2534dc13315df`. The original live `predictive-revenue.html` remained the older untracked CTA version with SHA `7144c99317d5a38d2f44e94bdd992bb26a6544a1626a0cab8973d25b9e0c9e9a`. Therefore the newly approved SaaS CTA still was **not** published.

No attempt was made to overwrite, roll back or “fix” this concurrent SEO release. Reusing the 670-file publisher, prior 662 source baseline or approval hash would now be incorrect.

## Exact 708-file private rebase

Using the original, already compiled and browser-tested 670-file SaaS route as an immutable source, an **isolated new private candidate** was created:

`/home/ubuntu/empire_releases/earned_media_saas_union_20261026/rebased_from_700_candidate`

- New candidate: **708 files**, SHA `62b62b184d5597ffc806a825723c4638f2953702c823561233d30058e398dab2`
- Only existing files changed: `predictive-revenue.html`, `predictive-revenue.txt`
- New-only, collision-free assets: same eight versioned `_next/static/` files as previous SaaS build
- All **698 other original live files**, including newer `commercial.html` and its recently published page JS/assets, preserved byte-for-byte
- The old founder receipt is **NOT** applied to the new 708-file source or candidate

Machine receipt: `/home/ubuntu/empire_releases/earned_media_saas_union_20261026/rebased_from_700_receipt.json`. Repeatable **read-only** check: import `empire_os.earned_media_saas700_reconciliation.verify` in the isolated worktree.

## Chrome and recovery verified

Chrome Headless private preview from the new SaaS page to the **newly published Buyer Readiness Commercial page**:
- Rebuilt SaaS CTA `/commercial?entry=%2Fpredictive-revenue#commercial-enquiry` persists after JavaScript hydration
- Correct versioned SaaS JS loaded, original SaaS preview present, Commercial form and required consent checkbox visible
- Actual browser title on destination: `Buyer Readiness & Revenue Intelligence | Empire AI`
- Zero external requests, POSTs, JavaScript exceptions or HTTP errors; no customer data submitted

Browser receipt: `docs/website/release_candidates/EARNED_MEDIA_SAAS708_CURRENT_SITE_BROWSER_QA_20261026.json`.

A new private user-owned **700-file** archive was created at `/home/ubuntu/empire_releases/earned_media_saas_union_20261026/private_700_baseline_backup/live_700_pre_708.tar.gz`, SHA-256 `65f7d9ab99a3808ea4e18922ef662c94365a1511d4e62c0019f03f92bbf220c7`. All 700 member bytes verified against live. It is **not root-owned** and does not replace ASTRA's production backup requirement.

Rehearsal copied 700 original files to a disposable private directory, changed only two routes plus eight assets to match all 708 staged file hashes, then simulated a failure and restored the exact original 700 file hashes from that private archive. The actual live tree and both original static candidates were not modified.

Rehearsal receipt: `docs/website/release_candidates/EARNED_MEDIA_SAAS708_PRIVATE_RESTORE_20261026.json`.

## Original owner action needed

1. Verify the current 700-file baseline remains stable and reconcile the original SEO/AEO entry-claim release under the single ASTRA website owner; do not overwrite the new Commercial work.
2. Independently inspect the new **708-file** candidate, current Commercial HTML/RSC metadata lineage, desktop/mobile visuals and consent/form parity.
3. Obtain **fresh explicit founder exact-payload approval** if proceeding with the 708-file candidate. The founder-approved 670-file receipt remains retained but is not transferable to a changed inventory.
4. Prepare a **new root-owned protected full 700-file backup** and independent original ASTRA owner approval bound to the *new* source/candidate digests.
5. Use an original-owner privileged publisher scoped only to 2 HTML/RSC route replacements and 8 new assets. It must verify the live site hash again immediately before a guarded publication and include independently tested rollback and public browser acceptance. The old 672-file/10-asset owner publisher does not match.
6. After publication, monitor real buyer-initiated enquiries and trace consented records through the original tenant-scoped Smart CRM; page clicks and browser source hints are not verified sales.

**Absolutely no website publication, send, CRM mutation, live consent submission, checkout/payment change or claimed revenue** was performed by this rebase.

Source: `empire_os/earned_media_saas700_reconciliation.py`, `scripts/qa_earned_media_saas708_current_site_browser_20261026.mjs`, `scripts/rehearse_earned_media_saas708_private_restore_20261026.py`.
