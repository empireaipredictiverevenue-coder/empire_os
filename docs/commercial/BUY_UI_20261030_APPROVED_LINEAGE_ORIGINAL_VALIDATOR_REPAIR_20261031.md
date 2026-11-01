# Empire AI — Correct the original /buy HTML evidence check after the approved 756-file site release

**31 October 2026, 23:10 UTC | original BSC checkout status owner branch `feature/direct-bsc-independent-gates-20261020` | SOURCE ONLY, not installed.**

## Failure isolated

The existing Ops Control first-sale monitor's exact read-only `_legacy_buy_ui_manifest_verified()` calls **the existing** `scripts/deploy_direct_bsc_buyer_status_release.py::_published_checkout_verified()`.

That original verification only accepts the **13 October** `DIRECT_BSC_BUY_UI_STATIC_EXPORT_MANIFEST_20261013.json` HTML digest `1aebea003643743f725470e47762503d809db9f2f4e1a674f1b46443a6e9389f`. The site was later **legitimately released** to 747→753 and 753→756 files with the **approved live /buy digest `435cd7b1fed3490998ec2ca74cd0fc68f1a6ff0a324a10adba6428def4e92552`**. Every one of the old 36 immutable assets **still matches its Oct 13 hash**; the old HTML digest alone produces `LEGACY_BUY_UI_HTML_OR_ASSET_INTEGRITY_RELEASE_HOLD` and repeatedly appears in the 2-minute Ops snapshot.

This is a false *version provenance hold*, **not** evidence that a fake order, settlement or customer was created, that the payment gates are ready, or that the site has missing immutable assets.

## Exact existing-owner change

The original `_published_checkout_verified` accepts either:
1. **Its original Oct 13 exact HTML digest**, retaining the 36 mandatory immutable asset checks unchanged; or
2. **The later founder-reviewed /buy digest**, only after verifying both pinned original approved website release manifests as an unbroken 747→753→756 chain. The identical SHA-256-pinned original release manifests are retained as immutable evidence snapshots in the existing checkout docs tree under `docs/commercial/original_release_evidence/`, because the production `empire-ops-control.service` has `ProtectHome=yes` and cannot access `/home/ubuntu/empire_releases/` at runtime. Their exact bytes are validated against the original approval-stage receipts at staging and by the existing hash pins on every production read. No approvals or payloads have been edited. They independently agree that **`buy.html` was not replaced by either later scoped overlay** and that both original preimages equal the exact approved later /buy digest. The later pricing and scoped-CRM releases explicitly keep commercial binding/checkout and payments disabled.

There is **no new manifest, payment writer, ad hoc live-content repin, consent mutation, customer POST, website rebuild, or timer**. The verifier must continue to reject unapproved new /buy bytes, missing legacy assets, changed legacy asset bytes, mismatched manifests, changed authorization flags, extra buy.html overlay replacements, or mismatched intermediate inventories. It intentionally does **not** hash unrelated live site routes on every two-minute run; they belong to the original protected website release verifier, not the BSC /buy byte-integrity gate.

## Verified source and tests

- Current production original verifier SHA-256: `635d613a0b3b34e84d0f8e0738d7da16c53480167867071f6444da1a6051315d`.
- Source-owner candidate verifier SHA-256: `092fe85cff417adb0ad1a2b3f6e132d62a5d079c049a5305ead7099f4106d7b6` (record final hash at commit).
- Price-overlay manifest SHA: `cd02971236fd268ead2ea261ffbea68cecda96dd7337dcb6f56774ec5c0463f7`.
- Scoped-CRM manifest SHA: `46eb6eafa943fa7f58d6eeb606c264617a0084ca953fcd836ad16939e932d55b`.
- Read-only current-site verifier: **PASS** against published `/buy`, pinned later manifests and **all 36 original assets**; 756-file reconstructed release inventory was separately checked exactly against live as supporting evidence.
- **43 regression tests PASS**, including 8 new synthetic checks for accepted approved later page, changed page, changed legacy JS asset, unpinned/removed manifest, invalid intermediate lineage, falsely enabled binding terms, and false buy overlay.
- Nothing published or charged, customer data untouched. Existing live Ops timer continues to report the old hold until the original owner promotes the source.

## Owner deployment acceptance

This is checkout source owned by the original BSC buyer-status module. **Do not directly overwrite /srv/empire_os/scripts/deploy_direct_bsc_buyer_status_release.py as an uncommitted modification**: that script's existing `_reviewed()` checks the production Git tracked source against `HEAD`, so a direct file replacement would make future original protected release preflights fail. Merge/coordinate the reviewed commit through existing checkout/BSC release owner and production Git provenance first; do not cherry-pick over another agent's dirty production branch.

After guarded owner integration, run the original existing Ops timer, confirm two consecutive valid snapshot cycles with:
- `NO_CANONICAL_FIRST_PARTY_SALES_ENQUIRIES` or a genuinely different authenticated canonical count from root probe, **never re-used stale zeros**;
- `LEGACY_BUY_UI_PINNED_ASSETS_AND_HTML_VERIFIED` (actual already-approved /buy version) and HTTP GET route canary as before;
- `payment_execution=false`, `revenue_recognition=false`, and explicit buyer/payment action gates still independently held;
- no change to the legacy /buy HTML, its 36 pinned immutable assets, the current 756-file live website, CRM, buyer data, systemd or backend configuration.

**Business next gate:** correct original Commercial anchor and approved $199 nonbinding copy remain separate ASTRA/SEO releases. There is still no verified recorded first-party purchase or revenue.
