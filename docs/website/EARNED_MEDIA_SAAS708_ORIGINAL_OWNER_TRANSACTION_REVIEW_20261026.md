# Original ASTRA website owner — 708-file atomic publisher transaction review

**Status:** private-only atomic transaction proof complete; source review proposed, no live publisher invoked.

The already approved and pinned **700-file production source** `f6cb9f0f541b041ebd5ca397c3c87268d89a70e086e26a16c1d2534dc13315df` and **708-file private candidate** `62b62b184d5597ffc806a825723c4638f2953702c823561233d30058e398dab2` were rechecked. Two existing SaaS routes need replacement; eight previously nonexistent content-addressed `_next/static/` files need addition. All 698 other source files, including the newer original SEO Commercial page, remain unchanged.

## Executable development proof

`empire_os/earned_media_saas708_atomic_private_trial.py` implements an exact-scoped disposable copy transaction:
- Fail closed if source/candidate full indexes differ from **literal approved hashes**, if routes differ from exactly `predictive-revenue.html` and `predictive-revenue.txt`, if any original files disappear, or if there are anything other than eight new `_next/static/` assets.
- Exclusively creates each new asset (`O_EXCL|O_NOFOLLOW`), checks each hash, then replaces each SaaS route atomically with a flushed and fsynced temporary file.
- Checks the entire 708-file final inventory against the original candidate manifest.
- On failure, restores the two original route bytes and deletes the new assets only when their bytes still match this transaction's expected values; refuses to overwrite any detected concurrent conflict.
- Refuses **actual production site and staged candidate as destinations**, limits writes to disposable temporary directories and has **no production CLI, root escalation, approval receipt, payment or CRM code**.

Run the repeatable **six full-size scenario** proof as the ordinary user:

```bash
cd /home/ubuntu/empire_worktrees/earned_media_advisory_bridge_20261025
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.rehearse_earned_media_saas708_atomic_transaction_20261026
```

Receipts: `docs/website/release_candidates/EARNED_MEDIA_SAAS708_PRIVATE_ATOMIC_TRANSACTION_20261026.json`. It proved one exact 700→708 private publication and **five** injected failure recoveries (`before`, `after_assets`, `after_first_route`, `after_all`, `post_apply`), each restoring the exact 700-file baseline. The full site and candidate source remained immutable.

The independent existing source/archive backup proof is at `docs/website/EARNED_MEDIA_SAAS708_ROOT_ARCHIVE_DIRECT_AUDIT_20261026.md`. The founder supplied original sudo archive creation stdout; the reported protected archive SHA matched a privately verified **700-member** archive. A direct root-only member audit **has not** been independently observed from this development shell, and original ASTRA owner approval **has not** been supplied.

## What the original ASTRA owner must do before any deployment

This is **not a production root publisher**. It deliberately does not handle privileged file ownership restoration, a root-authenticated lock, independent protected receipt attestation or live HTTP post-publish gates. The original owner must review and port the isolated transaction semantics into its own trusted root-owned publishing process, with its own race/concurrency policy, filesystem permissions, independent rollback verification and precise receipt semantics.

Do not run this user-owned worktree code as root. Do not run the original `scripts/owner_publish_saas_evidence_20261025.py`: it is pinned to obsolete 672-file/10-asset scope. Do not manufacture the independent original ASTRA signoff from a founder approval or this workstream's private tests.

**Original owner decision still pending:** independently verify root archive, source/brand/mobile/consent and Commercial HTML/RSC parity, review the newly scoped atomic transaction, authorise via its protected owner receipt and perform a separately controlled release. After release, prove public HTTP/browser acceptance and attribute only genuine opted-in enquiries through the canonical Smart CRM.

No production site changes, buyer submissions, outbound, funds or verified commercial revenue were caused by this prototype.
