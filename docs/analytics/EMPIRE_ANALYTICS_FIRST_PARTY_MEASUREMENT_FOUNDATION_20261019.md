# Empire Analytics — first-party measurement foundation (readiness wave)

19 October 2026 | Actual EmpireOS build, no production tracking enabled

## What was already present
Existing live Tag Intelligence timer and monitor:
  empire-tag-intelligence.timer
  empire_os/tag_intelligence.py
  empire_os/tag_intelligence_probe.py
  empire_os/tag_intelligence_monitor.py
  runtime/tag_intelligence/latest.json

The existing snapshot for https://empire-ai.co.uk was available and
generated on 19 October 2026 at 07:16:42 UTC. It is a bounded STATIC
MARKUP observation of one site/page. It did NOT attest GA4, Google
Tag, or GTM IDs; consent_mode_enabled was unset/unknown. This does
NOT prove no analytics can exist elsewhere, and it certainly is NOT
proof of zero visitors. It explicitly disclaims event delivery,
legal consent, advertising delivery and revenue proof.

The user wants a serious Google Analytics-class Empire-owned platform:
real traffic, engagement, source/medium, funnels, segmentation and
verified commercial/revenue attribution in a premium Empire AI UI.

## Implemented without new infrastructure or recurring work
- empire_os/analytics/measurement_readiness.py:
  a bounded, read-only, fail-closed adapter for the ALREADY running Tag
  Intelligence monitor. Attests source timestamp, OBSERVE mode, static
  homepage observation and safe tag presence indicators. Never exports
  tag IDs, site URLs with parameters, user data or secrets. Stale or
  contradictory snapshots return HELD, not invented zero traffic.
- scripts/review_empire_analytics_collection_readiness_20261019.py:
  --read-only one-shot command; no network, systemd or DB changes.
- empire_os/analytics/first_party_event_contract.py:
  offline, bounded contract for ALLOWLISTED future website events,
  supported names only: page_view, engagement, cta_click, form_start,
  form_submit_attempt. Only UTC timestamps, ephemeral opaque 32-hex
  event/session nonces, owner-registered static page paths. Deliberately
  no IPs, emails, user agents, cookies, URL query strings, referrers,
  purchase/revenue claims or arbitrary form body. No browser-provided
  acquisition label or consent flag accepted.
- Two required external SERVER-SIDE resolvers must prove website
  analytics consent and acquisition channel. The separate CRM prospect
  opt-in API is NOT equivalent to website tracking consent. A missing,
  unavailable, non-true or untrusted resolver holds the entire batch.
- Duplicate retry IDs are deduped; conflicting reuse is refused.
  Events are capped at 500 per offline batch and timestamps at 48h.
  Unknown/PII-bearing fields, invalid paths, future data and mixed
  unknown source cases fail closed.
- The aggregation helper NEVER exposes event/session IDs, query
  strings or individual user paths and ALWAYS labels output
  SIMULATION_ONLY. Form submit attempts are not verified enquiries.
  No developer should add its simulated counts to live dashboards.

## Critical remaining data/consent gates
1. Exact public-site ownership and authorisation from ASTRA for
   changes to the website, consent UI and event sender.
2. Review UK PECR/GDPR and relevant jurisdictions. Necessary
   operational logging is NOT blanket authority for analytics storage
   or optional cookies. Decide on purpose, consent basis, withdrawal
   behavior and retention. This wave makes no compliance certification.
3. A canonical, independently verifiable website analytics consent
   ledger. Do not reuse cold-email opt-in, invented browser booleans,
   or silently infer consent from page access.
4. A server-side anonymous session issuer and trusted acquisition
   origin classifier. Reject browser-supplied source/medium claims,
   secrets in UTM query strings and referral URLs.
5. Authenticated first-party intake service using rate limits,
   CSRF/origin validation, strict event dedupe, bot/noise filtering,
   bounded storage, controlled retention and monitoring. Endpoint
   remains NOT BUILT / NOT ENABLED in this wave.
6. Once observed by the *live* approved collector, reconcile bounded
   event aggregates to EmpireDB tenant-aware attribution records.
   CRM lead confirmation and realised BSC revenue need separate
   canonical receipts; clicks and forms are NOT lead/revenue proof.
7. Only then show site sessions, engaged sessions, channels,
   conversion rate, device/geo aggregates, attributed revenue and
   future Predictive Revenue confidence intervals in the live UI.
   Before then, retain "Not connected" rather than fake metrics.

## Verify now (existing production only, read-only)

    cd /srv/empire_os
    ./.venv/bin/python -m scripts.review_empire_analytics_collection_readiness_20261019 --read-only

Status on today's snapshot:
  STATIC_HOMEPAGE_TAG_SOURCE_OBSERVED_COLLECTOR_HELD
  static_homepage_observation_verified=true
  lawful_website_analytics_consent_verified=false
  website_sessions_verified=false
  first_party_collector_activation_verified=false

Tests:

    ./.venv/bin/python -m pytest -q \
      tests/analytics/test_first_party_event_contract_20261019.py \
      tests/analytics/test_measurement_readiness_20261019.py

The existing Tag Intelligence tests continue to pass. No public site
edits, founder-console restarts, API activation, migration, payments,
tracking cookies, external API calls or outbound communication.
This work is separate from the user-approved branded dashboard release
which is already deployed privately.
