# Empire Analytics — Dormant HTTP ingestion contract, zero live tracking

19 October 2026 | Build wave 2 | Founder Analytics continuation

## Purpose

Continue the existing Empire Analytics first-party measurement project,
not a parallel CRM, public server, tag manager, session DB or new payment
system. The branded Founder Console is active and first-party GSC
graphs remain separate from actual website sessions.

Current live read-only Tag Intelligence audit shows static homepage
source observed; GA4/GTM, website-analytics consent, visitor sessions,
actual conversion and realised revenue are NOT independently verified.

## Added source

- empire_os/analytics/dormant_event_ingress.py:
  FastAPI router factory with one explicitly named test-only route,
  /v1/analytics/_simulation/events. UNMOUNTED in production.
  Defaults to disabled (HTTP 503). Local simulation requires the exact
  factory test flag, EMPIRE_ANALYTICS_TEST_MODE=LOCAL_TEST_ONLY,
  a loopback peer, strict same-origin request headers, approved static
  paths and injected server-side consent/acquisition resolvers.
  No writer, storage or cookies are available.
- Reuses existing EmpireOS IntakeLimiter; maximum request 32 KiB,
  JSON-only and no compression, cookies, bearer token or forwarding trust.
- Reuses the already tested simulate_verified_batch event contract:
  allowlisted event names, ephemeral nonces, strict UTC time window,
  dedupe, PII field rejection, server consent and source authority.
  Returns simulated aggregates only, never personal identifiers.
- scripts/review_empire_analytics_dormant_ingress_20261019.py
  is a read-only operator; marks source collected events as unverified.
- tests/analytics/test_dormant_event_ingress_20261019.py
  covers unmounted/default-off safety, origin/credential controls,
  request bounds, injection, nonce replay, reused rate limiter, server
  proof failures and explicit no-write simulated output.

## IMPORTANT — Not an activated visitor collector

No public site / ASTRA release edits.
No systemd restart or additional service process.
No new database, cookies or individual visitor storage.
No production intake of website event traffic.
No revenue, buyer or conversion claim; test fixtures are simulations.
Not mounted on Search Intelligence API or public gateway.
An isolated FastAPI TestClient test verifies the HTTP contract; it is
not actual live site analytics.

## Safe operator command

    cd /srv/empire_os
    ./.venv/bin/python -m scripts.review_empire_analytics_dormant_ingress_20261019 --read-only

Expected:
    DORMANT_HTTP_CONTRACT_READY_COLLECTION_NOT_AUTHORISED

## Further required gates

1. Public-site owner ASTRA approval on the exact consent UI and tag.
2. UK GDPR/PECR and applicable jurisdiction-specific purpose, notice,
   lawful basis, preference/withdrawal and retention review.
3. Canonical per-session analytics-consent ledger in EmpireDB, not
   prospect email opt-ins nor browser-provided booleans.
4. Secure session issuer and independently resolved acquisition source.
5. Property-/tenant-partitioned durable store and verification receipts,
   controlled retention, bot/duplicate checks and no raw PII capture.
6. Public gateway rate limits, CSRF/origin checks, rollback and audit.
7. Only then activate and independently verify live source receipts,
   traffic, engagement and acquisition charts in Empire Analytics.
8. CRM conversion and realised revenue require separately verified
   original commercial receipts and settlement, not browser event counts.

GSC search impressions are not visitor sessions. Unknown remains
Not connected, rather than zero.
