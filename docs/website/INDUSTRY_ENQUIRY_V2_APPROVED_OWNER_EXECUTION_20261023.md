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
