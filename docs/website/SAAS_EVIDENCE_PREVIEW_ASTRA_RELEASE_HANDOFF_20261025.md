# ASTRA Website & Growth — Exact SaaS Evidence Preview Release Handoff

Date: 25 October 2026. **Founder authorisation received, independent original website-owner gate and root-backed rollback STILL HELD.** Never interpret this document or the founder chat as ASTRA's separate sign-off.

## Exact scope and pinned evidence

This concerns the existing public `/predictive-revenue` page only. Candidate generated from the existing EmpireOS source, isolated static export and browser checks:

- Live approved baseline: **662 files** verified against the existing root/site pinned manifest.
- Candidate: **672 files**, exactly 660 unchanged old files, two paired replacements `predictive-revenue.html` and `predictive-revenue.txt`, and ten new-only noncolliding `_next/static/` assets.
- Former HTML SHA-256 `7144c99317d5a38d2f44e94bdd992bb26a6544a1626a0cab8973d25b9e0c9e9a`, replacement `1eaaa66e633967d553b18ebe3ed5180af36a555778c2efce4235679e1fc31053`.
- Former RSC SHA-256 `6d730f3f9c34a0052c944e05bbddfcaa940fcbdd5056d7dc61afb1ef6c9d9f43`, replacement `9ec0c0306c41b0b8c3311027d662abe9334033d46a8fba1b660a98857c988563`.
- Candidate root: `/home/ubuntu/empire_worktrees/saas_evidence_preview_20261025/candidate_union_20261025` **staged only, NOT published**.
- Candidate hash receipt `docs/website/release_candidates/SAAS_EVIDENCE_PAIRED_UNION_20261025.json`, SHA bound to founder approval.
- Founder approval `docs/website/release_candidates/SAAS_EVIDENCE_FOUNDER_APPROVAL_20261025.json` records user statement **"yes go on"** made after the exact release boundary was explained; `founder_approval_for_exact_candidate=true`. It records `publication_authorized_now=false` pending other gates.
- Isolated browser/navigation `docs/website/release_candidates/SAAS_EVIDENCE_NAVIGATION_QA_20261025.json`: original Commercial -> Predictive Revenue navigation renders fresh preview and original enquiry, zero HTTP errors, JavaScript errors or POSTs. Remote Chrome test does not prove a real buyer submission or end-to-end Smart CRM delivery.
- Code checks: `scripts/review_saas_evidence_release_candidate_20261025.py` runs GET-free/read-only full baseline and candidate verification; new owner-publisher `scripts/owner_publish_saas_evidence_20261025.py` is root guarded. Six synthetic owner-publisher safety/rollback tests passed, but a privileged real-world release remains unexecuted.

## Protection/rollback state

A user-owned **staging-only** archive of the complete 662-file live baseline has been created and hash-verified (10,839,781 bytes) under the private directory

`/home/ubuntu/empire_releases/saas_evidence_preview_rollback_20261025/live_662_rollback_stage.tar.gz`

Archive SHA-256 `661f1daf77e0b4719b0178b4c52c2e71eaffc5711f335f04f24c2e35837dfe46`. Directory mode 0700, archive mode 0600. Source 662 hashes were verified before and after creation and tar members checked. **This is not root-owned, is not an ASTRA-approved rollback, and must never count as satisfying the production backup requirement.** `/var/backups/empire-website` is root-owned mode 0700 and inaccessible to the connected ubuntu role.

## Original ASTRA website release owner actions

1. Independently inspect current live site, source/brand and mobile/desktop previews; reconcile any newer website changes, and inspect published privacy/consent plus route parity. Do not overwrite newer unrelated content. Verify `/predictive-revenue` page and RSC pair are still the intended release versions and check that the current 662-file baseline is exactly unchanged.
2. Run the read-only preflight using the currently pinned repo: `/srv/empire_os/.venv/bin/python -B -m scripts.owner_publish_saas_evidence_20261025 --preflight`. This intentionally reports **FOUNDER_APPROVED_AWAITING_ORIGINAL_WEBSITE_OWNER_ROOT_CUSTODY**; it does NOT grant automatic publication.
3. In a separately authorised **root-owned original ASTRA release session**, capture a full protected rollback in exact file-relative `tar.gz` form at `/var/backups/empire-website/saas-evidence-20261025-root-backup.tar.gz` mode **0600**. The root directory must be uid 0 and mode **0700**. Read back and independently hash all **662 archive entries** against the original approved site inventory. The owner operator code checks these conditions again.
4. Original ASTRA website owner, *after independent visual/commercial/legal acceptance*, creates their separate **root-owned mode 0600** receipt at `/var/backups/empire-website/saas-evidence-20261025-website-owner-approval.json`. It must contain **exactly grounded values**, not copied guesses: `schema_version="empire.website.saas_evidence_owner_release_authority.v1"`, `original_owner="EXISTING_ASTRA_WEBSITE_RELEASE_OWNER"`, `independent_website_owner_review_complete=true`, `approval_for_exact_paired_route_release=true`, `founder_approval_sha256` equal to actual founder receipt SHA, `candidate_inventory_sha256` equal to freshly verified candidate inventory from the immutable manifest, `root_backup_archive_sha256` equal to freshly verified root archive hash, and `publication_performed=false`. The mode/UID and archive hash are enforced. **No such ASTRA receipt currently exists in evidence available to this build lane.**
5. Only with that independent owner authority, an eligible original root release operator may run the separately gated exact action `/srv/empire_os/.venv/bin/python -B -m scripts.owner_publish_saas_evidence_20261025 --apply-owner-approved-saas-evidence-paired-route`. It locks to prevent duplicate execution, requires real root privileges and a matching full root-owned rollback, rechecks both complete site inventories and expected 12-file delta, adds only the ten hashed assets, atomically swaps the paired HTML/RSC files, checks the complete postpublication inventory and emits a protected root receipt. It attempts rollback on error. It does not change DNS, Cloudflare, other pages, checkout terms, CRM, money or outbound.
6. Existing ASTRA owner still performs after-publication live origin and public GET smoke, site navigation, mobile/desktop rendering, and receipt/release/rollback reconciliation. A successful byte swap alone does not verify public availability or conversion.

## Verified current hold and safety

The connected remote session cannot access `/var/backups/empire-website` as root; it has **not** created the root-owned archive, the ASTRA independent approval receipt or published the site. Direct user-mode file writes to the live 662-file static tree are forbidden in this release lane. Founder approval is preserved for this particular 12-file delta only; if the candidate or live baseline changes, stop and obtain fresh approval of the reviewed delta.

**Success criteria after authorised publication:** exact 672-file live inventory, no unreviewed changes, matching HTML+RSC payload, all assets available, original form works without synthetic submissions, independent owner/root publication receipt and live GET inspection. Do not claim a customer, inbound conversion or revenue until genuine independently verified events occur.
