# Lead Generation Results — 2026-09-21

## Canonical commercial funnel

Source: live canonical runtime/commercial_loop/latest.json.

- Real acquisition evidence: observed.
- Qualification v2: current cycle wrote 0 new qualifications, with 53 downstream Omega observations.
- Omega candidate/score observations: 53.
- Approved outreach-ready buyer candidates: 15.
- Currently authorized/sent outbound intents: 15.
- Currently sent/delivered/replied intents: 15.
- Total replies: 1.
- Commercial buyer replies: 0.
- Verified commercial terms: 0.
- Commercially activated buyers with verified capacity: 0.
- Non-raw fulfilment orders: 0.
- BSC payment requests: 0.
- Verified BSC USDT payment evidence: 0.
- Fulfilments: 0.
- Recognized revenue events: 0.
- Realized gross-profit events: 0.

Highest current blocker: **buyer_conversation**.

The one reply observed is not counted as a commercial buyer conversation.

## Current acquisition cycle truth

Latest acquisition snapshot used chicago_311 for CHI and produced 0 accepted
candidates in that cycle. This is a source-yield result, not a system failure.
The source remains real-data-only and the canonical store remains Supabase.

## Buyer-review materializer truth

Latest cycle:
- scanned: 60
- eligible for deferred probing: 12
- probed: 12
- proposed: 0
- review-ready: 0
- deferred enrichment: 12
- rejection reasons:
  - no decision-maker: 9
  - site unavailable: 2
  - no contact evidence: 1
- errors: 0

This points to decision-maker/contact recovery as the immediate enrichment
bottleneck for that batch.

## DFW Storm Revenue Strike expansion cohort

Six additional researched buyer-side prospects are recorded in
docs/DFW_STORM_REVENUE_STRIKE_COHORT_2026-09-21.md:

1. Storm Force Roofing + Construction
2. Good Contractors Roofing and Restoration
3. Lon Smith Roofing
4. Bold Roofing Company
5. Veteran Brothers Roofing & Restoration
6. CTD Restoration LLC

These six are **research_ready**, not outreach-ready. They are not included in
the canonical 15 approved/sent count until they pass dedupe, qualification,
decision-maker/contact evidence, Why-Now and buyer-review gates.

The original eight canonical DFW storm prospects remain separately deduped:
Max Exteriors; Mastercraft Roofing; PowerEdge Roofing & Home Repair; RISE
Roofing & Construction; SPC Construction & Roofing; 180 Roofing & Contracting;
LABA Roofing; Top Notch Roofing & Restoration.

## What this means

The system has proven acquisition -> scoring -> buyer review -> outbound
delivery. It has not yet proven buyer conversation -> terms -> payment ->
fulfilment -> recognized revenue.

Near-term optimization must therefore prioritize:
1. stronger decision-maker recovery;
2. tighter Why-Now personalization;
3. offer/message experimentation;
4. reply/conversation conversion;
5. fresh high-intent storm and search-triggered cohorts.

No forecast, score, send, payment request or research-ready prospect is treated
as revenue.

## Source-health incident resolved

The Control Fabric initially reported source_pipeline_degraded because the
source-health cron inherited lane code CHI from a Chicago 311 acquisition
snapshot and passed it directly to Overpass, whose source contract accepts
full metro names such as Chicago, IL.

The probe now selects a valid Overpass geography from overpass_metro_cursor
before considering source-specific lane codes. The bounded post-fix health
check used Pittsburgh, PA and observed 5 candidates, 5 quality-accepted, zero
errors, and end_to_end_healthy=true. The probe remained OBSERVE-only and wrote
no acquisition prospects.
