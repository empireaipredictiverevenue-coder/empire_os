# Empire AI V2 — founder-approved exact-byte publication and recovery

**20 October 2026, founder approval explicitly supplied in ChatGPT.**
Founder instructed publication of 632-file release, exact inventory
SHA-256 `650318b7e8db14213cb115eb5adc90be846f1d6681142d04e9c293bd135bcfe3`,
with safeguarded rollback, live checks, no payment/outbound activation,
and continued improvements in separate releases.

This is approval of **website files only**, not new legal/editorial content,
settlement, outward messages, order creation or another agent.

## One-time deploy owner

`scripts/publish_approved_flagship_v2_20261020.py` is an explicit,
root-required, locked, single-use publisher. It verifies:

- The **exact** founder-approved 632-file inventory; source stage receipt,
  three key HTML page digests, gateway brand/art/font pins and private browser
  proof. The original October 13 buyer checkout manifest is unchanged.
- The original 603 published files still match root-protected archived
  rollback **byte-for-byte**, not merely a file count.
- The browser proof was rerun after the original private approval packet
  (one receipt hash changed), while all original source, candidate, page and
  rollback fields remained the same. Both old and fresh browser digests
  remain documented, with no silent repinning.
- No existing publication receipt, rollback switch or staging directory;
  source and stage never mutate during the switch.
- The atomic `renameat2(..., RENAME_EXCHANGE)` swaps the two directories
  in one filesystem operation. Previous published directory is retained
  outside the Git working tree and beside the candidate.
- Existing public gateway + checkout are checked by **GET only**: original
  HTML digest for `/`, `/buy`, `/commercial`; 200 for approved about and
  insights; JSON 200 for catalogue, tier and brokerage discovery; unchanged
  **404** for unauthorised roofing guide and treasury routes; checkout
  `payment_execution=false` and `revenue_recognition=false`.
- Both original gateway and checkout services, plus existing Ops timer,
  must remain active. Any failed verification automatically atomically
  reverts the public static directory to the prior exact version.

Payment features, CRM writes, outbound and currently gated editorial
routes must remain OFF; the script does not touch these systems.

## Operator command — execute only once

```bash
cd /srv/empire_os
sudo -n env PYTHONPATH=. .venv/bin/python -B \
  -m scripts.publish_approved_flagship_v2_20261020 \
  --apply-founder-approved-exact-v2 \
  --expected-inventory-sha256 650318b7e8db14213cb115eb5adc90be846f1d6681142d04e9c293bd135bcfe3
```

Expected result `EXACT_APPROVED_V2_WEBSITE_PUBLICATION_VERIFIED`
indicates post-publication checks passed. If any failed, status is
`WEBSITE_PUBLICATION_HELD_OR_ROLLED_BACK`; independently read the live
files and service health before another attempt.

Root-owned publication receipt will be created only after success:
`/var/backups/empire-website/FLAGSHIP_V2_PUBLICATION_RECEIPT_20261020.json`.

Original rollback tree:
`/home/ubuntu/empire_releases/flagship_checkout_union_20261020/out.pre-v2-public`.

Original protected tar:
`/var/backups/empire-website/flagship_current_live_20261020_before_union.tar`.

The deployment does **not** edit checkout's old 13 October historical
manifest. Its old strict canary must remain truthful against that historical
export; next website release-contract owner can supersede it in a new
versioned checkout verifier after inspecting the published V2 bytes.
Any further site changes require a fresh owner-attested candidate and
their own reversible release; do not rerun this one-shot publisher.
