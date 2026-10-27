# EmpireOS — Existing PPC Switchboard and Hub Recovery
Verified 27 October 2026 | Owner: commercial acquisition integration | READ-ONLY INVENTORY

## Recovered, not rebuilt
The Founder was correct: original voice and pay-per-call routing infrastructure already exists.

| Existing asset | Exact source | What it actually does | 27 Oct status |
|---|---|---|---|
| Canonical guarded pay-per-call preview | empire_os/ppc_switchboard_adapter.py | Uses original buyer_allocation.plan_allocation; reports a candidate and evidence, but execute_pay_per_call_route ALWAYS raises | PARKED, no call execution |
| Voice switchboard authority | empire_os/voice_routing_policy.py | Triple-gated voice route flag and status exposed through voice_gateway_api.py health | PARKED / route OFF in observed process; no provider route proof |
| General AGI switchboard | empire_os/switchboard.py | Legacy agent/decision switchboard, default port 9100 | Separate from homeowner Ringba call routing; port 9100 not listening during 27 Oct inspection |
| Legacy PPC router and telephony | empire_os/ppc_router.py, empire_os/telephony_webhook.py | Earlier call-platform and webhook design | Legacy donor modules, do not restart |
| Central Empire Hub | empire_os/hub.py | FastAPI root with buyer onboarding, Voice Lab, marketplace and Founder dashboard routers | Source exists and contract tests pass, but old hub.py deployment NOT verified running |
| Buyer marketplace | empire_os/buyer_marketplace_webhooks.py | Buyer-side partner and webhook components | Source exists; not proof of a contracted accepting call buyer |
| Call manager | empire_os/call_manager.py | Governed B2B prospect/call-ready follow-up planning with Vonage | Not the inbound homeowner call switchboard; cannot turn it on as call routing |
| Original Lead Smart commercial | runtime/revenue/lead_smart/effective_pilot_state/latest.json | Original Ringba roofing pilot state | PREACTIVATION, traffic/routing/call CTA OFF |
| Existing CRO and unit economics | empire_os/conversion_intelligence.py, empire_os/call_unit_economics_review.py | Homeowner funnel review and approved finance-unit margin calculation | Pure measurement functions, no settled call-source cohort |

Tests: 35 original hub/switchboard tests passed on 27 Oct. The original adapter's activation is hard-stopped. Service unit files for legacy ppc_router, empire-hub and call-manager were not found as installed active systemd services; port 9100 was not listening. Existing local Founder/other API listeners do **not** attest that hub.py is running or the call switchboard is active.

## Critical architecture mismatch to reconcile
Original switchboard policy still labels its canonical transport Vonage and canonical database Supabase. EmpireOS now uses first-party EmpireDB PostgreSQL and the current Lead Smart pilot is tracked via Ringba; direct settlement verifier is USDT/BSC, but payments are NOT activated from voice routing.

Do not reactivate old Twilio/Vonage, Solana or Supabase paths, old hub payout routes or the general switchboard.py to fulfil the roofing pilot. An old health flag is insufficient to authorise an executable call. Original commercial owner must explicitly design the canonical Ringba/EmpireDB identity, buyer and call-outcome transport, with correct privacy/contract and founder controls.

## Actionable owner-to-owner handoff
1. **Commercial Buyer team** verifies written source, ZIP/service, hours, capacity, payable conditions and named human receiving buyer, not just a buyer reported route.
2. **Ringba owner** provides a bounded authorised test of actual target routing, independently verified human answer, disposition and deduplicated unique-call outcomes. Do not claim target-connected implies human answer.
3. **Voice/telephony owner** refactors original parked PPC adapter (not general AGI switchboard), removing retired transport/database assumptions. Keep actual route executor OFF pending original-owner verified test and explicit decision.
4. **Hub/Founder API owner** reuses original Hub or existing authenticated Founder API for preview and approved status. No new console, duplicate hub or anonymous financial endpoint.
5. **Website/CRO owner** issues consent-appropriate, first-party source to ZIP to call-choice lineage; original page changes require website owner.
6. **Finance/CRU owner** independently reconciles buyer accepted/billable outcomes to deposited cash and costs, then permits analytical learning. Provider payout is not recognized revenue.

## Completed small integration
The original Founder competitor-intelligence reader now exposes call_acquisition_intelligence.existing_switchboard_and_hubs, directly composed from original guarded voice status and existing source inventory. It cannot route, call, approve payments, create agents/timers/databases or publish pages. A misconfigured old ACTIVE flag is labelled LEGACY_FLAG_CONFLICT_NEEDS_OWNER_REVIEW, not promoted into a working route.

Code: empire_os/competitor_intelligence_feed.py
Tests: tests/test_existing_ppc_switchboard_hub_reuse.py

Remaining missing proofs: live Ringba target, buyer human answer, source-to-call identity, accepted payable call and independently settled cash. This is **existing capability recovery**, not a newly launched PPC switchboard.
