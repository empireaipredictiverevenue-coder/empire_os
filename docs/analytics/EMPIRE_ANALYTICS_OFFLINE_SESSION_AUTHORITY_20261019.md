# Empire Analytics — Offline session authority and consent lifecycle

19 October 2026 | Continuation wave 3 | Source ready, production held

## Mission and existing ownership

This extends the existing Empire AI first-party analytics foundation,
not a replacement CRM/marketing API/database or a GA4 installation.
The official Empire AI branded private analytics dashboard is already
served by empire-founder-console.service, and the existing Search
Intelligence API provides genuine GSC search-performance observations.
Do not conflate search clicks with first-party website visits.

The already committed source includes:
- empire_os/analytics/first_party_event_contract.py
- empire_os/analytics/dormant_event_ingress.py
- empire_os/analytics/measurement_readiness.py
- existing EmpireOS Tag Intelligence monitoring and gateway rate limiter

The historical consent_api.py is for prospect communications
(email, SMS, voice and A2A), NOT analytics/website session consent.
Do not reuse opt-ins for tracking. The existing Avatar Presence
token HMAC design is a reference for future purpose-specific signed
authority but is not reused as a visitor token.

## What this wave BUILT

1. empire_os/analytics/offline_session_authority.py
   - In-memory ONLY prototype guarded by an explicit
     enable_offline_simulation=True flag.
   - Random 128-bit opaque simulated session nonce.
   - Exact approved empire-ai.co.uk origin.
   - 30-minute bounded lifetime and strict UTC clock validation.
   - Bounded 500-session process-memory capacity.
   - Consent starts UNKNOWN, cannot pass the event contract without
     separate, trusted SERVER-SIDE grant action.
   - Terminal revoke, expiry and erase deny subsequent intake; a
     revoked session may not silently opt back in. New consent requires
     a new session.
   - Purpose-specific draft policy version. Policy drift cannot be
     accepted as a valid consent grant.
   - Server-resolved acquisition category constrained to known
     channels and provenance categories. Browser-provided UTM/referrer
     claims are still rejected by the existing event schema.
   - Never exports per-session data from readiness(), and it does
     not store the simulated events or set any cookie.
   - It is not an enduring store, verified legal consent decision,
     identity token, secure public authorization or production API.

2. tests/analytics/test_offline_session_authority_20261019.py
   - Deny-default, explicit server authority, grant, deny, revoke,
     erase, 30-minute timeout, UTC rollback, policy mismatch, channel
     mismatch, site origin, capacity, concurrent nonce uniqueness,
     no database, no visitor/revenue claims or PII leaks.

3. tests/analytics/test_session_to_ingress_bridge_20261019.py
   - Full offline chain through FastAPI TestClient and the EXISTING
     dormant ingress factory: session -> simulated trusted consent ->
     event schema -> server source -> local-only simulated aggregate ->
     revoke -> next HTTP event fails.
   - No actual public endpoint is mounted on production services.

4. scripts/review_analytics_session_authority_20261019.py
   - --read-only runs only synthetic in-memory lifecycle, returns
     boolean proofs/status and explicit negative production authority
     claims. It returns no visitor/event counts, per-user paths or IDs.
   - The report may include the most recent existing Tag Intelligence
     static snapshot status, which is still not traffic/consent proof.

## Execute safe operator

    cd /srv/empire_os
    ./.venv/bin/python -m scripts.review_analytics_session_authority_20261019 --read-only

Expected status:
    OFFLINE_SESSION_CONSENT_AND_HTTP_CONTRACT_VERIFIED

It means the synthetic contract passes, NOT that any real site user,
consent, visitor session, CTA or conversion has been measured.

## Necessary next implementation waves

- ASTRA/public website owner reviews a consent-management UX with
  jurisdictional lawful-basis/withdrawal requirements.
- Design cryptographically authenticated, purpose-specific server
  consent issuance; grant acceptance MUST be tied to a real trusted
  site interaction and versioned policy, not merely caller passing a
  trusted_server_decision=True argument from a public endpoint.
- Implement EmpireDB transactional, owner-/property-/tenant-scoped
  decision history with durable revoke and consent source. **Do not
  use Supabase or create a parallel session database.**
- Implement server-signed short-lived pseudonymous session receipt
  with rotation, rate/abuse controls and erasure/retention. The
  offline random nonce in this prototype is NOT a credential.
- Independently resolve acquisition attribution based on trusted
  server-side campaign/link evidence; guard header spoofing and
  unknown source. Do not blindly classify direct from missing UTM.
- Persist event IDs with cross-REQUEST replay protection. Existing
  event validator only de-duplicates within an individual batch.
- Activate exact owned public route / consent UI under separate
  founder and ASTRA release approvals. Allow analytics consent to
  be denied/revoked without blocking essential site usage.
- Verify the first real authorized event and an independent receipt
  before changing visitor/sessions/engagement fields from unknown.
- Bridge canonical customer enquiries / buyer / payment / fulfilment
  only with documented identifiers and tenant isolation. GSC,
  HTML events or attempted form submissions never prove revenue.

No tracking code, new systemd unit, timers, public route, CRM mutation,
financial activation, DB migration, site publishing, provider spending
or outbound mail is introduced in this wave.
