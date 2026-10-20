# Meta social marketplace intelligence — offline research candidate

Date: 20 October 2026
Branch: `feature/meta-social-intel-research-20261020`
Authority: OBSERVE ONLY. No deployment or merge, no scraping, API credentials, database mutations, contact, social publication or spend.

## Evidence
Greg Isenberg's 19 October 2026 video *Meta Muse Will Create 1,000 Millionaires* describes four stages: research niches/localities; organise trustworthy source lists; own audiences through communities/pages; build dedicated matching software. EmpireOS's first-party YouTube link research CLI verified title/creator via public oEmbed but did not obtain a transcript or watch frames. The creator's published outline is available at:
https://startup.whatfinger.com/2026/10/19/meta-muse-will-create-1000-millionaires/

## Existing EmpireOS fit
- `empire_os/community_intent.py`: evidence-led Reddit/LinkedIn observations; retain existing owner.
- `empire_os/commercial_social_intent.py`: company affiliation evidence for Reddit/LinkedIn, not a buyer commitment. Retain existing owner.
- `empire_os/icp_intent_source_atlas.py`: source atlas; currently only Reddit public RSS is automatically collectible.
- Buyer Scout / CRM / Predictive Revenue / Data Brokerage: later downstream consumers subject to source rights, commercial validation and owner-approved typed interface. This branch connects to none of them.

## Research candidate built here
`empire_os/meta_social_opportunity_research.py` ingests bounded, pre-authorised **structured** observations offline, restricts accepted origins to Meta URLs, holds personal contact fields and raw text, staleness, unknown rights and duplicates, then creates niche+US ZIP hypotheses only where aggregated demand AND business supply evidence co-exist. No authenticated demand, purchases, revenue or qualified leads are inferred.

Read-only review entry point:
`PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_meta_social_opportunities_readonly --observations-file <reviewed_structured_packet.json>`

Tests:
`PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q tests/test_meta_social_opportunity_research.py`

Packet root: `{"schema_version":"empire.meta_social_opportunity_review.v1","observations":[...]}`.
Observation fields: `platform` (facebook_group | facebook_marketplace | instagram), `kind` (aggregate_demand | business_supply | market_pricing), `source_url` (https, on appropriate Meta host), `subject_type` (aggregated | business), `niche`, `us_zip`, `observed_at` (timezone-aware ISO), `rights_status` (verified_permitted), `access_method` (official_approved_api | authorised_manual_review | consented_partner). Do NOT put names, handles, phone numbers or raw conversation text into observations.

## Production gates
1. Confirm supported Meta product endpoints and actual permissions for approved business Pages / professional Instagram. No Facebook Groups API: Meta removed it in April 2024.
2. Document lawful source/usage rights, privacy and retention. Public visibility is not itself permission for automated extraction or resale.
3. Independently establish commercial buyers, provider capacity, target ZIPs, payable appointment rules and revenue share. The findings here are hypotheses only.
4. Require source-quality checks, anti-duplicate checks, access controls, suppression/consent and explicit typed ownership-boundary signoff before any handoff to CRM or Brokerage.
5. Require separate founder approval for outbound, site changes, Meta collection, spending or production activation.

## Commercial recommendation
Prioritise US HVAC and roofing B2B provider network discovery paired with opt-in demand intake via owned channels. Use authorised Instagram business discovery first, Facebook group manual topic review only where permitted, and build owned niche community/page audiences without copying member databases. Do not automate DMs, browse private communities with robots, or harvest individual consumer posts into tradable leads.

## Known limitations
- No Meta API credentials, accounts or permissions were checked or changed by this candidate.
- No actual Facebook or Instagram observations were collected.
- Source-rights claims in offline input are declarations, not independent legal verification. Production ingestion must authenticate and audit them.
- No integration to CORTEX, CRM, brokerage or revenue measurement has been implemented.
