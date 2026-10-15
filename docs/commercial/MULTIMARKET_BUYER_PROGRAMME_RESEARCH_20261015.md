# Empire AI — international buyer and publisher programme research

15 October 2026 | Sovereign, OBSERVE, read-only | Research candidates only

**Goal:** Find a real, funded buyer or an approved affiliate programme that accepts our actual consented first-party UK, US, Canadian or Australian traffic. Public marketing pages do NOT establish a contract, exact payout, installer capacity, postcode/ZIP buy box or permission to send any consumer information.

## Public first-party programme shortlist

| Market | Company and role | Official programme evidence | Gate |
| --- | --- | --- | --- |
| USA | Modernize — home-improvement affiliate/lead recipient: solar, roofing, HVAC | https://modernize.com/affiliates | Obtain approval and written source/vertical/ZIP billable-event terms; existing research only, no duplicate introduction |
| USA | Angi — affiliate channels for links, calls and lead auction APIs | https://www.angi.com/landing/affiliatepartners | Confirm publisher approval, exact market and allowed first-party SEO source; auction feature is not a granted API contract |
| USA | Home Services Lead Group — home-service PPL/PPC affiliate network | https://homeservicesleadgroup.com/affiliates | Confirm programme identity, active campaign, publisher rules, accepting ZIPs, payout and funded buyer |
| UK | Leads 2 Trade — home-improvement lead affiliate, solar supported | https://leads2trade.co.uk/about/affiliates/ | Confirm whether new suppliers accepted and identify overlap with existing LeadsDoWork exclusivity; no customer data transfer |
| Australia | Your Solar Quotes — tracked solar publisher referrals | https://yoursolarquotes.com.au/solar-affiliate-program/ | Validate Australian traffic acceptance, payout event and terms |
| Australia | Australian Solar Quotes — solar quote referral/profit-share inquiry | https://www.australiansolarquotes.com.au/about-us/referral-partners/ | Programme enquiry only; terms, acceptance and payable event unknown |
| Canada | LiveLeads — lead-auction marketplace with supplier registration | https://www.liveleads.ca/ | Verify actual category/province buyer bids, supplier approval, data protection and funded proceeds |
| Canada | CentFix — home-services partner programme, percentage of collected revenue publicly advertised | https://centfix.ca/affiliates | Confirm applicable service area, credited sale, hold/cancellation rules and written contract |
| Canada | Xolar — installer direct referral reward after completed solar installation | https://xolar.ca/referral-program/ | **Not** proof of B2B paid-per-lead buying; check whether publisher/company participation accepted and installation evidence |

## Existing live commercial relationships — do NOT prospect afresh

- SolarBriton: 15 October human reply interested in discussing a UK no-upfront tracked referral pilot; currently editorial-only. It is a prospective **supply partner**, not a verified downstream buyer. First prove a UK solar buyer with MCS, postcode coverage and terms.
- LeadsDoWork: 13 October programme application accepted; private portal contains category/rate details not yet approved. Existing 14 October founder clarification must not be duplicated; verify exclusivity and consent before any UK activation.
- AceLeads: application acknowledged 13 October, pending human buying brief. Do not relabel as an unused prospect.
- RVNU: already contacted in US; await verified reply before follow-up.

## Discover -> verify -> commercial gate

The existing `empire_os/buyer_public_research_seed.py` (used by the existing buyer acquisition scout) now rotates 2 publisher-targeted searches across USA, UK, Australia and Canada **without increasing the previous 2-query budget**. Its reviewed first-party programme URLs enter existing `research_seed_records`, company-site probing, canonical identity and founder qualification. An existing quota of at most four publisher programme review slots rotates fairly between regions; no new timer, integration or buyer database is created.

Keep disjoint states: PUBLIC_PROGRAM_CANDIDATE -> FIRST_PARTY_PAGE_OBSERVED -> CONTACT_HISTORY_AND_HOLDS_REVIEWED -> HUMAN_BUYING_BRIEF -> FOUNDER_APPROVED_TERMS -> VERIFIED_BUYBOX_SOURCE_AND_LOCATION -> PERMITTED_TEST -> ACCEPTED_SETTLED_REVENUE.

Every geography requires its own consent/privacy and marketing compliance assessment, authorised traffic source, accepted cities/ZIPs/postcodes/provinces, funnel and tracked event, chargeback/dispute windows, contractual price and settlement conditions. A posted illustrative payout or a paying **installer member** does not establish that the network will buy a publisher's lead. A direct-installation reward (Xolar) is categorically distinct from a CPL or PPC contract. Zero new spend; no email, calls, signup, portal login, paid traffic, buyer activation or funds movement in this research task.

## Known search-fabric limitation

The production seed snapshot at 16:04 UTC on 15 October reported 12 query attempts but **zero fresh search domains** and search-provider health unverified. That's not an empty buyer market; static seed URLs and first-party site evidence remain research-only fallbacks. Existing canonical network discovery had 213 observed domains and 22 recent first-party corroborated domains (16:26 UTC), with no verified buyer terms. The system must not turn missing search results or aggregate buyer counts into invented buying capacity. Investigate the existing search-fabric provider separately before reporting autonomous fresh discovery success.
