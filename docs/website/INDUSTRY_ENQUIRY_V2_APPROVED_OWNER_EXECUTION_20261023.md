# Founder-approved V2 surgical website publication — root website owner action

23 October 2026. Founder explicitly approved the *exact* V2 industry-to-enquiry
website release, followed by V3 as a separate subsequent release.

Source: commit `758a5a31b`.
V2 manifest: `docs/website/release_candidates/INDUSTRY_ENQUIRY_SOURCE_HANDOFF_20261023_V2.json`.
Manifest SHA-256: `d41167d3e2413dbfe914bf8f0527ef0da26da3df0723aff8eaa3c1b9f86065aa`.
Original existing-owner transaction reused in:
`scripts/publish_industry_enquiry_v2_20261023.py`, committed `1477fed0d`.

## Execution status — BLOCKED, NOT LIVE

Read-only preflight passed: all current live 653 files, the 10 original HTML/RSC
files to replace, the 6 proposed immutable assets, staged source commit and
original HTTP route bytes match the pinned contract.

The remote-access policy refused the attempted privileged publication command
before it ran. The remote agent **must not bypass that privileged owner policy**
or manually replace the public export as the unprivileged website account.

No root-protected fresh backup, publication receipt, or live file mutation has
been established by this attempt. V2 must **not** be called publicly deployed.

## Exact root-owner console instructions

The original, authorised website release operator uses an already privileged,
root-controlled terminal under its usual security policy. Do not expand
existing permissions to make the command run.

Read-only preflight:

```bash
cd /srv/empire_os
/srv/empire_os/.venv/bin/python -B -m scripts.publish_industry_enquiry_v2_20261023 --preflight
```

One-time exact founder-approved publication, run by the **existing authorised
root website owner**, not by an unprivileged session:

```bash
cd /srv/empire_os
env PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.publish_industry_enquiry_v2_20261023 \
  --apply-founder-approved-industry-enquiry-v2
```

If the root owner cannot run the command under their normal permission model,
keep the site unchanged. No alternate privilege route or direct file copying.

The guarded script first creates a fresh protected full-site 653-file rollback
tar at `/var/backups/empire-website/industry_enquiry_v2_pre_653_20261023.tar`,
with mode 0600, and independently verifies every archived file hash. Only
after successful backup and unchanged production-inventory checks does it use
the existing site transaction core to install exactly 10 pinned page files and
6 new immutable assets. All 643 unrelated original files are preserved.

The script checks the entire 659-file resulting static tree and served HTTP
GETs, including unchanged home page, /buy, Predictive Revenue, privacy, and
the existing commercial offers API. Failed checks trigger narrow rollback.
An authorised successful release writes a separate protected
`industry_enquiry_v2_pre_653_20261023.publication.json` receipt with exact
status `EXACT_APPROVED_INDUSTRY_ENQUIRY_V2_PUBLISHED_AND_GET_VERIFIED`.

Neither the preflight nor this written founder approval is a publication
receipt. Do not claim success until the privileged operator's receipt and
independent served-byte review agree.

After V2 live proof, V3 can begin in the same original Website & Growth
ownership chain, focused on verified UK/US inbound conversion and evidence
measurement. V3 must not be bundled with the approved V2 file set.

No synthetic enquiries, CRM writes, outbound messages, payments or model
training are authorised by this website-file approval.

## 23 October 2026: root publication lock ownership blocker isolated

The founder's authorised `sudo env PYTHONPATH=/srv/empire_os ... --apply-founder-approved-industry-enquiry-v2` invocation reached the root code path but failed opening `/var/lock/empire-industry-enquiry-v2-release-20261023.lock` with Linux EACCES. This is **not** another founder approval request: manifest and current 653-file live preflight still pass.

Read-only diagnosis: `/var/lock` points to `/run/lock`, a root-owned `1777` sticky directory. The precise existing regular lock file is owned by `ubuntu:ubuntu` (UID/GID 1000), mode `0600`, length zero. `fs.protected_regular = 2`; the publisher opens the lock with `O_CREAT|O_RDWR|O_NOFOLLOW`, so an existing user-owned file in a sticky directory can be refused even to root. The original unprivileged attempted publisher invocation created the file **before** checking effective UID. No active publisher process or unprivileged-visible file holder was found, but authorised root-owner should independently check with `sudo fuser` before touching the lock.

**Permanent code correction**: owner script `scripts/publish_industry_enquiry_v2_20261023.py` now refuses non-root before its lock creation. Two regression tests cover held unprivileged no-lock behaviour and the existing exact one-lock root code path using a no-op publisher. `13 passed` across the website owner publisher tests and existing controlled publisher transaction tests. This does not grant elevated privileges, auto-run publication or widen the approved site release.

**One-time legitimate authorised root-owner remedy**: verify exact pathname and ownership, ensure no live lock holder, then change ownership of *only* the existing zero-length Ubuntu-owned `run/lock` file to root:root while preserving mode 0600. Never delete the lock to skip contention; never lower `fs.protected_regular`, loosen the sticky-directory or lock permissions, add sudoers entries or run parallel publishers. The owner should then re-run the already-approved exact V2 publisher with current normal `sudo` credentials, and verify its protected current 653-file backup, 659-file site and publication receipt. If any preflight fails, hold and inspect. The unprivileged remote assistant did not modify `/run/lock`, create a privileged backup, publish website files or send messages.

## 23 October lock-file recovery amendment

Root publication previously returned
`[Errno 13] Permission denied: '/var/lock/empire-industry-enquiry-v2-release-20261023.lock'`
because the initial unprivileged invocation had created the original 0600
lock as `ubuntu` inside the kernel-protected sticky `/run/lock` directory.
The kernel has `fs.protected_regular=2`; root opening the existing user-owned
file with `O_CREAT` is denied. The original legacy file was unheld in the
read-only inspection and **was not removed or altered**.

The existing owner publisher now uses a **root-owned mode-0700 backup
directory** for its new private release lock:
`/var/backups/empire-website/.industry_enquiry_v2_20261023.release.lock`.
Only the authorised root owner may execute. It validates the directory owner,
permissions and absence of symlinks; verifies the lock file is root-owned,
regular, one-link and 0600; and acquires an exclusive nonblocking lock.
When the original legacy lock exists, it also opens that same inode
**read-only without O_CREAT**, verifies regular one-link file status and
takes a second exclusive nonblocking lock. Both locks remain held throughout
the original guarded publication. This maintains concurrency safety while
avoiding Linux's protected-regular-file denial; it does not relax system
security settings, delete or chown the old lock, or bypass root authority.

The guarded live preflight still checks exactly 653 original files, ten
replacements and six additions. Backup, immutable candidate, rollback,
consent and outbound policy remain unchanged. The operator still uses the
identical founder-approved command above; the software itself now handles the
legacy lock safely.
