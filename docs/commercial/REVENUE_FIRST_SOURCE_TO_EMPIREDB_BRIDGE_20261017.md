# Revenue-first website source to canonical EmpireDB enquiry evidence

17 October 2026 | Existing first-party commercial form and checkout API | Backend source staged and tested.

## Real missing commercial connection

A buyer-initiated consented commercial enquiry already reaches EmpireDB through the existing ingest_prospect_atomic RPC, but the form currently does not identify which first-party industry page was reported as the origin. This prevents even cautious website-page source review.

A strictly optional claimed_entry_page field now passes through the existing commercial request schema and existing record_founder_led_interest service. No DB table, new service, cookie, queue or tracking database.

Accepted exact page paths only: /, /commercial, /predictive-revenue, /industries/roofing, /industries/solar, /industries/hvac, /industries/property, /insights/revenue-opportunity-assessment.

External URLs, path traversal, query strings, fragments, personal identifiers, unsupported paths, invalid types and newline injection fail before DB invocation. A permitted non-null input adds a claimed_entry_page_review object to the existing EmpireDB RPC evidence JSON, with the page, source UNVERIFIED_BROWSER_SUBMITTED and five explicitly false claims: organic_search_attributed, search_click_proven, qualified_buyer_proven, marketing_consent_granted, recognized_revenue_proven.

Missing optional input stores NO page-source object, maintaining legacy semantics. The pre-existing canonical prospect contact_source, consent-to-respond record, real commercial form source_url, idempotency, deduplication, email-first preference and payment gates remain unchanged.

This is a BROWSER CLAIM, not independently verified SEO attribution. Aggregate Search Console query metrics cannot be associated with specific visitors from this field. A truly attributed sale requires authorized first-party source evidence linked to consented canonical prospect, independently verified buyer agreement/event, payment and fulfilment before recognizing revenue.

## ASTRA-owned UI integration, separate from backend

ASTRA currently owns apps/empire-public-site/src/app/commercial/page.tsx. It should preserve its live customer form while carrying the exact same-origin page source as the optional claimed_entry_page in the existing commercial POST. Only use an explicit reviewed page allowlist and ephemeral first-party referral context. Do not pass raw third-party referrers, UTM queries, emails, IPs or device IDs. Do not infer a visitor source from a direct navigation to /commercial.

The website has NOT been changed by this patch. Backend source changes need the existing separately authorized release and any appropriate service restart. Only once both are actually deployed and real opted-in enquiries occur can EmpireDB accumulate reviewed page-source claims.

## Bounded proof and safe release

Run the existing offline test suite:

    /srv/empire_os/.venv/bin/python -m pytest -q tests/test_first_party_commercial_source_evidence_20261017.py tests/test_first_party_sales_interest.py

The tests prove every allowed path, 16 rejected input types, consent-first validation, backwards compatibility, one existing RPC payload, nonbinding commercial authority and no automatic email or checkout. DB calls are mocked; do not create a fake prospect to prove a live route.

After approved deployment: use GET-only website/offer canaries, independently observed real enquiries and aggregate EmpireDB sales state. Never infer real client count or revenue from code/tests alone.

This is one minimal last-mile bridge, not a new CRM, SEO stack, lead router, payment processor or outbound service. No buyer capacity, payable call or recognized income is conferred by this field.
