# EmpireOS buyer discovery A/B research review — 10 October 2026

## Baseline versus independently tested publisher-first discovery

EmpireOS canonical registry prior to this test: **195 company records** with **57 Gmail threads**, and buyer-scouter candidate queue **155 candidates**; the 16-target founder qualification file is an evidence-recovery shortlist, not confirmed active customers. Many records are contractors, generic businesses, directories or other ICPs, so the 195 figure is not 195 verified call buyers.

**External publisher-first method:** Search for roofing/home-services *publisher application*, SEO/owned organic traffic approval, call qualification and tracking, then inspect the company's official affiliate/offer pages. Current manually reviewed cohort: 4 first-party publisher channels **not in the canonical registry** when checked, and no corresponding Gmail outreach found.

| Company | Official publisher evidence | Offer relevance | Contact path | Commercial truth |
|---|---|---|---|---|
| eLocal (elocal.com) | https://www.elocal.com/affiliate-contact/ and https://www.elocal.com/price-list/affiliate-pay-per-call-rev-share-category-coverage | Publisher onboarding; SEO/SEM allowed in published guidance; Roofers call category and ZIP-coverage information | First-party affiliate questionnaire (not submitted) | First-party advertised call bid ranges are NOT a publisher commitment, eligible ZIP allocation or approved EmpireAI rate |
| Polyares (polyares.com) | https://www.polyares.com/pay-per-call-affiliate-program and https://www.polyares.com/pay-per-lead-affiliate-program | Home-services roofing call and form inventory, written rate on approval, tracked numbers or ping/post discussed | First-party publisher application (not submitted) | Buyer capacity, payout and terms require individual written approval |
| Home Vanta (homevantaleadgroup.com) | https://homevantaleadgroup.com/for-affiliates | Home-services roofing and SEO/content publishers, explicit traffic-source review and call/lead formats | First-party affiliate inquiry; email contact preferred, but no message sent | Relationship to other similarly named home-services companies is unverified; no buy-box received |
| Global Wiz (joinglobalwiz.com) | https://joinglobalwiz.com/ and https://joinglobalwiz.com/affiliates | Roofing/home-services publisher programme, explicitly lists SEO and owned-and-operated content | First-party affiliate application (not submitted) | Campaign availability and source approval are conditional |

**Known-match controls:** LeadSmart (leadsmartinc.com), PX (px.com), Callflowmarket (callflowmarket.com) and Position Calls (positioncalls.com) were already represented in EmpireOS. ServiceCallPros was independently returned by public search but had an existing outreach thread, so it must not be treated as a fresh contact. General blog/directory listings about buying roofing leads are **research sources**, not necessarily buyers or publisher destinations.

## What the search comparison actually proves

- **Manual selected sample:** four relevant *company-published* publisher programme entry points absent from the earlier registry. Not a random controlled sample; **not** a statistical precision comparison or verified current campaigns.
- **Why this worked:** Intent-constrained queries sought publisher acceptance, exact home-services verticals, SEO/owned-site supply, tracking/qualification rules and contact/application paths instead of only a broad company name.
- **What remains unproved:** Live coverage in Empire AI's target ZIPs, actual phone or form bid capacity, contact person's authority, onboarding acceptance, signed agreement, payout, consent and real billable events. No buyer outreach, portal signup or traffic activation is authorized by this research.

## What EmpireOS learned — deployed in its existing scout source fabric

1. Two *publisher-first* queries rotate on the **existing 30-minute scout**, preserving the total search-query budget and baseline rotating local SMB research. No additional scheduler or provider.
2. Four observed official publisher URLs are retained as **research-only first-party seeds**, all initialized with buyer capacity/terms/outbound approval set to false.
3. Seed outputs include per-method query count and a registry-compared **domain novelty** report. Novel domains are explicitly not treated as verified buyers or actual revenue; missing baselines return UNKNOWN, not fabricated novelty.
4. Future learning should use actual verified buyer replies, accepted publisher accounts and real payable calls by domain/source strategy. Operational domain novelty is a weak research signal, not a trained conversion predictor. Avoid repeatedly recommending contacted or suppressed companies; preserve existing Gmail/suppression checks.

**Priority:** Keep LeadBank/Validated/Connexis's warm conversations ahead of this new outreach cohort. For first new prospect review, prioritize eLocal's explicit first-party roofing call category, then Polyares's onboarding, then the other two conditionally. No outbound without new founder approval.


### First-party validation improvement

The existing `scripts/probe_buyer_network_direct_sites.py` now tests
**one additional official publisher page per reviewed company**, derived
from the reviewed HTTPS seed and restricted to the same host. The other
eight standard site probes remain unchanged. This fixes a known blind
spot where `/affiliates`, `/for-affiliates`, `/affiliate-contact` or
the pay-per-call programme page are not at `/publishers`.

This is not a new crawler, separate queue or live API subscription. It
is the original bounded first-party domain probe with one additional
same-domain evidence check on four pre-reviewed company pages.

Evaluation is intentionally restricted to operational novelty and
first-party published eligibility until we have **independently confirmed
buyer replies and payable outcomes**. No publisher has approved EmpireOS
to send traffic by virtue of a source path, and a domain count is not
a conversion/precision metric.
