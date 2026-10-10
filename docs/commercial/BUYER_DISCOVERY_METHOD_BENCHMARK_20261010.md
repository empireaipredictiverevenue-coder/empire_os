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


## 10 October — known-company buyer-demand pulse, not new buyer count

A second research pass discovered **fresh or recently visible publisher recruitment
claims from companies EmpireOS had already emailed**. The domain count would
miss them, so the existing commercial registry now accepts a private, bounded
`known_company_public_demand_review_latest.json` evidence file from
human-reviewed first-party pages or company-linked LinkedIn profiles.

| Existing company | Independently attributable public evidence | Research classification | Commercial issue |
|---|---|---|---|
| 1st Choice Marketing / 1stcm.net | https://www.linkedin.com/in/jason-kashou-1b662186 and official founder corroboration at https://www.1stcm.net/about/ | Public home-services publisher recruitment claimed; roofing is named | Prior September outreach unanswered; no fresh buy-box, terms or approval |
| MutualCall / mutualcall.com | https://www.linkedin.com/company/mutualcall and https://mutualcall.com/ | Publisher recruitment claimed for roofing, but the same network also **advertises calls for sale to buyers**; do not merge buyer- and seller-facing posts | Prior September outreach unanswered; both directions exist, exact role/campaign must be confirmed |
| Omni Call Network / omnicallnetwork.com | https://www.linkedin.com/company/omni-call-network and https://omnicallnetwork.com/services | Publisher recruitment claimed for home-services roofing, with SEO described as accepted; other posts seek buyers | Prior September outreach unanswered. Public consumer-service page lists `555-010x` example routing numbers, so it is **not** runtime proof of a working consumer call route |

These posts were reviewed on **2026-10-10**. Their actual publication
timestamps are **not independently established** by a date-scoped source,
and the registry records that distinction. A public post is not an accepted
buy-box, real traffic capacity, valid recipient, partner contract, payable
call or verified commercial outcome.

### Rules taught to the existing commercial scout

1. **Buyer role polarity**: explicit "buying calls / onboarding publishers"
   is publisher demand; "we have calls available / looking for buyers" is
   a supply-side pitch. If both occur in a single excerpt, mark MIXED and
   hold. Generic network advertisements are not buying intent.
2. **Existing-contact memory**: match against canonical company/domain
   identities and retain all prior emailed threads, suppression state,
   founder review requirements and the unchanged commercial stage. A new
   social post is not permission to send a duplicate email.
3. **Evidence quality**: trace a specific company source URL to a same-host
   official site, preserve source-date uncertainty and distinguish public
   marketing claims from live tracking, phone and payout verification.
4. **Comparable yield**: count independently corroborated novel publisher
   programmes and known-company demand reactivation separately. Neither
   is a realised revenue measure, and no model should claim conversion
   superiority until campaign acceptance and paid-call outcomes exist.

### Revised cold-start priorities

**Polyares first for small controlled volume**: official call-publisher
programme says one category, one state, one tracked number is an appropriate
test and written rates follow approval:
https://www.polyares.com/pay-per-call-affiliate-program .

**eLocal next, conditional on supply capacity**: its publisher programme
expressly conditions weekly publisher payments on an agreed minimum monthly
call volume and has a more detailed affiliate questionnaire:
https://www.elocal.com/affiliate-contact/ .

Both remain uncontacted, unapproved research opportunities.
Known-network reactivation should be via a founder-reviewed, suppression-
checked single contextual follow-up, not a fresh introduction.
Warm LeadBank, Validated and Connexis stay ahead for revenue.


**Quality caveat (1st Choice):** The company's public homepage
(https://www.1stcm.net/) contains apparent template/testimonial and
contact placeholders (for example an illustrative name and a clearly
nonstandard phone number). Its About page separately names Jason Kashou,
but neither page proves a buyer's operational routing. Mark as
`POSSIBLE_TEMPLATE_CONTACT_DETAILS_ON_WEBSITE` for diligence, not
as a categorical fraud finding. This and Omni's example `555`
numbers are the kind of false operational proof the research should
penalise instead of overlooking.


### Live-search provider result — 10 October 2026 (not a conversion win)

A bounded two-query run through the existing EmpireOS search fabric
returned **zero fresh domain results**. Diagnostics included Bing RSS
timeout/circuit-open, DuckDuckGo HTML/Lite HTTP 202/circuit-open,
Mojeek HTTP 403/circuit-open and non-relevant Bing HTML/RSS results.
The seed stage's Python API returned without raising an exception, so its
prior `error_count=0` was **not** evidence that search providers were healthy.

The existing `buyer_public_research_seed.py` now reports independent
`fresh_search_domain_count`, `fresh_search_result_status`, query-method
result counts including explicit zeroes, and
`search_provider_health_independently_verified=false`. It keeps separately
the four independently reviewed publisher programme seeds. They were
**not** discovered by the failed fresh run.

This identifies an actual operational blocker: search fabric availability
and extraction quality. Future improvement should independently verify
search source health, avoid repeated failed provider retries and leverage
bounded first-party site evidence without paying for third-party scraping.
Do not interpret code tests, zero exceptions or existing static seeds
as productive search yield.


## 10 October 2026, ~09:20 UTC — live buyer-search comparison

The live 12-query EmpireOS seed run found **4 fresh domains**, all from
one local San Antonio water-damage restoration query. Publisher-first
queries: **0 domains**. Dynamic buyer queries: **0**. This is a
usable *provider yield* observation, not confirmed network buying demand.

At that snapshot the registry comparison contained **206 unique domain
aliases**. Three of the four earlier externally reviewed publisher
programme domains had entered the canonical company registry:
`elocal.com`, `homevantaleadgroup.com` and `joinglobalwiz.com`.
`polyares.com` remained in the public research seed but was **excluded
from the candidate queue**, even though it has an explicit first-party
publisher application.

**Root cause:** `buyer_acquisition_scout.run_buyer_scout` considered
public research seeds only after opportunity/canonical/search results and
then applied a global `max_domains` cap. Publisher candidates could be
lost before the first-party probe. The resulting zero is not proof that
the programme is unattractive.

**Fixed method:** At most four explicitly source-tagged
`public:publisher_review:<exact-host>` domains may occupy
`max_domains // 8` reserved research slots. These never replace
opportunity/intent/priority canonical recovery seeds. They are
prioritised inside the **existing** bounded `max_probes` selection,
not given new traffic, a new queue, an extra timer or a verified buyer
status. If the batch is too small, zero reserved slots are allowed.
The research origin, lack of canonical identity verification and
blocked outbound authority are preserved. Tests include 50 unrelated
search hits crowding four first-party publisher programme pages.

### Actual onboarding and compliance comparison (publisher, not advertiser)

| Gate | Polyares | eLocal |
|---|---|---|
| Official publisher info | https://www.polyares.com/pay-per-call-affiliate-program | https://www.elocal.com/affiliate-contact/ |
| Published small-volume pilot | One category, one state, one number; no volume commitment advertised | Experienced publishers; payout cadence depends on agreed minimum monthly call volume |
| Source category | Owned directory/content traffic is supported, subject to approval | SEO/SEM accepted as an acquisition category, subject to publisher review and campaign rules |
| First contact route | https://app.polyares.com/register/start — account creation and **acceptance of Terms of Use** required to proceed | https://www.elocal.com/affiliate-contact/ — multi-step affiliate questionnaire with legal identity, phone, address and prior call-running questions |
| Rate/coverage | Individual category/geography rates in writing after review; call-duration threshold per category | Advertiser bidding and assigned tracking numbers; exact affiliate rate, minimum volume and buyer area are not yet provided |
| Settlement | Net terms, method, minimum and dispute window defined in later agreement | Published weekly payments conditional on agreed volume; independent signed terms still required |
| Existing EmpireAI supply | No independently verified billable calls, buyer allocation or signed publisher relationship | No independently verified billable calls, buyer allocation or signed publisher relationship |
| Founder gate | **Do not create account or accept website Terms** without founder review | **Do not submit legal company identity or accept terms** without founder review |

**Preferred next test:** Ask Polyares to validate *one actual roofing
buy-box* (a specific state/ZIP subset), exact allowable first-party organic
traffic source, publisher-specific duration threshold, written billable-call
rate or formula, duplicate/dispute terms, tracking handoff and settlement.
The website's built-in sample $25 payout and 60% acceptance are explicitly
illustrative, NOT a price quote or a revenue prediction. Do not claim we
already have monthly traffic or calls. No live route should be opened
until proof.

**eLocal alternative:** Determine realistic minimum monthly call volume,
what happens to payables below that minimum, source approval requirements,
effective network margin and the permitted number of parallel publishers.
The application has mandatory legal and telephone information not verified
in this research; do not fabricate or submit it.

**Revenue experiment:** When a real publisher buys our traffic, compare
*accepted payable calls / connected calls*, gross accepted payout,
rejected-call reasons, net money settled per qualified visit, source
attribution and payments actually received. Do not use domain novelty
or aggregate website traffic as the success metric. Preserve buyer-specific
suppression, legal approval and traffic gates.
