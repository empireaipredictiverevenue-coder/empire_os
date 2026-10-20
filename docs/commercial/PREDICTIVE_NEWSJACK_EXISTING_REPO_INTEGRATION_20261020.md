# Predictive Revenue — Existing Newsjack Repo + JEV Source-Owner Integration

**20 October 2026 | Predictive owner branch | read-only**
**No new news monitoring worker, crawler, external PR connector, scheduler, LLM, billing, marketing dispatcher or production mutation.**

## Existing ownership found and preserved

The repo we already researched is **https://github.com/elvisun/newsjack** (MIT); our 18 October owner document explicitly described it as a methodological reference, **not installed or vendored at that time**:

`/home/ubuntu/empire_worktrees/jev_newsjack_traffic_20261018/docs/architecture/JEV_NEWSJACK_ORGANIC_TRAFFIC_BRIDGE_20261018.md`

That branch/worktree already implements:

- `jev_newsjack_traffic.review_newsjack_jev_traffic`: owner news evidence freshness, sector/country scope, deduplication, independent-corroboration and trusted GSC gates, optionally JEV typed shadow review.
- `jev_newsjack_adapters`: existing last30days/Search Intelligence and GSC owner ingestion.
- `jev_newsjack_official_sources`: Federal Register/GOV.UK original official-source adapters.
- `jev_newsjack_traffic_briefs`: editorial research previews and existing owned destination checks.
- `jev_newsjack_marketing_handoff`: never-sent first-party draft preparation.
- `jev_newsjack_measurement_review`: owned traffic and attribution readiness.

Original owner source is held in its existing isolated worktree, not copied into Predictive. There are also later JEV owner worktrees; **the JEV owner must choose the reviewed canonical revision**, not the Predictive adapter. The server checked in this round does not provide `newsjack` on `PATH` or at `~/.newsjack/bin/newsjack`. Thus the upstream Newsjack full detector is **not proven installed or invoked** and JEV's own review explicitly has a `newsjack_installed_or_invoked` flag. Do not imply a live news feed or automatic story detection from the mere existence of source code.

### Upstream Newsjack feature map (research only)

Useful upstream functions include `newsjack-monitor-setup`, `newsjack-detector`, `news-search`, `story-origin-check`, `newsjack-triage`, `fact-check`, `angle-generator`, `coverage-tracker`, `newsworthiness-check`, and `ai-visibility-writing`.

Use the MIT repo with security review and a pinned release/revision **through the existing JEV owner**, not a direct `curl | bash` or unsolicited auto-updating installer on EmpireOS. The upstream detector may use optional third-party keys; **no new subscription or external message send is authorised**.

### Correct ownership model

1. **Research/Newsjack/JEV owners** — source collection, dated original news evidence, duplicates, origin checks, editorial standing, safety, SEO/GEO/PR angle suggestions, traffic/GSC attribution.
2. **Predictive Revenue** — append source revisions and time to market/world event hypotheses; exact market/canonical region crosswalk; economic scenario *proposals*, expected cash and profit under original explicit what-if assumptions, forecast registration and tracked outcomes.
3. **Finance/Commerce/Quant** — paid transactions, capacity/terms/costs, matched original forecast/outcome pairs, calibration, and actual revenue/profit.
4. **Commercial/Marketing owner** — human-approved promotion/owned site and outbound subject to current approvals. Tragedy, harm, unknown facts and premature news are not automatic sales hooks.

## Feature adapter built now

`empire_os/predictive_real_world_newsjack.py`

- `review_existing_jev_newsjack_handoff(owner_review,as_of)`: safely consumes **existing owner result** `empire.organic.newsjack_jev_review.v1`. Validates source schema, state counters, source fingerprints, publication time/freshness, original shadow-only JEV classification confidence, non-commercial authority and sector/country scope. Emits only anonymous, reviewed source fingerprints and research-stage cards.
- Crucially, **GB/US national-level market scope is NOT the canonical metro or actual service territory**; the adapter cannot invent a Little Rock or London linkage. No sourced conversion probability, verified physical event or incremental margin claim is made.
- The adapter accepts the original owner's `newsjack_installed_or_invoked` flag as **owner-reported only**; it does not treat that flag as proof of a trustworthy story, API integration, publisher independence, or permission to publish.
- `review_newsjack_event_research`: supplemental **source-owner metadata-only** event triage into existing Event Truth, Media Trend and Strategic Scenario categories. Does not collect news itself. Uses 72h *research* freshness, not an upstream pitch-permission substitute.
- `bind_newsjack_research_to_economic_twin`: an event-to-existing-Twin research link only if niche, exact geography, original pilot SHA and territory source revision match. It does not fabricate a conversion, CAC, price, capacity or weather shock multiplier.

`scripts/review_predictive_newsjack_readiness_20261020.py`

Reads source-owner reviews with `--read-only` and optionally an **explicitly supplied** approved JEV owner JSON artifact. Without one, the operator correctly reports no live JEV input; the currently nonexistent `runtime/real_world_news/latest.json` is an optional future source-owner convention, **not an activated news provider**.

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_newsjack_readiness_20261020 --read-only

# When the Newsjack/JEV owner has actually exported its reviewed JSON:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_newsjack_readiness_20261020 \
  --read-only --jev-owner-review /path/to/owner-reviewed-jev.json
```

The bridge was also smoke-tested directly against the **real** `jev_newsjack_traffic.review_newsjack_jev_traffic` implementation in its original worktree using a **fictional offline** UK solar story, without network, inference or publishing. The owner returned `RESEARCH_REVIEW`; the Predictive adapter returned `JEV_NEWSJACK_SOURCE_RESEARCH_REVIEWED` with one GB-sector **research only** card.

## Production and measurements

Real commercial measurement must later distinguish discovery time, first publication, original-source freshness, sector and region, verified audience interest, GSC observations, authorised content, website visits, attributable enquiries, conversions, gross profit, costs and forecast error. Until linked source and financial outcome records exist: actual incremental revenue, ROI, and prediction accuracy are **null**, not zero or invented.

**Status: additive feature tested offline; not deployed.** The upstream CLI is not installed on the server checked, no Newsjack monitor is running as a result of this work, no JEV/Newsjack owner code changed, and there was no publishing, emailing, prospect activation, payment, source feed spend or production model training.
