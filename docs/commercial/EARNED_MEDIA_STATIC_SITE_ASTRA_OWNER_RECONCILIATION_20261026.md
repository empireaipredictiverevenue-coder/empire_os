# EmpireOS earned-media CTA — actual public website release reconciliation

**Observed:** 26 October 2026, read-only on EmpireOS. **Status: ASTRA ORIGINAL RELEASE OWNER PICKUP REQUIRED. NO PUBLICATION AUTHORISED OR EXECUTED.**

## Verified public-site serving path

The active public gateway (`empire_os/public_gateway.py`) serves `/predictive-revenue` from `/srv/empire_os/apps/empire-public-site/out/predictive-revenue.html`. A two-source-file React/TypeScript patch does **not** update the deployed HTML route or its associated static Next.js assets. The live HTML contains exactly one old `/commercial#commercial-enquiry` link and no proposed new source-hint link. Its SHA-256 remains `7144c99317d5a38d2f44e94bdd992bb26a6544a1626a0cab8973d25b9e0c9e9a`. The live paired `predictive-revenue.txt` SHA-256 is `6d730f3f9c34a0052c944e05bbddfcaa940fcbdd5056d7dc61afb1ef6c9d9f43`.

Existing ASTRA SaaS preview `/home/ubuntu/empire_worktrees/saas_evidence_preview_20261025/candidate_union_20261025` has pending HTML SHA-256 `1eaaa66e633967d553b18ebe3ed5180af36a555778c2efce4235679e1fc31053` and RSC SHA-256 `9ec0c0306c41b0b8c3311027d662abe9334033d46a8fba1b660a98857c988563`. Its HTML also contains the old CTA once and none of the new `/commercial?entry=%2Fpredictive-revenue#commercial-enquiry` CTA. That separate 2-route/10-hashed-asset candidate has existing founder review, protected backup and original ASTRA owner signoff requirements; do not replace it with a competing static export.

## Independently reproduced actual site preflight hold

`/srv/empire_os/.venv/bin/python -B -m scripts.owner_publish_saas_evidence_20261025 --preflight` returned `SITE_RELEASE_HELD_NO_PUBLICATION / LIVE_SITE_NOT_MATCHING_APPROVED_PIN`.

Full public-site index comparison: **662 live files / 662 pinned baseline files; identical file names; 658 unchanged hashes; 4 newer live pages differ**:

- `industries/roofing.html`
- `industries/hvac.html`
- `industries/property.html`
- `industries/legal-mass-tort.html`

These four existing live pages must be reviewed against original release receipts and preserved; never overwrite or roll them back just to make a stale preflight pass. An arbitrary manually changed pin would void the prior release and source-integrity approvals.

The existing live GET verifier returned `EXISTING_PUBLIC_PAGE_VERIFIED_NEW_PREVIEW_NOT_LIVE`; five governed Predictive Revenue products are visible, but source clicks, buyer consent submissions and settled cash are **not proven**.

## Reconciled ASTRA action — one coordinated release, no duplicate stack

1. ASTRA original website owner to inspect concurrent updates to these four pages, reconcile release receipts and rebase the full original static candidate on the verified current site while keeping newer approved content unchanged.
2. Review the exact two-source-file earned-media CTA patch at commit `a0075ac81`, `docs/commercial/EMPIRE_PUBLIC_OWNED_GUIDE_CTA_TWO_FILE_20261026.patch`. It is **source code only**. Do not apply the whole earned-media branch: private Founder UI and separate backend source cleanup are not in scope for a public-page CTA.
3. If ASTRA chooses to include CTA, rebuild/verify the existing `predictive-revenue.html` and paired RSC/static assets as one reproducible release; update the full static manifest SHA, rollback baseline, scope receipt and original owner signoff. Earlier founder approval is limited to its exact unchanged 12-file SaaS candidate and **must not be treated as new altered-payload approval**.
4. Verify the displayed CTA leads to existing `/commercial?entry=%2Fpredictive-revenue#commercial-enquiry` and preserves the existing opt-in/enquiry handler with no synthetic valid first-party submission, no external sending and no CRM/payment changes.
5. Only a separately authorised ASTRA/root operator applies the scoped published static files after protected backup and negative testing, then verifies public browser route, hashed assets, and the actual number of genuine buyer-initiated requests.

**Owner coordination:** existing GitHub issue [#103](https://github.com/empireaipredictiverevenue-coder/empire_os/issues/103) received updated reconciliation comment [#6418920264](https://github.com/empireaipredictiverevenue-coder/empire_os/issues/103#issuecomment-6418920264). This is notification, not evidence ASTRA has accepted it or authorised deployment.

**Non-events:** No live code/assets changed, no root release action or service restarts, no sent mail, no real enquiry created, no payment made or revenue verified by this reconciliation.
