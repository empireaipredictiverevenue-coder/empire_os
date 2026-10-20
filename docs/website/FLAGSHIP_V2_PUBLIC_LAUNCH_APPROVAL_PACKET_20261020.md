# Empire AI public site V2 — final exact-byte launch decision

20 October 2026. Canonical Website & Growth owner release control.

## Current state

**Exact static candidate independently build-verified: YES.**
**Public deployment approved: NO.**
**Live website switched: NO.**
**Existing payments, orders, email and ingestion affected: NO.**

The work is not waiting on another design/build iteration. This is the
founder/publication control point for one **specific** existing 632-file
release candidate: cinematic 3D flagship, current buyer checkout and
native first-party product-proposal routes while preserving published
legacy insight and about pages.

Private original candidate:
`/home/ubuntu/empire_releases/flagship_checkout_union_20261020/out`

Authoritative private proposed approval record (issued root-owned):
`/home/ubuntu/empire_releases/flagship_checkout_union_20261020/PUBLIC_V2_RELEASE_SIGNOFF_PROPOSAL.json`.

## Evidence-bound candidate identity

- Exact 632-file inventory SHA-256:
  `650318b7e8db14213cb115eb5adc90be846f1d6681142d04e9c293bd135bcfe3`
- Intended V2 home `index.html`: `061b03b39a22575a4ed79626e1ef44637a012345bcc9a855610b07e45871e209`
- Intended V2 buy `buy.html`: `435cd7b1fed3490998ec2ca74cd0fc68f1a6ff0a324a10adba6428def4e92552`
- Intended V2 commercial `commercial.html`: `c0f8518d0113ea30faf38cd4f2f769e80fd2ff46d715e4d86100cde6f4659b7f`
- Private original receipt SHA-256:
  `475daf56c67d0a1dd29f36d7d1ad93d94d7e89c4355bb7bb13abcc0a4361507d`
- Verified browser evidence SHA-256:
  `8e33be75643b28cc436ca877756ff865d8b6b55a2d86decf5aabc76df70ab601`

Source stage manifest and all 135 source-bound original files still
verify. Owner SHA-pinned public gateway visual/image/font assets:
**17/17 passed**. Private candidate static digest audit:
**632/632 passed**. Combined browser route and viewport checks:
**12/12 passed**. In-page mobile/desktop navigation:
**4/4 passed**. Zero JS errors, missing local assets or buyer POSTs.

Existing 2026-10-13 buyer checkout manifest is historical and immutable;
a new approved V2 release must be managed as a **separate versioned
contract**, never by quietly repinning or bypassing the existing checkout
reader. Read-only seven-gate checkout canary remains **6/7 HELD** against
the currently published site until new approved production publication
and release contract reconciliation.

## Real gateway & rollback evidence

An isolated **real FastAPI public gateway** process used
`EMPIRE_PUBLIC_SITE_OUT` pointing to this private union and bound only
to `127.0.0.1:8127`. All observed GETs returned expected HTTP 200
for the homepage, buyer checkout, commercial, about, insight,
pinned Earth artwork, font, brand, Next JS chunk, and public checkout
catalogue and tiers. The temporary preview process was stopped.

Root-owned site backup:
`/var/backups/empire-website/flagship_current_live_20261020_before_union.tar`.

Original 603 live files compared byte-for-byte to this archive using
`tar --diff`, **no differences**. Archive SHA256 verified:

`44ed2382af1700ff0644b7802bffb79b589d8dd2cda819f9941137ee852a503a`.

There is a known unavoidable mixed-generation compromise: 497
original-live-only paths remain in the candidate, including 448
previous JS files and eight legacy HTML pages. The verified candidate
preserves their old assets and has passed bounded browser/navigation
testing. The founder/website owner must explicitly accept this risk or
request an independently verified clean new build.

## Next controlled sequence after approval

1. Obtain the founder's **explicit approval to publish this exact
   632-file release**. The present user request "come on" is treated as a
   direction to complete engineering, not forged visual approval of
   exact publication bytes.
2. Re-verify the private proposal and all 632 SHA-256 digests immediately
   before release. Confirm *all 603 live bytes still match* the archived
   original, or pause for a new backup.
3. Run the website owner's reviewed atomic/reversible static-tree switch
   (separate release action; not supplied by the read-only checker).
   Keep prior HTML and bundle files recoverable. Do not run `rsync
   --delete` or silently change unrelated canonical Git source.
4. Confirm exact live HTML and pinned static SHA256, gateway HTTP
   status/CSP, desktop/mobile navigation, existing eight retained
   legacy pages, checkout route and genuine consent path.
5. Reconcile the **new** buyer page with independently reviewed V2
   release evidence and retain old checkout pin. No money movement or
   test buyer POST.
6. On any mismatch, restore the unchanged archived public static
   tree and confirm checkout/public gateway health.

Separate commercial work: obtain one genuine opting-in buyer and
accepted terms, then verify a real order, USDT settlement, fulfilment
and realised margin. A technically launched site is not a first sale.

## Exact no-deployment operator command

```bash
cd /srv/empire_os
sudo -n env PYTHONPATH=. .venv/bin/python -B \
  -m scripts.review_flagship_public_v2_signoff_20261020 --read-only
```

Output must show
`EXACT_V2_BUILD_PROVEN_FOUNDER_PUBLICATION_APPROVAL_REQUIRED`.
The optional flag `--write-private-review-packet` creates only the
original private non-authorizing record and refuses repeat writes.
**Neither flag deploys, activates checkout payment, changes legal terms,
sends email, creates orders, or authorises commercial claims.**

Keep Website & Growth as the owner, with revenue work in the
existing Revenue & Buyers chat. No fourth chat or new scheduler.
