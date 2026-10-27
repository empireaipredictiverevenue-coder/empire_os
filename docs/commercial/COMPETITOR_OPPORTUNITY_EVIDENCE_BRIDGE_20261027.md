# EmpireOS — Competitor Change → Commercial Evidence Review Bridge

Date: 2026-10-27. Owner: original EmpireOS competitor intelligence / commercial research teams. Implementation OBSERVE and no new service.

## Purpose

Continue the Olly Rosewell competitor-monitoring research within the existing EmpireOS intelligence architecture. Public pricing, offer, feature and announcement changes are ONLY signals to investigate. They do not establish customer demand, a lead, a qualified buyer, acceptance terms, capacity, consent or revenue.

## Integrated code

- `empire_os/competitor_opportunity_evidence_bridge.py` reads the original first-party radar's canonical `runtime/competitive_intelligence/competitor_change_radar_latest.json`, original `runtime/buyer_acquisition/scout_latest.json` and original `runtime/opportunity_briefs/latest.json` as read-only sources. The bridge creates source-linked research cards only for fresh pending changes with valid baseline and change evidence. It requires exact canonical public-domain matches, not fuzzy names or personal email matching; extracts NO personal contact details.
- `empire_os/competitor_intelligence_feed.py` exposes `commercial_opportunity_research` under the EXISTING founder feed, including active pending-change count, freshness failures, known proof gaps and cross-reference summary; no new dashboard or API route.
- `scripts/refresh_opportunity_brief_chain.py` includes a read-only commercial research summary in the EXISTING fifteen-minute opportunity-brief report. It does NOT append competitor changes to the original local-contractor customer opportunity briefs and does NOT create Buyer Scout work items or mutate buyer/CRM/DB records.

## Commercial research facts recorded

1. Originating HTTPS source and persistent competitor review ID, exact category, observation timestamp, bounded observed excerpt and source reference.
2. Exact-domain matches, when any, to the existing Buyer Scout research candidate and existing opportunity briefs; these matches remain **RESEARCH PROFILE MATCH ONLY** and confer no commercial authority.
3. Explicit outstanding evidence: buyer acceptance, independently confirmed territory, criteria, caps/hours, written terms, qualified conversion and independently settled revenue.
4. Human review research question, but task_dispatched=false. Source age more than seven days is not actionable and is counted as stale.

## Current real verification

- 2026-10-27: canonical radar held **4 observed source baselines** and **0 pending change reviews**. Existing buyer and opportunity brief inputs were read successfully. **0 commercial research briefs** were created, **0 leads** admitted and **no verified revenue** attributed. This is honest non-conversion, not a system failure.
- The tests specifically prove a synthetic price change becomes one source-linked manual research card, preserving independent buyer terms unknown; a similar but different domain never joins; stale evidence is dropped; forged approval flags and missing baselines fail closed. No fabricated live competitor changes were injected into production.
- Tests: 76 scoped competitor/brief regression tests passing on the isolated branch before merge.
- No database changes, outbound, paid API, queue dispatch, new timer, CRM write, website/SEO edit, or Predictive Cloud forecast executed.

## Next responsible implementation slice

Within the existing commercial evidence owner, develop a verified buyer/ICP proof checklist and evidence collection for leads the buyer has actually agreed to accept. Specifically corroborate accepted geographies, qualified call/lead criteria, operating hours, caps, pricing/payment terms, consent and independent acceptance. A radar change can open review but must never bypass this evidence. Predictive Cloud model feedback must consume verified historical conversions/settlements only. User-generated complaints and supplier prices are subsequent licensed-source research, NOT authority for messaging or payments.

Status: `CANONICAL_FIRST_PARTY_RESEARCH_BRIDGE_IMPLEMENTED` / `REVIEW_ONLY` / `NO_COMMERCIAL_ADMISSION`.

## Verified buyer research proof coverage extension

The bridge now reads only the original Buyer Scout's already-published candidate rows and exposes the count of research candidates, source-reported canonical identity flags, written commercial-terms flags, and budget-evidence flags. These are **source-reported flags, not independent buyer acceptance**. It emits at most ten minimal-domain proof-gap rows without contact details, email addresses or outreach authority; exact duplicate source domains are considered ambiguous rather than matched.

On 27 October 2026 the current source had 5 Buyer Scout research candidates and 0 affirmative canonical-identity, written-terms or budget-verification flags. Radar had 4 successful source baselines and 0 pending public changes; thus 0 competitor-driven commercial review briefs, 0 new qualified leads and 0 independently verified settlements were attributed. No source was modified to make these values appear positive.
