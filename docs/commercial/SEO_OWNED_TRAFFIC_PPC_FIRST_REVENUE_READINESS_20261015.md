# Empire AI — First-party SEO + PPC revenue readiness (15 October 2026)

**Owner:** Empire AI SEO Director, Commercial Exchange and Business Development. **Production:** OBSERVE only. **Budget:** £0. **Policy:** first-party owned website, own EmpireDB, existing Search Intelligence and affiliate attribution; no new server, paid model, new timer, paid ads, third-party content farms or automatic publication.

## Real baseline — not estimated search volumes

Read the live, authorised Search Intelligence loopback Google Search Console adapter for `sc-domain:empire-ai.co.uk` (queried 15 October; final included date **13 October**, allowing processing lag). Use the existing, separately developed SEO director's `organic_revenue_baseline.py` for exact validation and query-privacy handling.

| Identical 29-day windows | 15 Sep–13 Oct | 17 Aug–14 Sep | Proof |
| --- | ---: | ---: | --- |
| **Sitewide daily Search Console impressions** | **83** | **168** | `GSC /search-console/daily`, dates dimension |
| **Sitewide daily organic clicks** | **1** | **3** | `GSC /search-console/daily` |
| Query + page returned impressions | 27 | 94 | `GSC /search-console/observations`, anonymised/omitted queries possible |
| Query + page returned clicks | 0 | 0 | Not a contradiction with the sitewide daily report |
| Query + page distinct queries, latest period | 10 | 29 | Only queries exposed in the API report |
| Legacy AEO page query impressions | 16 | 91 | Query/page subreport only; **not** verified value or ranking |
| Current GSC query/page coverage of sitewide impressions | **32.53%** | **55.95%** | Remaining queries/visits not observable by keyword, do not invent details |

A sitewide GSC click means a searcher entered the site. It is **not** an advertiser click, lead, bought call, earned PPC commission or invoice. Zero independently verified billable CPC events were found by this review; that does **not** assert all Empire AI revenue is zero.

**Indexability readback:** `https://empire-ai.co.uk` homepage; `/industries/roofing`, `/industries/solar`, `/industries/hvac`, `/predictive-revenue` all return HTTP 200 with one title, H1, description and matching https canonical, with no observed `noindex`. These are **technical signals**, not independent proof of Google's indexing or high editorial quality. `/roofing` is HTTP 200 with `noindex,nofollow` and remains BUYER-GATED — **do not remove** until buyer/source, privacy, tracking and founder activation approval. `/privacy` and `/terms` are now public HTTP 200, but do not currently show matching canonical tags; do not treat their new public status as evidence of legal approval or unpublish them automatically.

**Canonical duplication:** `https://www.empire-ai.co.uk/` is HTTP 200 without redirect to the preferred root, as is `http://empire-ai.co.uk/`. GSC attributes impressions across both www and apex homepage variants. Ask website owner to verify exact routes, HTTPS, asset compatibility and 301/308 redirects to one preferred host; preserve canonical and trust/checkout/Google OAuth traffic. **No redirect or DNS mutation has been made by this SEO review.**

**Existing site structure:** sitemap currently lists 20 owned URLs, including three selected AEO locations and industry pillars. More than 200 legacy `_aeo_pages` templates exist on disk, but disk presence is **not** proof of publication or indexing. No mass sitemap/indexation release: Google's scaled-content and doorway policies require distinctive first-party value and correct geography. See https://developers.google.com/search/docs/essentials/spam-policies .

**Health mismatch:** `/v1/search/search-console/status` reports the configured property `ready` and the same live API serves actual Google data. Its long-running `/v1/search/summary` and `/health` still report `credentials_not_configured` through old status code. A controlled restart of **existing** `empire-search-intelligence-api.service` is needed only after regression/read-back; avoid new infrastructure. This status error must not be used to claim lost Google credentials.

## Build ONE original conversion-oriented asset at a time

**P1: `Roofing buyer criteria & real call quality` — B2B revenue buyer-facing resource.** Expand `/industries/roofing` with sourced answers to: what counts as a qualified installation/replacement inbound call; how first-party SEO differs from aggregated supply; where consent/recording/ANI/ZIP constraints matter; what events count as accepted and payable; and why unverified buyer rates cannot be quoted. Use first-party observations and externally verifiable primary sources, not fictional buyer logos, testimonials or payout numbers. CTA: `Request a documented roofing buyer-corridor review` *only* after the existing first-party CRM/lead form consent and routing are verified. Keep consumers off unapproved `/roofing` PPC/phone route.

**P2: `Solar publisher-to-installer economics` — prospective UK/AU solar partner-facing resource.** On `/industries/solar`, explain UK MCS/postcode coverage versus Australian state/installer coverage; distinguish website visitor clicks, leads, booked appointments and completed installations; list buyer acceptance requirements and clear referral disclosures. Cite appropriate original buyer/operator evidence before publication. SolarBriton remains a publisher discussion; no downstream buyer buy-box is signed.

**P3: `Predictive revenue: evidence versus forecasts` — EmpireOS product demand.** Improve `/predictive-revenue` with the exact evidence loop from verified search signal to opportunity, buying terms, fulfilled outcome and reconciliation, including honest unknowns. Link internally to `/industries/roofing`, `/industries/solar`, `/trust` and existing B2B commercial offering, subject to manual editorial and website owner review. Do not conflate site SEO traffic with realised revenue or generate fake case studies.

**Page-release checks:** one genuinely useful audience, original editorial evidence, precise title/H1/meta/canonical, internal navigation, accessible fast-rendering site, product/source fit, country-specific buyer/consent review, no paid/referral links before contract, complete disclosures and `rel="sponsored"` for any later affiliate/paid links (https://developers.google.com/search/docs/crawling-indexing/qualify-outbound-links; FTC https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking). Do not automatically mass-produce location swap pages or manipulate clicks.

## Four distinct money models — keep PPC honest

| Model | Where money would come from | Current gate | Next real-world proof |
| --- | --- | --- | --- |
| **Paid advertiser click (PUBLISHER_PPC/CPC)** | A *specifically approved advertiser/buyer* pays for verified unique outgoing clicks | **NO signed Empire AI payable-per-click buyer.** Existing `affiliate_tracking` supports model tokens in review; ingress `/r/` remains all-404, canonical writer absent, no redirect or click revenue. | Obtain signed per-click commercial terms, accepted country/niche/SEO source, unique/invalid click rules, amount/currency, refund/settlement, source/consent, canonical idempotent paid-event recording, partner reconciliation and founder authority. |
| **Pay per qualified call / form lead (PPCALL/PPL)** | Known US or UK buyer pays under actual accepted event definition | Zach / Validated is a live US conversation; 15 Oct status check sent. LeadBank, Inquirly, Connexis have separate ongoing packets. No current accepted buy-box/approved delivery. | Buyer-signed campaign and ZIPs, source approval, payable event, route/caller-ID/consent, reconciled accepted event and payment. |
| **Publisher display ads** | Approved contextual ad network pays for eligible ad impressions | Optional commercial route, **no Empire AI ad account/serving approval verified**, no ad code installed. | Founder choice whether to use an external platform, site policy/original-content review, account acceptance, legal/privacy approvals and ad inventory. |
| **Paid search PPC advertising** | Empire pays advertisers/search platform for purchased clicks to its own first-party offers | **DISABLED: £0 authorised budget**, no verified positive conversion economics. | After real buyer payout/ROI proof and funds: a *separate* founder-approved capped ad campaign; never use affiliate buyer funds or blindly send traffic. |

**Zero-spend monetisation priority:** organic-first site conversion and existing warm US roofing buyer; then approved PPL/pay-per-call pilots; pursue direct CPC as a separate negotiated buyer contract. Do not treat public network affiliate pages as per-click contracts. Google AdSense has free signup but is not first-party infrastructure and is intentionally optional; see https://support.google.com/adsense/answer/9724/eligibility-requirements-for-adsense and https://blog.google/products/adsense/evolving-how-publishers-monetize-with-adsense/ .

## Delivered code and strict limits

- Reuses the SEO Director's existing, independently tested `organic_revenue_baseline.py` GSC proof validator rather than starting another search agent.
- `empire_os/search_intelligence/organic_ppc_commercial_review.py` joins bounded GSC and first-party page metadata to honest PPC/PPL/call/ad readiness decisions, with fixed researched partner roles and per-country labels.
- `scripts/inspect_owned_organic_ppc_readiness.py` fetches only eight predetermined company pages and the `www` homepage; no redirect follows, indexing call, commercial action, live ad tags, traffic-buying API, remote seller, model or database. It consumes an existing time-limited GSC snapshot and prints a PII-free operator report. No recurring timer is added.
- The independent SEO director's older indexability probe rejects the now-published `/privacy` and `/terms` routes because it still expects 404s. That ownership-sensitive rule needs a separate **evidence-based adjustment** after reviewing legal publication; do not weaken buyer-page `noindex` or silently bypass the hold. This bridge's scoped audit handles those pages as public, incomplete metadata without any legal approval inference.

**Status to use:** search measurement connected; sitewide search demand low; five technically indexable core pages; `/roofing` safety hold preserved; advertiser CPC contract not verified; paid advertising off; affiliate referrals and revenue execution off; content and website changes must be reviewed by their owners. No payments, new infrastructure, sends or site writes happened in this task.
