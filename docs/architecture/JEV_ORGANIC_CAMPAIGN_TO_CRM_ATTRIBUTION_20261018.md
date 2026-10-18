# Empire AI — Organic campaign URL → founder-led enquiry evidence integration

**Date:** 18 October 2026
**Branch:** `feature/jev-newsjack-traffic-20261018`
**Site owner:** ASTRA/flagship; **sales owner:** existing first-party commercial intake.
**Current implementation scope:** isolated feature code, unit tests and offline API tests.
**Production deployed:** NO. No genuine test enquiries submitted.

## Actual gap and reused assets

The existing canonical industry pages `/industries/solar` and
`/industries/roofing` have ordinary `href="/commercial"` calls to action.
The existing `/commercial` React form submits to
`/v1/checkout/commercial/interests`, proxied to the canonical checkout
service and recorded through `first_party_sales_interest.record_founder_led_interest`
via EmpireDB's existing `ingest_prospect_atomic` RPC.

The previously built NewsJack/Marketing Director handoff emits
campaign-scoped URLs to those industry pages, but no end-to-end campaign token
was carried to the enquiry. The separately owned `/research/{campaign_id}`
runtime already has event and enquiry capture for **released** research
campaigns and is not replaced or broadened here.

## Added: one-hop link token support, no identity tracking

1. `apps/empire-public-site/src/lib/organic-campaign-touch.ts` validates
   the exact URL parameters `utm_source`, `utm_medium`, `utm_campaign`,
   `utm_content`, matching a `campaign_<24 hexadecimal>` identifier with a
   known channel+asset suffix. Accepted sources: LinkedIn
   (`organic_social`), YouTube (`organic_video`) and owned newsletter
   (`email`). Direct /commercial URL tokens also require the explicit
   `utm_landing` path in the allowed page set. No free-form URLs or visitor
   identifiers enter this contract.
2. `OrganicCommercialLink.tsx` reuses the existing /commercial link on
   two industry CTAs. The original SSR href continues to function without
   JavaScript. On hydration, it adds the strict campaign token only if the
   user arrived on an allowlisted, campaign-tagged industry page. This
   supports normal click, new-tab and copy-link journeys. No cookies,
   localStorage or visitor profile.
3. The existing Commercial form reads a valid one-hop token from its own
   URL, and only includes it on a voluntary, consented form submission;
   no automatic event write on the page.
4. `FounderLedCommercialInterestRequest` accepts optional `organic_touch`.
   `first_party_sales_interest.record_founder_led_interest` validates it
   via `empire_os/organic_campaign_touch.py` and, after specific-contact
   consent, stores it as an additional, explicitly **unverified link token**
   in the existing EmpireDB `p_evidence` payload. It does not alter
   `contact_source`, suppression, buyer identity, pricing, terms, checkout,
   orders, payment, or the idempotency key.
5. Without this token, legacy enquiries retain their original schema and
   behaviour. Invalid tokens fail before database write.

## What the fields mean

- `campaign_id`: proposed campaign ID from a tagged URL; NOT a verified
  marketing campaign activation.
- `asset_id`: proposed channel asset; NOT a publication receipt.
- `source` and `medium`: URL claim; NOT a cryptographically confirmed
  referrer or a recorded social-platform click.
- `landing_path`: allowlisted industry/owned entry path; NOT an
  independently recorded session.
- `evidence_class=BUYER_SUBMITTED_URL_CAMPAIGN_TOKEN_ONLY`.
- `session_verified=false`,
  `channel_click_verified=false`,
  `source_campaign_registry_verified=false`,
  `attributable_enquiry_confirmed=false`,
  `revenue_attribution_confirmed=false`.

This feature **does not** install a general analytics SDK, create a
cookie, start a marketing mail list, record a pageview, assert a campaign
conversion, or join revenue records without actual independent evidence.

## Privacy and QA checks

- Event collection or new session measurement requires separate
  analytics/consent handling by the existing owner.
- New code never reads raw referrer URLs, stores a visitor identity, or
  sends an outbound email.
- Bad domains, fake campaign names, unknown landing paths, mismatched
  source/medium, duplicate URL keys, invalid asset suffixes and
  unconsented submissions are rejected.
- Python tests cover the optional EmpireDB evidence path with a **mocked**
  canonical RPC, plus non-consent/no-write and existing API compatibility.
- Browser helper tested using Node's built-in test runner without browser
  instrumentation. Site TypeScript check passes.
- The existing /research campaign event contracts remain unchanged.

## Next genuine verification

1. ASTRA/site owner to review the **isolated** component changes against
   its current flagship work and merge without overwriting other agents.
   Checkout owner to review optional backend evidence schema and deploy
   both compatible halves together after standard owner tests.
2. Check actual live rendered industry CTA, /commercial form and checkout
   status after deployment; do **not** submit fake production prospect PII.
3. Only when a genuine buyer voluntarily submits an enquiry via a
   published approved campaign, verify the canonical prospect record
   and `organic_campaign_touch` with the existing founder-readonly CRM.
4. Join a genuine campaign or click receipt independently through the
   existing Marketing Director event ledger; until then the URL token
   remains a **claimed source**, not confirmed attribution.
5. Require actual source-scoped landing visitors, confirmed form receipt,
   qualified conversation and recognised-payment/fulfilment evidence
   independently before any traffic-to-revenue metric is reported.

**Result:** a unit-tested, minimal one-hop integration patch, not a claim
of deployed, revenue-proven or session-observed attribution.
