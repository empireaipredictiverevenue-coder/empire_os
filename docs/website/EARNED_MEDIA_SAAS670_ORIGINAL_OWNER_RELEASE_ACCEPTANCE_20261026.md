# ASTRA original website owner — revised 670-file public release acceptance

**26 October 2026. Status: RELEASE HELD, private candidate tested, no production publication.**

## Exact requested website change

The **live website currently has 662 files**. The revised original SaaS guide/evidence + consented commercial CTA release has **670 files**: replace *only* `predictive-revenue.html` and its paired `predictive-revenue.txt`, add **eight** new noncolliding `_next/static/` hashed assets, preserve all other 660 existing files byte-for-byte. Five more recently updated pages (including `commercial.html`) are preserved.

**Live full inventory SHA-256:** `e894e2a9134ad13c6612f886c59b54da72b9c4791947dd0429e912723f0cdaa9`.

**New candidate full inventory SHA-256:** `2d37c7537329914fcecf531b34ff6fbeec42413da7dd42f5d5e4174f1411742b`.

**New HTML:** `f963b929c7601c8d831cd0483308ead0b0556520923ffb38c79a77944d3bc32f`.

**New RSC:** `d3b0b6ab9527047dc3d9271e37d110fd2485d015704cf4bfbcb0d91aabbbb0b7`.

The new CTA leads to the *existing* contact-consented commercial form: `/commercial?entry=%2Fpredictive-revenue#commercial-enquiry`. Page markup, React hydration, real browser click and visible checkbox have been verified **only on the local private candidate**, not on the public domain. Read-only catalogue GETs passed with 0 4xx/5xx, 0 JavaScript errors, 0 external requests and **0 POSTs**.

Private candidate: `/home/ubuntu/empire_releases/earned_media_saas_union_20261026/rebased_candidate`.

The prior ASTRA approval, release code and issue #103 were all for a **different 672-file / 10-asset candidate**. Their exact hashes are NOT valid approval for this release. The original `scripts.owner_publish_saas_evidence_20261025` is incompatible and must not be run for this candidate.

## New owner preflight

```bash
cd /home/ubuntu/empire_worktrees/earned_media_advisory_bridge_20261025
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_earned_media_saas670_owner_authority_20261026 --preflight
```

The CLI is **GET-free, read-only, and has no --apply option**. It evaluates fresh source and candidate inventory hashes, the original browser QA receipt's pinned SHA, scope (2+8), exact new founder approval, root-controlled backup and independent ASTRA owner approval.

**Last observed:** three evidence gates missing:
- Fresh explicit founder signoff **for this exact new inventory hash** (not the superseded 672-file approval). A newly and genuinely founder-approved scoped document can use `empire.website.saas670_founder_exact_approval.v1`, with `decision="FOUNDER_APPROVES_EXACT_REVISED_662_TO_670_PAYLOAD_FOR_ASTRA_REVIEW"`, the live/candidate hashes and owner ID. This packet does **not** create, presume or solicit that approval.
- A **root-owned full 662-file protected rollback**, with member-by-member byte hashes and mode-0600 archive inside root-controlled mode-0700 `/var/backups/empire-website`. The user-owned private rehearsal archive `8d80f0d...` is not sufficient.
- A distinct original ASTRA owner approval with independently verified brand, desktop/mobile, legal/consent and site source review, matching this candidate, fresh founder receipt digest, and the root archive digest. It must be mode 0600, root-owned. The existing Commercial HTML vs RSC page-title mismatch still needs independent owner treatment.

**Owner paths reserved as contracts; NOT CREATED by this workstream:**
- Founder exact-scope receipt: `/srv/empire_os/docs/website/release_candidates/SAAS670_FOUNDER_EXACT_APPROVAL_20261026.json`.
- Protected backup: `/var/backups/empire-website/saas670-pre-release-20261026.tar.gz`.
- Independent original ASTRA receipt: `/var/backups/empire-website/saas670-original-astra-owner-authority.json`.

Even if all receipt gates eventually verify, **this preflight does NOT perform publication**. An independently reviewed original-owner, root-guarded atomic publisher matching 2 route replacements + 8 immutable asset additions must then use a fresh root rollback, publication receipt and live HTTP/browser acceptance. No production deployment, restart, CRM write, outbound, funds or actual buyer event is authorised by the preflight.

## Tests and reproducibility

- Full 662 → 670 private overlay and 670 → 662 byte-exact private recovery passed using an independently verified *user-owned* archive.
- `docs/website/release_candidates/EARNED_MEDIA_SAAS_PRIVATE_RESTORE_REHEARSAL_20261026.json` records the result.
- `docs/website/release_candidates/EARNED_MEDIA_SAAS_REBASED_BROWSER_QA_20261026.json` records isolated browser testing.
- Current missing receipt gate contract lives in `empire_os/earned_media_saas670_owner_preflight.py`; tampered founder/source/browser/old approvals are tested.
- Existing owner issue: https://github.com/empireaipredictiverevenue-coder/empire_os/issues/103.

**Commercial conversion remains unverified:** A source-hint query string is not validated buyer identity, CRM delivery or realised revenue. We will attribute real enquiries only after authentic buyer consent and tenant-authorised CRM evidence.
