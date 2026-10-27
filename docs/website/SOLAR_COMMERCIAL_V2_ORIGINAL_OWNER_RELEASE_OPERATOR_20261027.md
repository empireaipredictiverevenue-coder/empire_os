# Solar + Commercial V2 — original ASTRA owner release-operator review

**Review-only implementation, not a running publisher, new agent, scheduler, approval or live website release.**

This candidate reuses the original website's rollback-capable transaction helper from scripts.release_predictive_roofing_two_page_20261022.apply_four_pages_and_eight_assets for the already reviewed Solar + Commercial V2 release. No changes were made to the older publisher or other owners' website source, checkout, data, or service.

## Exact owner review

- Isolated script: scripts/owner_review_solar_commercial_release_20261027.py
- Isolated tests: tests/test_owner_review_solar_commercial_release_20261027.py
- Immutable V2 packet: /home/ubuntu/empire_releases/website_solar_commercial_premium_20261026_candidate_v2/
- Existing owner pickup: docs/website/release_candidates/SOLAR_COMMERCIAL_V2_ASTRA_OWNER_PICKUP_20261026.json (already in the original repo; not duplicated)
- Owner issue: https://github.com/empireaipredictiverevenue-coder/empire_os/issues/128

Source commit d7229c635. Manifest SHA-256 14b65c040e398d74ac637f0845d2fd62046e7e0db9bb2eefdc348dabf1919f39.

The original 700-file site becomes 710 files only through replacing 10 existing Solar/Commercial HTML+RSC payloads and adding 10 immutable assets. All other 690 files remain unchanged.

## Root rollback evidence

Founder-run original backup: /var/backups/empire-website/solar-commercial-v2-before-20261027.tar.gz

Expected archive SHA-256: 4e7bb1ea2c8fbb81d99ff59e8debdff3b28f20826e1738278af452494f9b3bff

Root-only audit requires root-owned private 0700 directory, root-owned 0600 one-link archive, correct archive SHA and all 700 member SHA hashes matching the full original live inventory.

## Non-publication checks

Read-only V2 candidate preflight:

    PYTHONPATH=/home/ubuntu/empire_worktrees/solar_commercial_owner_release_review_20261027 /srv/empire_os/.venv/bin/python -B /home/ubuntu/empire_worktrees/solar_commercial_owner_release_review_20261027/scripts/owner_review_solar_commercial_release_20261027.py --preflight

Root-only read-only protected archive audit (NO PUBLICATION):

    sudo env PYTHONPATH=/home/ubuntu/empire_worktrees/solar_commercial_owner_release_review_20261027 /srv/empire_os/.venv/bin/python -B /home/ubuntu/empire_worktrees/solar_commercial_owner_release_review_20261027/scripts/owner_review_solar_commercial_release_20261027.py --audit-protected-backup

Expected root audit status: ORIGINAL_700_FILE_ROOT_BACKUP_INDEPENDENT_READBACK_VERIFIED. Stop review on mismatch.

## Original owner signoff is still required

The live action named --apply-exact-owner-approved-solar-commercial-v2 is gated and MUST NOT be invoked before ASTRA's own separate approval. It is root-only and requires a distinct ASTRA owner-created root 0600 JSON approval at:

    /var/backups/empire-website/solar-commercial-v2-astra-owner-approval.json

The receipt must record actual independent design, legal/copy and consent review, exact founder visual acceptance, the source commit, candidate SHA, backup SHA, 10 replacements/10 additions, and no prior publication. The script never creates or grants approval. Do not fabricate attestation from the founder's general chat permission.

Once and only once truly approved, the original owner may review its guarded action: verify complete original 700-file inventory, original root backup, separate owner attestation, two old-route origin GETs and six neighbouring route hashes, then reuse the existing atomic transaction to install the 10 additions and replace only 10 route files. Check the entire 710-file inventory, two new origin HTML GETs, six unchanged neighbour GETs and 10 immutable assets before sealing an exclusive root publication receipt. Any exception triggers the reused transaction's original scoped rollback. Do not change the SEO gateway or other services.

Public HTTPS browser smoke and real consent/catalog checks must follow original-owner publication; a static release alone is not proof of a genuine buyer or revenue.

## Review proof

Seven local tests cover exact scope, pinned immutable candidate, nonroot blocked live action, unprivileged protected backup blocked, untrusted owner backup directory blocked, success on a full disposable site copy and forced post-install rollback to all 700 original hashes. No live file, CRM, DB, payment or outbound changes were made.

**Use the existing ASTRA website owner. Do not merge this into a separate concurrent website release, and do not use the old SaaS-only publisher.**


## 27 October — founder exact visual/copy/displayed-pricing approval

The founder explicitly responded "yes i approve" to the exact request for approval of the final Solar and Commercial V2 designs, copy, and displayed pricing. The original repo saved the complete SHA-bound chat authority evidence at:

    docs/website/release_candidates/SOLAR_COMMERCIAL_V2_FOUNDER_FINAL_VISUAL_APPROVAL_20261027.json

Receipt SHA-256: 21ef90007ab15a08a91a0b48109fb0640032010249d7ed900971d026d6b23ee1.

This owner release code rejects a modified or missing founder approval receipt, checks that its screenshot hashes, manifest and source match the immutable reviewed candidate, and separately requires the ASTRA root-only approval receipt to cite the founder receipt SHA in the approved_founder_visual_receipt_sha256 field. If these bindings differ, no publication occurs. This founder approval is not a claim that ASTRA itself independently accepted or performed a release.
