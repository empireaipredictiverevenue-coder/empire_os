# EmpireOS — Competitor Change Radar integration v1

**Date:** 26 October 2026. **Authority:** OBSERVE/read-only. This is an upgrade of the original first-party competitor intelligence and original YouTube-inspired research, not a new service, database, tenant, dashboard or acquisition team.

## Motivation and sources
- Olly Rosewell, [Rival Radar competitor monitor](https://www.youtube.com/watch?v=33dXIOzu8Qs): creator proposes tracking competitor pricing, product features, changelog and blog daily. Video description reviewed; captions unavailable, no verified performance/market demand claims.
- Related creator links: [Treg lead-data waterfall](https://www.youtube.com/watch?v=tlqW6vSw3b8), [multi-country pricing API](https://www.youtube.com/watch?v=C9fFpESF2Pk), [evidence-backed SaaS complaint mining](https://www.youtube.com/watch?v=aCi6BhrvjhM), [social marketing research](https://www.youtube.com/watch?v=FNBT-Pns4Ss).
- These are design leads, not evidence of our demand, lead count, buyer acceptance or financial results.

## Implemented now
1. `empire_os/competitor_change_radar.py`: bounded offline HTML fact extraction for pricing, offers, feature statements and public announcements; contact-line exclusion; normalized fingerprints; first-baseline/no-change/change comparison; source-attributed factual diffs; research priority, explicit human review status. No inference of buyer intent or money.
2. `scripts/review_competitor_change_radar.py`: human-invoked CLI. Uses original `competitor_call_channel_atlas` operator-source allowlist plus existing `competitor_call_source_watch` robots and bounded HTTPS HTML fetch functions, or accepts explicitly marked prior public-fetch receipts. Max two distinct operator domains per live invocation, rotating cursor with retained baselines. No extra service, API purchase, credential or scheduler. Results saved only where explicitly requested; no implicit production runtime changes.
3. `empire_os/competitor_intelligence_feed.py`: optional `commercial_change_radar` overlay in the original founder-feed read/refresh path. Reads only `runtime/competitive_intelligence/competitor_change_radar_latest.json`, validates OBSERVE/authority flags, and exposes a separate human-review queue. Does not insert into canonical company roster, Revenue GPS economics, TAM counts, buyer entities or outreach.
4. The original `competitor_call_source_watch.refresh` now passes its already-fetched, robots-permitted HTML into the radar interpreter. This shares original source requests, fingerprint monitoring and its two-domain rotation; errors leave the prior watcher running.
5. Focused tests in `tests/test_competitor_change_radar*.py` and `tests/test_competitor_radar_existing_watcher_bridge.py` protect that connection.

## Live observation proof (non-production candidate)
- Two real public baselines acquired and compared successfully: `https://www.elocal.com/affiliate-contact/` and `https://homeservicesleadgroup.com/affiliates`. Unchanged on second observation; three feature excerpts across two public pages, zero unverified leads or sales.
- Rotating scan then attempted `https://modernize.com/affiliates` and `https://investor.quinstreet.com/`; both robots unavailable/disallowed so no HTML was fetched. This was reported as source failures, not page changes or zero market demand.
- Candidate snapshots: `/home/ubuntu/empire_releases/competitor_change_radar_20261026/live_baseline_candidate.json`, `live_comparison_candidate.json`, `live_rotating_candidate1.json`, `live_rotating_candidate2.json`. The first read-only candidate was separately promoted to the canonical radar snapshot after checking authority flags; later comparison files remain candidate evidence.
- Tests on development branch: 42 targeted watcher/radar/feed tests and 39 pre-existing competitor intelligence tests passed before this final integration.

## Integration commands
```bash
cd /srv/empire_os
# One bounded operator-source review, using original atlas and first-party robots policy
PYTHONPATH=. .venv/bin/python -B scripts/review_competitor_change_radar.py \
  --live-original-atlas runtime/competitive_intelligence/call_acquisition_atlas_latest.json \
  --max-sources 2 \
  --output /home/ubuntu/empire_releases/competitor_change_radar_20261026/manual_candidate.json

# Next run: supply the previous candidate to retain per-source baselines and source cursor.
# Always inspect source failures and manual review queue before any further owner-approved integration.
```

## Boundaries and next exact work
- Existing first-party watcher-to-radar hook is implemented and tested in the original refresh function. It runs when the existing competitive intelligence refresh invokes that function; **no new timer is added**, and no independent ongoing refresh cadence was established. Observe actual operational invocations before claiming 24/7 coverage.
- Existing TAM and Buyer Acquisition owner must own later entity reconciliation, verified buybox/decision-maker evidence, permitted email verification waterfall and suppression; raw pricing changes are NOT qualified leads.
- Existing customer-voice owner can add licensed/permitted complaint and social observations, with source citations and deduplication; no private group scraping or rule evasion.
- Predictive Cloud owner should evaluate whether historical observed changes preceded genuine qualified conversations and paid outcomes, including false-positive counts and costs. Do not fabricate measurements.
- Cross-country repricing should be handled only after lawful source, currency, tax and geo evidence exists. Do not claim proxy-derived regional prices from generic UK responses.
- Preserve no paid traffic, no unsolicited sends, no money, no production payment activation.

**Acceptance:** bounded semantic interpretation integrated into the existing original source-watcher refresh, read-only canonical snapshot and feed overlay validated, live observations recorded, original DB/CRM/search owners preserved. Running timer cadence is not newly activated; CRM promotion and Predictive Cloud outcome feedback remain **NOT CONNECTED** until their owning systems validate them.
