# Original Buyer Scout — targeted publisher sweep (27 October 2026)

## Purpose

Increase the quality of the **existing**, scheduled 30-minute EmpireOS Buyer Acquisition Scout's publisher/marketplace discovery sources. Reuse the original `empire_os.buyer_public_research_seed` source list, original contact-history gate and original qualification loop. No new scraper/agent/timer/DB, no automatic contact, no claim of real buyer coverage or revenue.

## Current original source evidence at 15:02–15:04 UTC

- Existing original Scout timer `empire-buyer-acquisition-scout.timer` is active.
- Existing founder candidate queue contains **151 candidates**, most awaiting direct-site review; it is a research queue, not 151 payable buyers.
- Existing qualification loop reports no independently verified accepting buyer capacity/accepted pilot in the inspected source.
- Contact-history checks across both linked Gmail accounts showed prior outreach to **DOPPCALL, Marketcall, Aragon Advertising, Omni Call Network, Elite-Calls** (all **not** new). DOPPCALL also appears as `ALREADY_CONTACTED` in the original queue, and `webuycalls.com` as `DELIVERY_HOLD`. Callmart is already submitted and awaiting approval; never duplicate its buyer signup or publisher application.
- The legacy discovery-recovery report can mix runtime file names and technical infrastructure domains with commercial companies. **Do not** use its raw discovery count as independently verified buyer count. The original canonical research/verification/contact-history gates stay authoritative.

## Newly added first-party publisher research seeds

| Domain and evidence | Public offer scope | Original qualification state |
|---|---|---|
| [tryleadledger.com/affiliates](https://tryleadledger.com/affiliates) | Residential trade inbound calls, fixed offer-specific rates, first-party organic allowed; **published live offers currently pest control FL and plumbing OR/WA, not proved live roofing**. Requires W-9 before first payment; UK sole-trader eligibility unknown. | RESEARCH ONLY; confirm eligible payer and UK tax route before application |
| [luxenworks.com](https://luxenworks.com/) | Public publisher form says home-service calls including roofing, HVAC, water damage; per-call qualifications and traffic review. | RESEARCH ONLY; validate counterparty identity, current geo and terms |
| [dependablecalls.com/publishers](https://dependablecalls.com/publishers) | Public publisher exchange lists roofing/HVAC/plumbing, says net-30 and per-call reconciled statement; no partner-specific price guaranteed. | RESEARCH ONLY; confirm scope, geo, signed terms, compliance and cash route |
| [oncall-24.com/join-our-network/](https://oncall-24.com/join-our-network/) | Public affiliate interest form for home-services phone-call supply; fixed/dynamic/rev-share possible. | RESEARCH ONLY; verify buyer's active programme and attribution |
| [join.leadswitchmedia.com/publisher](https://join.leadswitchmedia.com/publisher) | Insurance publisher onboarding, not a roofing buyer. | FUTURE INSURANCE RESEARCH ONLY; no live insurance calls or consumer traffic |

Each seed enters the **original** `_MULTIMARKET_REVIEW_SEEDS` list with `identity_verified=false`, `buyer_capacity_verified=false`, `commercial_terms_verified=false`, `buyer_price_verified=false`, `outreach_authorized=false`. Target market labels represent the U.S. demand market, **not** the publisher's registered jurisdiction. Search call budget and existing half-hour timer remain unchanged.

## Revenue-first selection criteria

1. **First-party counterparty** and correct role: a programme buying publisher-originated homeowner calls (not selling Empire AI calls, not software-only).
2. **One active buy-box**: ZIP/states, service, homeowner intent, accepted traffic source, contact privacy disclosures, relevant hours and caps.
3. **Commercial agreement**: specific payable event or duration, buyer credits/duplicate rules, payout basis, settlement method and UK sole-trader contracting eligibility.
4. **Evidence-proven pilot**: first-party consented caller → Ringba/network call ID → independent qualified disposition → actual payment, then a canonical pre-outcome forecast and later validated shadow learning.

An offer webpage, claimed payout, application submission, test call, apparent destination connection, or traffic projection is **not** independently verified commercial capacity or revenue.

## Tests and acceptance

`tests/test_buyer_targeted_sweep_seeds_20261027.py` validates all five source-domain IDs, intact original search budget and unchanged consent/revenue/outbound proof requirements, plus domain de-duplication. Broader original Buyer Scout tests must remain green before production integration. Any other agent's concurrent uncommitted work in `empire_os/buyer_public_research_seed.py` must be preserved exactly.

**Status:** new researched sources queued to original Scout code path for first-party verification; no outreach, buyer acceptance or revenue asserted.
