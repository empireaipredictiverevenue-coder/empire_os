# Original ASTRA website release — protected backup operator action

**Current status (26 October 2026):** 700-file live site and 708-file private candidate still SHA-pinned. Founder approved exact 708-file package for *review only*. Root-owned release authority remains under the independently appointed original ASTRA website owner. This document neither approves nor publishes.

## Step 1 — original privileged website release operator only

The existing root-owned website backup directory at `/var/backups/empire-website` was observed as UID 0 and mode 0700. An ordinary `ubuntu` process cannot see its contents. The normal-user `--preflight` therefore reports **unverified**, which is NOT proof the archive does not already exist.

**Run the following only in the independently authenticated original website release-operator shell, after examining the current release inventory and confirming the site has not changed:**

```bash
cd /home/ubuntu/empire_worktrees/earned_media_advisory_bridge_20261025
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_earned_media_saas708_original_owner_20261026 --preflight
# Current read-only gate is expected to hold while original root evidence is inaccessible.

sudo sh -c '
set -eu
d=/var/backups/empire-website
a="$d/saas708-original-site-700-20261026.tar.gz"
test -d "$d" && test ! -L "$d"
test "$(stat -c "%u:%a" "$d")" = "0:700"
if test -e "$a" || test -L "$a"; then
  echo "PROTECTED_ARCHIVE_ALREADY_EXISTS_DO_NOT_OVERWRITE"
  exit 2
fi
umask 077
tar --format=posix -C /srv/empire_os/apps/empire-public-site/out \
  -czf "$a" .
test "$(stat -c "%u:%a" "$a")" = "0:600"
sha256sum "$a"
echo "ROOT_ARCHIVE_CREATED_REQUIRES_FULL_MEMBER_HASH_VERIFICATION"
'
```

**This is a backup-only operation**, with fail-on-existing destination. It does not modify the site or create independent ASTRA release authority. If a protected archive already exists, STOP: inspect it under original owner control; do not overwrite it. If tar errors or any site drift occurs, STOP; quarantine incomplete artifacts under the owner process and return to the current source reconciliation.

## Step 2 — original-owner privileged independent audit

After the archive exists, the original owner must verify the archive's 700 regular-file members, their SHA-256s against the exact current live inventory, archive root ownership and mode 0600, and that the live inventory still hashes to:

`f6cb9f0f541b041ebd5ca397c3c87268d89a70e086e26a16c1d2534dc13315df`

An unprivileged `ubuntu` preflight cannot read the root-only directory and **will still report unverified** even if the backup exists. The original owner can independently run the reviewed verifier with its own authorised privileged process, preferably from a separately reviewed root-owned code copy rather than executing a mutable `ubuntu` worktree as root. The pure audit implementation lives in `empire_os/earned_media_saas708_owner_preflight.py` as `verify_protected_site_backup()`; it makes no writes.

**The archive's SHA-256 alone is NOT enough to satisfy the integrity requirement.** An actual 700-member byte comparison is required.

## Step 3 — independent original-owner receipt and production decision

If the archive passes, the appointed original ASTRA website owner, **not the founder or this workstream**, verifies original SEO/AEO Commercial-page HTML/RSC title lineage, desktop/mobile visuals, legal/consent, exact two-route/eight-new-asset scope, immutable old/new source inventory and founder review receipt SHA:

`9c50507dc469678b2e4f69c57bba035c6ea45c07832acab1d0dd89e7b9c67ee6`

The original owner must create its own protected root-owned, mode-0600 authority receipt `/var/backups/empire-website/saas708-original-astra-owner-release-authority.json` only after completing that review. Its exact gate fields and schema are checked by `empire_os/earned_media_saas708_owner_preflight.py`. No script in this worktree creates, signs or fakes that receipt.

The original 672-file / ten-asset publisher must **not** be reused for the revised 708-file candidate. An original-owner reviewed replacement publisher must implement and test exact two-file replacement + eight immutable asset additions, full site hash comparison, root-owned rollback and live smoke checks under a separate publication decision. The founder's current review approval is **not** that final publication decision.

**Outcome:** No public release, CRM write, email, payment or revenue recognition is authorised or claimed by this backup-only handoff.
