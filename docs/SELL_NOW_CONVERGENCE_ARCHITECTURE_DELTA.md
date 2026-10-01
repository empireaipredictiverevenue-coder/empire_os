# Sell Now / Opportunity Radar Convergence — Architecture Delta

Date: 2026-10-01
Status: CANDIDATE / OBSERVE-FIRST

## Purpose

Remove the structural hard-code that keeps all market opportunities permanently
factory-blocked even after explicit factor evidence has been bridged.

## Placement

Owner: Opportunity Radar -> Opportunity Factory -> Sell Now.
No new store, queue, service, or authority.

## Truth contract

Factory readiness may only use explicit fresh factor observations already
accepted by opportunity_revenue_evidence.bridge_factor_evidence.

Readiness requires:
- explicit offer;
- observed commercial demand;
- demand factor evidence;
- quality/enrichment/Omega qualification evidence;
- buyer-match/outreach/conversion distribution evidence;
- terms/payment/LTV economics evidence;
- fulfilment evidence;
- evidence refs for every accepted factor.

Scores, research priority, buyer capacity, search presence, social mentions,
policy, or pricing proxies never satisfy these requirements.

Partial evidence removes only blockers it directly satisfies.
Unknown remains unknown.

## Authority

Read-only planning state only. No send, allocation, payment, terms acceptance,
revenue recognition, DB mutation, deployment, or authority expansion.

## Verification

Focused Radar + factor bridge + Sell Now tests, compile, diff check, then
independent candidate verification.
