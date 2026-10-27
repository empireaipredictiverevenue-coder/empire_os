# Empire AI — ASTRA original website release gate (708-file candidate)

**26 October 2026 · Exact-payload founder review approved · Publication not executed**

This handoff continues **the existing ASTRA website release**. No second website owner, independent agent, database, scheduler or privileged publisher was created.

## Current verified release contract

- **Current public source:** 700 files; full site inventory SHA-256 `f6cb9f0f541b041ebd5ca397c3c87268d89a70e086e26a16c1d2534dc13315df`.
- **New private candidate:** 708 files; full inventory SHA-256 `62b62b184d5597ffc806a825723c4638f2953702c823561233d30058e398dab2`.
- **Exact diff:** replace `predictive-revenue.html` and paired `predictive-revenue.txt`, plus add 8 immutable hashed static assets. Preserve all **698 other existing files**, including the already published original SEO/AEO Commercial page.
- **Approved source evidence:** the founder directly said “yes i approve” for this exact 708-file release **for ASTRA's final review only**, and subsequently approved continuing the remaining original-owner release checks. The exact founder receipt lives at `/srv/empire_os/docs/website/release_candidates/SAAS708_FOUNDER_EXACT_APPROVAL_20261026.json`, SHA-256 `9c50507dc469678b2e4f69c57bba035c6ea45c07832acab1d0dd89e7b9c67ee6`. It contains **no immediate public publication authority**.
- **Browser acceptance:** private Chrome navigation confirms the correct SaaS CTA, live SEO-updated Buyer Readiness destination title and visible consent checkbox. 0 POST, 0 JS errors, 0 external requests. Browser QA JSON SHA-256 `16e15e8ed3b888976045cda37312389a43d1415560044d8ab8bc0856cc6470fc`.
- **Private disaster-recovery rehearsal:** 700 -> 708 -> exact 700 file hashes in a disposable tree. User-owned private archive SHA-256 `65f7d9ab99a3808ea4e18922ef662c94365a1511d4e62c0019f03f92bbf220c7`. This test backup is **not** an original-owner root-protected production archive.

The live Predictive Revenue page remained on its previous SHA-256 `7144c99317d5a38d2f44e94bdd992bb26a6544a1626a0cab8973d25b9e0c9e9a` when last inspected. No public release has been performed by this workstream.

## Original-owner read-only gate

Run within the existing isolated review worktree using the existing EmpireOS Python:

```bash
cd /home/ubuntu/empire_worktrees/earned_media_advisory_bridge_20261025
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_earned_media_saas708_original_owner_20261026 --preflight
```

This checks all 700 source hashes, 708 candidate hashes, exact 2+8 scope, signed-off founder receipt bytes, isolated Chrome QA, and **only independently produced** protected rollback and original ASTRA owner release receipt. It has **no apply flag** and cannot create authorisations, send, submit or publish. Exit 2 is expected while separate owner gates are absent.

**Verified:** source/candidate, scope, founder approval, Chrome consented navigation. **Remaining:**

1. **Original owner protected backup**: Archive *all current 700 source files* under original root-owned `/var/backups/empire-website/`. The directory must remain root-owned mode 0700, archive regular/root-owned mode 0600, complete SHA-256 file-members equal the live source index. The owner acceptance scanner looks for `saas708-original-site-700-20261026.tar.gz` in that directory and fails closed if missing/unreadable/untrusted. The connected development terminal does not have authorised privileged access to create this archive, and no test copy is allowed to masquerade as it.
2. **Independent original ASTRA website owner authorisation**: The original owner independently reviews website brand, desktop/mobile, privacy/consent, Commercial HTML-vs-RSC metadata lineage, newer SEO/AEO Commercial release and its preserved files, exact source/candidate hashes, founder receipt SHA and fresh protected archive digest. Original owner then creates its own root-owned mode-0600 approval receipt `saas708-original-astra-owner-release-authority.json` in the protected backup directory, schema `empire.website.saas708_astra_owner_authority.v1`. Never create or claim this receipt on the founder's behalf.
3. **Separate controlled original-owner publisher:** The legacy original owner script is pinned to **672 files and ten assets** and must not be executed on the new 708-file candidate. The exact-root publisher should be reviewed and scoped to only two route replacements/eight new assets, recheck *fresh live hashes immediately before mutation*, exercise an independently verified rollback, and confirm public HTTP/browser acceptance. The read-only scanner explicitly cannot confer publication authority.

**Do not force the previous 662/670/672 baselines onto the current SEO-published 700-file site.** If the source changes again, stop and reconcile through the original website owner, not by overwriting concurrent releases.

## Real commercial result boundary

No actual buyer enquiry, consented source attribution, tenant CRM accepted opportunity, settlement or recognised revenue is established by these tests. Keep the original production buyer qualification and revenue evidence chain separate from browser CTA QA.

Existing ASTRA owner tracking: https://github.com/empireaipredictiverevenue-coder/empire_os/issues/103. Isolated artifact evidence is under `docs/website/release_candidates/EARNED_MEDIA_SAAS708_*`.
