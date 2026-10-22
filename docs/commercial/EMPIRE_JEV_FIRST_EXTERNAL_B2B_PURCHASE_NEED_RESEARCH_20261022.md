# EmpireOS — original public B2B need signals, not government tenders

**22 October 2026 · Manual public-web Research review · US/GB · Observe only**

## Commercial goal

Find companies **explicitly seeking qualified appointments, better
conversion, lead-generation help or software**, instead of treating federal
construction tenders, historical permits, old CRM records or forum commentary
as a confirmed Empire AI customer.

This source packet extends the current Jev/Intent Brain/Buyer Scout Research
review flow. It does not add a second collector, CRM, email agent, identity
database or automatic outbound pipeline.

## External original public page findings

The following candidate source pages were opened or read through web review.
The EmpireOS server's direct Reddit JSON endpoint returned **HTTP 403**, so
these are **manual public-page observations**, not claims of live Search
Fabric ingestion, independent verified business registration or source
licensing.

| Source date, geography | Original public post | Genuine stated need | Next evidence gate |
|---|---|---|---|
| 10 Sep, Tennessee, USA | https://www.reddit.com/r/LeadGenMarketplace/comments/1wciats/roofing_lead_generation/ | Roofing company representative says it seeks qualified booked appointments; offers 10% of closed deals, refuses upfront/PPL fees | First verify company and authority; capacity to deliver organic appointments and precise signed revenue-share/attribution terms unproven |
| 17 Jul, Pennsylvania, USA | https://www.reddit.com/r/smallbusiness/comments/1uzetzd/roofing_siding_business_owners_what_are_your_best/ | Owner says company wants 2–4 additional qualified appointments per week; previous Google Ads unprofitable | Identity; whether outside organic/conversion help is still wanted; forum prohibits commercial market research/spam |
| 17 Sep, Surrey, GB | https://www.reddit.com/r/smallbusinessuk/comments/1wirhh8/any_uk_roofers_finding_work_unusually_quiet_at/ | Roofer describes weak quote-to-job conversion and has already changed ads manager | Convert-vs-demand diagnosis; no evidence they are looking to hire another supplier, and existing relationship must be respected |
| 14 Jul, Florida, USA | https://www.reddit.com/r/Roofing/comments/1uwpnd6/commercial_roofer_in_fl_looking_for_advice_on/ | Self-described roofing partner seeking reliable commercial project leads, currently referrals | Public advice/research, not explicit purchase of our software or lead product |
| 7 Oct, US geography unspecified | https://www.reddit.com/r/GeneralContractor/comments/1wzjygh/lead_generation_marketing_whats_actually_working/ | General-contractor discussion about trust and results from lead-generation companies | Marketing-quality research only; the author has not been verified as a buyer |
| 10 Apr, Spokane, WA, USA | https://www.reddit.com/r/LeadGeneration/comments/1shjssl/desperate_for_leads/ | Third-party coach says an HVAC/electrical client needs more inbound calls | No original contractor's request or authority; aged indirect demand |
| 30 Jun, US agency | https://www.reddit.com/r/LeadGenMarketplace/comments/1uk1vw1/need_a_leads_gen_for_my_startup_web_agency_150/ | Web agency seeks accepted qualified small-business web-design leads; mentions $150/50 accepted, plus 10% paid-close commission | Over 90 days old; agency identity, payment/contract, business-only data provenance and source permission require fresh verification |
| 24 Jul, USA unspecified | https://www.reddit.com/r/RoofingSales/comments/1v5hfs1/looking_for_a_sales_opportunity_generation/ | A 1099 roofing salesperson seeks a reliable way to generate appointment interest | Individual representative authority for a company is unknown; not a canonical corporate buyer |

These are eight distinct public **source observations** across the UK and
US, *not* eight verified businesses, available leads, accepted referrals or
commercial conversations.

Two authors explicitly describe a supplier search. The more recent
Tennessee request carries major revenue-share/capacity constraints; the
web-agency request is stale and asks for sensitive contact fields requiring
a legitimate business-data purpose and provenance check. The other records
are company-need research, market discussion or third-party/role holds.
No consumer storm-hit addresses, telephone numbers, user profile identities
or inferred homeowner information were extracted.

## Existing Jev pipeline intake and guardrails

`empire_os/jev_external_public_need_review.py` accepts exactly the pinned
eight original public post IDs with manually classified source/market/date
metadata. It checks Reddit original-post URL identity and approved enum
values, refuses spoofed roles and purchase claims, and emits a bounded
review queue.

`scripts/review_jev_public_b2b_sources_20261022.py` emits
`JEV_EXTERNAL_PUBLIC_B2B_NEED_REVIEW_20261022.json` with a pinned source
checksum. **No source is admitted to the canonical signal inbox** because
source licensing, business identity and first-party rights haven't been
independently verified. All downstream actionable gates remain false.

**Required next original evidence steps** through existing owners:

1. Research/source-licensing owner: verify original post, authorial context,
   timestamp, community rules, commercial use restrictions and any later
   edits or withdrawal; confirm relevant geography and niche.
2. Buyer Scout/business-identity owner: independently establish the actual
   legal business/company, business representative authority, live stated
   needs and whether they are currently procuring permitted B2B services.
3. Offer/capacity owner: determine if Empire AI can lawfully and genuinely
   deliver the required result **without paid traffic**, and prove specific
   accepted-lead/appointment criteria, attribution and buyer terms.
4. CRM/tenant owner: search canonical prior contacts, opt-outs, bounced
   recipients, tenant ownership, and permission to contact. Only after
   independent checks should a proposal be drafted for founder review.
5. Economic-memory owner: recognise income only after actual accepted and
   settled payment, never a public post, source score or contract hypothesis.

## What this does not authorise

No DMs, scraping user profile emails, automated replies, cold calls,
person enrichment, homeowner lists, CRM mutations, UK/US data resale,
paid traffic, external paid Jev calls, payments or automatic supplier terms.
There are **zero independently verified buyers** and **zero authenticated
commercial purchase commitments** in this packet.

The procurement tender lane is still entirely separate and unaffected.

**Feature branch review only. Production unchanged.**
