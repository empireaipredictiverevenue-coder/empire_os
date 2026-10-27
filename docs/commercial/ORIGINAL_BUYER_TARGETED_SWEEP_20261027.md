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


## Follow-on seller-fit review — 27 October, 15:28 UTC

The existing original Scout runtime completed an on-demand OBSERVE pass after commit `20d3db171`; all five new publisher seeds appeared **once** in the original seed snapshot with `outreach_authorized=false`, `buyer_capacity_verified=false`. The bounded later Scout returned 3 candidates, 0 independent purchase-budget records, 0 direct buyer confirmations and 0 earned revenue. No new timer or API key.

**Dependable Call Exchange (`dependablecalls.com`)**: official publisher page markets roofing/first-party consented inbound calls and a net-30 reconciled per-call settlement. The public publisher onboarding form has an optional US phone field, BUT uses Turnstile verification and requires user consent/privacy attestations. **Do not automate around the challenge or claim a completed application.** Its posted website Terms of Service (`https://dependablecalls.com/legal/terms`) explicitly say the legal terms remain **pending final legal review**. This prevents treating the public terms as a final vetted publisher contract. Confirm separate signed publisher contract, current roofing buyer ZIPs, UK sole trader acceptance and exact call/payout conditions before applications or routing. Public business and payout claims are unverified supplier representations.

**Luxen Works (`luxenworks.com`)**: official seller page lists roofing inspection marked **Google Ads** traffic, while Empire AI's proposed first supply is **organic SEO**. That is an exact programme-source mismatch until Luxen confirms an organic roofing programme in writing. Public seller conditions include 60/90-second duration buffers, a **$500 minimum payment threshold**, and pay-after-buyer-pays qualification. Broad advertising of 50+ buyers or maximum headline payout is not a contract or evidence of funded supply. Seller form requests five compliance attestations: do not tick on behalf of the founder without review; no seller form submitted.

**Real human commercial fit questions are prepared in the already-connected original founder Gmail account `phil@empire-ai.co.uk`; both are unsent drafts** (no mass outreach or repeat contact):
- Dependable: `https://mail.google.com/mail/u/?authuser=phil%40empire-ai.co.uk#all/1a17df8e04ce78e2`. Verified direct email via the provider's published first-party contact: `david@dependablecalls.com`. Exact asked: UK sole trader, one organic roofing buyer corridor, source consent, settlement rules and final signed contract.
- Luxen: `https://mail.google.com/mail/u/?authuser=phil%40empire-ai.co.uk#all/1a17df9292264ee8`. Verified direct email via its published first-party contact: `dfoster@luxenworks.com`. Exact asked: whether owned organic roofing is accepted vs Google Ads-only, 1 current ZIP corridor, buffer, UK sole-trader eligibility, written IO and $500/after-buyer-paid settlement.
- Neither email or business application has been sent/submitted. Drafts must not count as attempted outreach.

**Additional pre-existing original shortlist choices**: `homevantaleadgroup.com` (official affiliate page says SEO and roofing category are considered; no verified current accepting campaign), and `leadspedio.com` (publisher/onboarding public pages mention home services; no specific accepting roofing buy-box established). Treat as first-party website **research only**; previous correspondence must be independently rechecked before any follow-up or application.

**Original owner next action:** obtain **one real roofing buy-box from an authenticated counterparty** with accepted owned SEO, specific eligible ZIPs, payout duration/event, buyer hours/caps, disputes/credits, UK contract eligibility and actual settlement. Preserve user and buyer source/privacy evidence. Only then use the original authenticated financial outcome and Predictive Cloud shadow learning path. No new commercial dashboard, agent, timer, send authority or fabricated sales.
