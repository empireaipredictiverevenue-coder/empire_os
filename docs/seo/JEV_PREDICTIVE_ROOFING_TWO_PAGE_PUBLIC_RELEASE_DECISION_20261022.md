# Empire AI — exact two-page public SEO release decision

**22 October 2026. PUBLIC WEBSITE NOT YET CHANGED. Approval for the private Founder Console does not authorise public website publication.**

## Scope and evidence

The Jev-led Search Department examined 30 previously observed 404 URLs using real pinned model assessments. The original 7–19 October GSC page-only observations comprised 44 impressions and zero clicks across those legacy URLs. They are NOT the baseline for two existing site pages, a ranking prediction, a model accuracy claim, or any qualified enquiry.

The only candidate public pages are:

- `https://empire-ai.co.uk/predictive-revenue`: dated forecast-versus-actual reconciliation guide, clearer B2B title/description, and one-line 320px header wrapping fix.
- `https://empire-ai.co.uk/industries/roofing`: a new buyer-leg, call-acceptance and settlement-evidence explanation.

No restoration or redirect of any legacy 404 URL; no changes to consumer `/roofing`, homeowner guide noindex, payment, API, price, digital avatar, animated homepage, terms, privacy, editorial paid traffic, browser agents or outreach.

**Website content source commits:** `4fb0eaa6f`, `79dd421bb`. Static export contains 154 files but MUST NOT replace the 645-file mixed-generation live website wholesale.

## Verified private candidate

- Full guarded overlay root: `/home/ubuntu/empire_releases/seo_predictive_roofing_public_pilot_20261022/overlay-79dd421bb/out`.
- Overlay SHA-256 receipt `2f33238d06878150d908663b1ec3415a415db62ad7266254f2438a0899edc62a`.
- 653 files total = preserved 645 live static files + 8 new content-hashed Next assets; only 4 existing bytes replaced (`predictive-revenue.html`, `predictive-revenue.txt`, `industries/roofing.html`, `industries/roofing.txt`).
- New assets have no filename collisions. All 645 original paths and 641 original non-target files are preserved, with pinned hashes. The initial unreleased candidate failed 320px horizontal overflow; its failure receipt is preserved. The corrected release passes browser smoke at 320, 390, 820 and 1440px: 8/8 target route checks; 2/2 interactive commercial navigation; zero page errors, missing static assets, POSTs or external requests.
- Browser evidence SHA `8565d384217bfa4674195e4990db9a0b4f75e8f0b1589b449513f49bbeba919f` with 390px screenshots at `overlay-79dd421bb/BROWSER_predictive_390.png` and `BROWSER_roofing_390.png`.
- Screenshots visually inspected by assistant: both first viewport designs and mobile header layout remain legible. The buyer catalogue shows a deliberate `temporarily unavailable` state in private preview because model/browser runtime deliberately blocks all backend calls. **This is not evidence that real checkout or a real lead submission worked.** Founder visual sign-off remains a separate required approval.

## Fresh complete live rollback is NOW DONE

On **22 October 2026 at 12:15:06 UTC**, the entire original 645-file public static tree was snapshotted as:

`/var/backups/empire-website/seo-two-page-prepublish-20261022T121506Z.tar`

- SHA-256 `ce96f4736d24d4d3ce5158b8cde745d5c144b677f25a20abf9956dc39594fa50`.
- Complete root-owned archive, root-private mode 0600; every file read back from archive and SHA-verified against exact 645-file public baseline, and production rescanned unchanged afterward.
- Snapshot custody manifest `/var/backups/empire-website/seo-two-page-prepublish-20261022T121506Z.receipt.json` SHA-256 `812a26346fc63186da8b0fcf7b967fac8499beaffc91717a401a71ffff7775e8`.
- Not itself authority to publish. If production files change before approval, the next publisher must fail closed and prepare a newer, verified snapshot and candidate.

## Guarded publisher prepared but NOT executed

Versioned `scripts/release_predictive_roofing_two_page_20261022.py` accepts read-only `--preflight`; publication requires a separate explicit, exact-page founder authorisation and the distinct `--apply-founder-approved-predictive-roofing-two-pages` flag. The latter must NOT run from this preparation-only instruction.

Operator preflight from the canonical code (run as root to independently verify root-owned backup):

```bash
cd /srv/empire_os
PYTHONPATH=. sudo -n /srv/empire_os/.venv/bin/python -B \
  -m scripts.release_predictive_roofing_two_page_20261022 --preflight
```

The publisher verifies both pinned release receipts, the separate root backup, the exact current 645-file hashes, and the four old/new payload hashes. It employs an exclusive per-release lock, writes only new hashed assets and four page files, and restores the original four files/deletes new assets if its transaction fails. It refuses source modifications, asset collisions, changed public baselines, missing backup or another deployment attempt. This is a bounded rollback implementation, NOT blanket production fault tolerance or verification of a successful real commercial form submission. All unit tests run only in isolated temporary directories; synthetic fail-on-fourth-file and post-deploy errors were rolled back.

## Remaining final gates

1. The founder reviews the actual candidate visual presentation, including its two private screenshots and existing navigation/conversion paths, and **explicitly approves this exact two-page public release**.
2. The owner re-runs pinned preflight; if any of the 645 live files changed in the meantime, stop and re-snapshot/re-stage, without overriding other website agents.
3. Execute only with the distinct owner-approved release flag after approval; verify public HTTPS for both pages, original page self-canonicals, linked commercial intake availability, public `/commercial`, homepage, consumer roofing and historic 404 URL holdings. Preserve noindex on the separately held guides.
4. Obtain fresh GSC *page-only* data after a suitable reporting lag and compare matched windows. For 7–19 October, the 32 returned page rows include **neither** target page; that is missing returned observation, not zero indexing or proven zero traffic. Measure actual consented enquiries, buyer qualification, accepted order, fulfilled transaction and economic settlement separately. Do not claim realised revenue from a search impression, call attempt or predicted outcome.

**Owner handoff state:** root rollback backed up; candidate browser verified; exact publisher preflight ready; **live two-page publication HELD pending specific founder authorisation**.
