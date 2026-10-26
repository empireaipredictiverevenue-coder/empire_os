# EmpireOS original sales GET-only canary for AEO source-hint integrity

26 October 2026. Original first-party sales surface GET canary and original SEO daily observer only. No new service, cron, database, tenant writer, lead form, enrichment provider, ad spend or outbound.

Original deployed AEO V2 market paths:
- /aeo/general_contractor/NYC/
- /aeo/hvac/DFW/
- /aeo/roofing/DFW/

Original first-party commercial intake stores only the strictly bounded and consented buyer-declared source (UNVERIFIED_BROWSER_SUBMITTED). Future public-site rebuilds could accidentally change an AEO link or omit the Commercial frontend allowlist, silently dropping this useful claimed path while keeping the general enquiry page live.

The existing scripts/probe_first_party_sales_http_readonly.py now contains an additive inspect_aeo_claim_handoff() function that uses its original bounded same-origin loopback GET transport, without any browser automation or form submission. It checks each of the three published market pages is HTML HTTP 200 with the exact intended one approved entry-query + Commercial form anchor, and their original slashless self-canonical. Then it checks exactly one original deployed Commercial compiled page JavaScript supports all three paths and the existing intake endpoint. External scripts are never fetched.

The existing scripts/review_original_seo_action_lifecycle_20261026.py invokes this bounded canary as part of the pre-existing daily SEO sequence and appends aeo_source_handoff_canary status to the existing immutable daily SEO receipt. An invalid canary is HELD and does not overwrite Google inspection, misreport visits, disable checkout or create another timer. The existing first-party generic sales canary behavior and private CRM authentication canary remain unchanged.

A successful report proves publicly deployed *static navigation and compiled JS support only*. It never establishes actual visitor behavior, source/SEO attribution, consented enquiry receipt, CRM presence, qualifying customer, accepted order or revenue. Any future canonical source count requires the existing privileged Ops Control and exact CRM evidence owner.

Tests: 56 focused original/new tests, including missing link/canonical, missing bundled allowlist, broken script, external URL non-following and daily integration. Live GET-only trial returned three verified links plus matching original Commercial JS, without writes or outbound.
