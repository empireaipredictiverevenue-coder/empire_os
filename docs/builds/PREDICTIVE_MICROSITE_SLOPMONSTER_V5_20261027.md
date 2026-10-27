# EmpireOS Predictive Microsite Factory V5 — Verified Page Outcomes

**Date:** 27 October 2026
**Code location:** `agent/predictive-microsite-slopmonster-20261026`
**Authority:** Private OBSERVE/read-only. Existing SEO, website, predictive, buyer, CRM and finance owners remain canonical. No deployment.

## What was already present
V1–V3: SlopMonster MIT-pinned copy checker, original Empire AI branded responsive draft HTML, ZIP/postcode source review, exact Predictive Registry evidence, original buyer ZIP targeting observations.
V4: Original-custody calibration review, research-priority (not ROI) queue, genuine existing two-page GSC baseline and strict draft-only future approved-site attribution.
**V4 already existed locally at commit `bc5ef5d47` when V5 work started.** Do not restart or duplicate it.

## V5 tested changes
- `empire_os/microsite_verified_outcomes_v5.py` wraps existing V4 `review_deployed_microsite`. It accepts *authorised original owner reader callbacks* only, not arbitrary user-supplied attribution manifests.
- Every page must be independently confirmed by the original site owner at `https://empire-ai.co.uk/research/campaign_<24hex>` with the exact campaign ID, asset ID and immutable deployment readback. This is a **future integration contract**. No existing factory page currently meets it.
- Source readers for GSC page rows, first-party lawful consented sessions, CRM and verified settlement must match the **same candidate ID, deployed asset SHA-256, canonical campaign/asset ID and bounded reporting window** (max 31 days). Fields missing from the original owning service stay `null`, never inferred zero.
- CRM acceptance events are compared to distinct original accepted-event refs. Settled event rows must refer to a subset of those accepted IDs, have distinct settlement receipts, positive integer amounts and a total exactly matching the original settlement owner. Across pages, shared acceptance IDs, settlement IDs, campaign IDs and release URLs are rejected; no double-counted revenue.
- **Critical V4 deployment SHA repair:** a noindex factory preview cannot be the public indexable release's byte-identical artifact. The original owner may now supply immutable `source_preview_sha256` and separately verified `asset_sha256` with `deployed_asset_readback_verified=True`. The original V4 measurement joins all downstream metrics against the **deployed SHA**, while preserving the source-preview link. V5 requires this dual-SHA contract on owner-approved pages.
- `scripts/review_ranked_microsite_outcomes_v4_20261027.py` (existing one-shot) now additionally emits `approved_page_measurement_readiness_v5.json` for its original weekly page window. No new task or DB table.
- `tests/test_microsite_verified_outcomes_v5_20261027.py` covers missing release, whole-chain hypothetical proofs, source-window mismatch, cross-source asset drift, fake release, unknown vs observed zero, duplicate events, settlement overcount, multiple pages claiming one campaign, mutable draft/deployment digest and future indexable deployment receipt.

## Actual original-source run
Used the existing V4 staged two illustrative page proposals + original 2026-10-26 weekly SEO report.
Period: **2026-10-16 through 2026-10-22**.
Current state: **2 candidates / 0 owner-approved deployed factory pages / 0 factory pages with verified metrics / 0 observed settlements / no realised revenue claims**. The lack of authentic factory traffic/CRM/settlement feeds is an *unmeasured state*, not proof that actual business conversions or revenue were zero.
The read-only report:
`/home/ubuntu/empire_releases/predictive_microsite_factory_slopmonster_v4_20261027_stage/approved_page_measurement_readiness_v5.json`
The existing two-page SEO report remains a **separate reference baseline** and was not relabelled microsite traffic.

## Run the integrated reporting command
```bash
WT=/home/ubuntu/empire_worktrees/predictive_microsite_factory_slopmonster_20261026
DIR=/home/ubuntu/empire_releases/predictive_microsite_factory_slopmonster_v4_20261027_stage
cd "$WT"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 scripts/review_ranked_microsite_outcomes_v4_20261027.py \
 --candidate-source "$DIR/two_territory_research_input.json" \
 --commercial-source "$DIR/commercial_research_review.json" \
 --gsc-bridge "$DIR/gsc_evidence_bridge.json" \
 --output "$DIR"
```
Produces the unchanged V4 research, calibration and attribution outputs plus the new V5 approved-page readiness report. No external API requests, model calls, database writes or publishing.

## Remaining owner handoff — required before reporting real outcomes
1. **Website owner** must explicitly approve a useful unique page, publish via the existing source-controlled site release process and provide immutable mapping from draft SHA to live deployment SHA, with a real canonical campaign and asset ID. A founder permission in chat alone is not an original deployment readback.
2. **SEO/GSC owner** must provide a read-only page+weekly-window resolver for the newly approved URLs; the existing original two-page report is not a newly deployed microsite source.
3. **Privacy/attribution owner** must provide lawful actual server-side consented-session, campaign ID and asset ID evidence. Browser-only self-reported claims cannot mint verified sessions.
4. **CRM owner** must expose read-only canonical enquiry/qualification/buyer acceptance counts plus accepted event IDs at the same page/week scope; no PII or fabricated lead totals.
5. **Settlement owner** must expose accepted-event-to-cash settled source receipts with transaction references, same week and currency. Realised revenue only from the original settlement owner's independently verified records.
6. **Predictive Cloud owner** must issue genuine, retrospectively measured pre-outcome forecasts and separate source-owner verification receipts for historical calibrations; none of the current factory examples has three independently custodied calibration pairs. A model's R-squared isn't an out-of-sample reliability result.
7. **Marketing + website design owners** should review V3 branded desktop/mobile screenshots and real user value before any URL or domain exists. SlopMonster 5/5 only checks cliché/style patterns, not sales conversion or usability.

No automatic domain creation, mass postcode pages, self-publishing, real-money routing, second DB, duplicate agent, new scheduler, new collector, SEO owner-file edits or backend deployment.
