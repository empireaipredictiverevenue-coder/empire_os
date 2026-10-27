# EmpireOS Predictive Microsite Factory V4 — ranked research queue and outcome measurement

**Date:** 27 October 2026
**Worktree:** `/home/ubuntu/empire_worktrees/predictive_microsite_factory_slopmonster_20261026`
**Branch:** `agent/predictive-microsite-slopmonster-20261026`
**Authority:** OBSERVE and private staging only.

## What V4 adds
- `empire_os/microsite_calibration_bridge_v4.py` reconstructs forecast/actual reviews using the **original** `predictive_materializer.materialize_daily_actuals` and `predictive_calibration.review_forecast_calibration`. It requires pre-outcome forecast issue timestamps, frozen forecast SHA-256 and the original owner's independent source-custody verification callback. R², future projections or a claimed history alone cannot establish calibration. Zero authentic calibration bundles are available to this workstream; **calibrated count is 0**.
- `empire_os/microsite_ranked_production_queue_v4.py` produces a bounded, source-reconciled research queue. Each score is explicitly an **internal review-priority heuristic**, not predicted search demand, ranking, CTR, profit or revenue. Inputs are the original factory packets and validated commercial/GSC overlays. The original website owner remains responsible for any actual publication.
- `empire_os/microsite_page_outcomes_v4.py` creates per-page measurement registers with distinct unknown GSC impressions, clicks, consented sessions, enquiries, accepted events and cash settlements. It can independently read the **original** `weekly_two_page_YYYY-MM-DD.json` source only for its two pre-existing approved pages. The original GSC baseline never becomes mini-site traffic or attributed revenue.
- `empire_os/microsite_approved_page_measurement_v4.py` establishes a **future approved-page join contract** using exact candidate ID, HTML SHA, original site-owner deployment readback, GSC page row, actual server-side consented sessions, canonical CRM identity/buyer acceptance and settlement-to-original-accepted-event receipts. Original-owner callbacks must be connected separately; tests exercise fake callback implementations only. Arbitrary user-supplied approval booleans are not accepted. There is no active live microsite measurement feed.
- `scripts/review_ranked_microsite_outcomes_v4_20261027.py`: private read-only one-shot command, no new daemon, automatic publication or analytics collector, no external model calls, no DB writes.
- `tests/test_microsite_ranked_queue_outcomes_v4_20261027.py` includes fail-closed calibration lineage, no duplicate scores, exact source scoping, no fake page analytics, mock original-owner attribution chain and refusal of unverified publisher approvals.

## Real production-source run — 27 October 2026

Inputs: Original `weekly_keyword_intent_2026-10-26.json`, `weekly_two_page_2026-10-26.json`, source `lead_smart/coverage/latest.json`, two **illustrative** candidate research briefs, no forecast-registry credentials. Source snapshot contains 27,310 Lead Smart ZIP targeting-guidance rows; that source **does not establish verified buyers, payout or route**. Both candidates are held.

The ranking actually produced:

| Research rank | Example candidate | Internal research points | Verified exact GSC keyword? | Calibrated forecast? | Approved for publication? |
|---|---|---:|---|---|---|
| 1 | Chicago, US ZIP 60601 roofing | 30/100 | No | No | No |
| 2 | Manchester, UK heat pumps | 15/100 | No | No | No |

Points represent completeness of observed research evidence and source relationships, **not market sizes**. Manchester is simply a registry market anchor and a preview; its demand, installation capacity and ZIP/postcode-level facts are not proven.

The weekly **pre-existing** SEO page-source baseline is:
- Predictive Revenue: **1 impression and 0 clicks** within 16–22 October 2026.
- Roofing industry: **no page row in returned GSC data** (clicks and impressions remain **unknown**, not zero).
- Neither page is a newly generated microsite. These counts are not visitor sessions, consented enquiries or settled orders.
- New factory pages published **0**. Attributable enquiries, buyer acceptances, settlements and realised revenue for those candidates **unknown**.

Output directory (not public):
`/home/ubuntu/empire_releases/predictive_microsite_factory_slopmonster_v4_20261027_stage/`

Contains source-backed two-candidate manifests and previews, `commercial_research_review.json`, `gsc_evidence_bridge.json`, `ranked_research_queue.json`, `calibration_readiness.json` and `microsite_outcomes.json`.

## Repeat the read-only ranking

```bash
WT=/home/ubuntu/empire_worktrees/predictive_microsite_factory_slopmonster_20261026
DIR=/home/ubuntu/empire_releases/predictive_microsite_factory_slopmonster_v4_20261027_stage
cd "$WT"
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /srv/empire_os/.venv/bin/python -B \
  scripts/review_ranked_microsite_outcomes_v4_20261027.py \
  --candidate-source "$DIR/two_territory_research_input.json" \
  --commercial-source "$DIR/commercial_research_review.json" \
  --gsc-bridge "$DIR/gsc_evidence_bridge.json" \
  --output "$DIR"
```

## Remaining owner integrations
1. **Predictive owner:** issue independently auditable real forecast receipts with exact metro/postcode + keyword scopes, immutable issue date *before* outcome date and independent calibration/outcome custody. Existing Predictive Registry role is optional and wasn't read in this run; do not create dummy forecasts or reuse model R² as calibration.
2. **SEO/site owner:** verify local original content demand, real search opportunities, page utility and a reviewed immutable deployment/asset identity. Do not duplicate keyword-swapped or postcode doorway pages. Only the existing website owner may publish.
3. **Attribution/CRM owner:** supply the original read-only source adapter for lawful website analytics consent and immutable campaign/asset joins. First-party analytics currently has **simulation-only** status, not verified real sessions. Connect independent buyer acceptance and settled receipts by original event ID, not sitewide totals. A private mock end-to-end test is not a real event.
4. **Design owner:** render desktop/mobile screenshot checks on the newly updated V3 responsive hero with original SVG logo, then review contrast, brand, accessibility and performance. SlopMonster measures writing patterns; it does not prove visual quality or conversion improvement.
5. **Commercial owner:** get written specific buyer eligibility/ZIP coverage, payout terms and approved route before any conversion CTA is switched on.

**Decision:** private research queue and future measurement join are implemented; automatic approved mini-site publishing and realised revenue attribution are NOT live, and no production files/services/database changed.
