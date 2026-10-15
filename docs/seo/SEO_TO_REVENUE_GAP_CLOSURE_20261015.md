# EmpireOS — SEO → Verified Revenue gap closure, 15 October 2026

**State:** OBSERVE / founder review. **Existing owners:** Empire SEO Director, website/gateway owner, commercial buyer partnerships, EmpireDB owner. **No new services, timers, paid spend, consumer routing or automated outreach.**

## Production observations (read-only)

1. **All four host/scheme variants serve duplicate HTTP 200 pages.** At 21:17 UTC on 15 October, `https://empire-ai.co.uk/`, `https://www.empire-ai.co.uk/`, `http://empire-ai.co.uk/`, and `http://www.empire-ai.co.uk/` all returned HTTP 200 with exactly the same first-party homepage SHA-256 prefix `6c4b927c1426891a1ec1`. Each includes the preferred HTTPS apex canonical. This is a redirect/canonical consistency gap, **not** proof of lost rankings. The production `empire_os/public_gateway.py` has concurrent uncommitted legal-route changes. The separate read-only policy `empire_os/public_canonical_host_review.py` is prepared and tested but not wired. **Owner action:** review ingress and implement safe HTTPS non-www 301/308 on ordinary public GET/HEAD pages, preserving checkout, OAuth, A2A, APIs, consent, static resources and tracking; test before/after. Do not edit the other owner's work.

2. **Five published, sitemap-listed research pages have no incoming link from the 20 sitemap-listed pages' `<main>` anchors.** Original bounded sitemap crawl: 20 URLs, no obvious broken internal destinations from their main content. Orphan candidates (all HTTP 200, self-canonical, non-noindex) are:
   - `/research/campaign_3438b6c3b110f941407ce1dd` — Denver roofing, coverage-gap methodology, ~4,092 visible characters
   - `/research/campaign_948947123543615f2c6eab7f` — Atlanta class-action research, ~3,717 characters
   - `/research/campaign_7d5e758b1ec56415de7516a6` — NYC general-contractor research, ~3,570 characters
   - `/research/campaign_99a64a18052abf58600b64a6` — Dallas–Fort Worth HVAC research, ~3,774 characters
   - `/research/campaign_83ccabdbe7356a6f17d77440` — Denver HVAC research, ~3,402 characters

   These are explicitly internally projected **research methods**, not verified external market findings or paid customer case studies. They carry original headings and caveats, but the existing `owned_campaign_release.load_release()` reports five published campaigns with zero paid-media spend. Their content and release hashes are pinned. **Owner action:** independently review source/reader value and disclosure; only then connect relevant pages through contextual, restrained links from existing industry content or approved research navigation. If insufficiently valuable, review whether they belong in the sitemap. Never mass-publish or redirect unrelated legacy AEO 404s. Do not edit `owned_campaign_content.py` casually: changing the generated HTML invalidates the published campaign hash contract and may fail-close all five routes.

3. **Research enquiries are separate from commercial form acquisition counts.** The five `/research/campaign_*` pages submit JSON to `/api/research/enquiry`, backed by `public.record_owned_campaign_enquiry(jsonb)` and `public.owned_campaign_enquiries` under EmpireDB migration 025. The existing founder canonical sales aggregate `scripts/probe_canonical_sales_intake_aggregate_readonly.py` counts only `first_party_commercial_sales_enquiry` and `self_serve_predictive_revenue` in `public.prospect_acquisitions`. Consequently its zero count, if returned, **is not a count of research form submissions**. **No direct research table rows or personal details were read in this audit; actual research submission count remains unknown.** Owner action: request an authorised read-only, count-only EmpireDB observer of research enquiries and `campaign_enquiry_submitted` server events. Keep research interest separate from buyer-stated commercial opt-ins, verify appropriate retention/consent and decide whether a founder-reviewed, explicit identity join is lawful/needed before any CRM promotion. No new privilege, access grant, DB write or outbound without review.

4. **GSC numbers predate today's SEO releases.** Connected sitewide `sc-domain:empire-ai.co.uk` baseline 15 Sep–13 Oct: 83 impressions / 1 click, versus 168 / 3 previously; only 27 impressions shown in the bounded visible query/page subset. All four commercially improved pages were published on 15 October with SHA-matched receipts. This is **not** proof of post-release uplift or failure, nor evidence of a payable click. Use the existing scorecard, do not spawn another SEO telemetry service.

## Genuine warm solar publisher — action before spend

Solar Briton sent an inbound business reply on 15 October, explicitly willing to **explore** a 30-day, no-upfront tracked-referral/revenue-share pilot. Their finance/marketing team requested a payable outcome and proposed rate, attribution window, reporting, installer/postcode coverage with MCS numbers and consumer code membership, and data roles/deletion. They state they are editorial only today and have no pre-existing consumer enquiry handoff. Their suggestion is either named-company opt-in with appropriate permission or a link to Empire AI's own form, subject to written terms.

**Commercial roles:** Solar Briton is a potential *upstream publisher*, NOT proof of a downstream installer buyer. An outbound publisher commission payable by Empire AI is not revenue to Empire AI. No named/contracted UK installer with postcode capacity, billable definition, acceptance/reversal rules and settlement has been evidenced here. Do not invent payout rates or offer a live quote form. A generic commercial B2B enquiry form is NOT a verified solar homeowner quote/consent-transfer flow. Do not purchase the previously offered €800 annual placement. **Recommended sequence:** establish verified accepting downstream installers and service areas; negotiate written payout terms to Empire AI; calculate affordable upstream referral share from actual margin and reversal risk; agree disclosure, source approval, 30-day test scope, named consent and reporting; only then obtain founder approval for any source-to-buyer activation. No message sent as part of this audit.

Independent compliance/verification reference points:
- ICO, transparent collection and lead generation: https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/direct-marketing-guidance/collect-information-and-generate-leads/
- ICO, planned information sharing and electronic marketing: https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/direct-marketing-guidance/plan-direct-marketing/
- RECC, public consumer code membership search: https://www.recc.org.uk/scheme/members
- MCS, 2026 transition guidance: https://guidance.mcscertified.com/books/mcs-guide-to-moving-over/

## Ranked next owner decisions

**P0 — Commercial acceptance:** obtain one actual UK solar installer/aggregator willing to buy an accepted enquiry, with MCS and consumer-code verification, geography, payable event, refunds and signed terms. Until then, Solar Briton remains *warm publisher research* with zero active routing or payout. Draft only; founder approval before sending.

**P0 — Enquiry visibility:** establish the authorised count-only readback of first-party `owned_campaign_enquiries` in EmpireDB; compare against canonical consented commercial CRM aggregates **without** treating research interests as consent for transfer or promotion. No PII disclosed in general reports.

**P1 — Canonical host:** existing gateway owner integrates/tests the already prepared redirect policy and Cloudflare trusted host behaviour. Avoid collisions with active legal work.

**P1 — Research page usefulness:** editorial review all five indexed research worksheets, then either connect relevant source-honest pages via existing industry navigation or hold sitemap inclusion pending independent research.

**P1 — Post-publication GSC:** recheck when Google data for Oct 15+ is actually processed; compare page impressions/clicks vs correct baseline, do not fabricate conversions.

**Evidence rule:** Real data → sourced intent → consented enquiry → identified accepting buyer → approved payable terms → accepted event → settlement → realised revenue. None of today's page views, publisher interest, orphaned content or old GSC impressions satisfies the financial stages.
