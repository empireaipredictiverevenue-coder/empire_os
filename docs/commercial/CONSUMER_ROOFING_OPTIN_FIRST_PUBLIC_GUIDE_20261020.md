# Empire AI consumer opt-in programme — Roofing Cost Guide

20 October 2026. **Built and tested in an isolated worktree, not published; consumer email collection disabled.**

## First useful deliverable

The new /roofing/cost-guide page offers a real, printable five-step homeowner checklist: problem description; written scope; roofing quote cost factors; licensing, insurance and warranties; comparing like-for-like bids. This is general education, not a contractor quote, case study or price guarantee.

A separate, *optional* Empire AI homeowner newsletter form is coded but deliberately fail-closed: it renders only if a first-party `GET /v1/consumer-optin/roofing/status` endpoint returns a signed-off policy-shaped response including:

- `status=OPTIN_COLLECTION_ENABLED`
- `notice_version=roofing-homeowner-updates-v1`
- `subscription_product=EMPIRE_AI_OWN_BRAND_HOMEOWNER_UPDATES`
- `privacy_notice_url=/privacy`

**No such status endpoint has been deployed.** The existing business/agency commercial enquiry RPC and legacy SQLite lead-intake path are not used for homeowner newsletter email addresses. Guide download is ungated; there is never a requirement to agree to marketing or contractor sharing.

The proposed own-brand POST contract, also not deployed, is `POST /v1/consumer-optin/roofing` with explicit unchecked optional-brand checkbox, original notice version and a `optional_named_buyer_referral=false` assertion. The UI only reports an opt-in success if a separate trusted API genuinely returns `OPTIN_RECORDED_PENDING_VERIFICATION`; it does not claim email delivery or add anyone to a marketing list.

## Release and verification

Isolated source worktree: `/home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020`, branch `feature/consumer-optin-roofing-20261020`.

Isolated static Webpack build: `/home/ubuntu/empire_staging/consumer_optin_roofing_20261020`. Next.js 16.3.5 compiled successfully, TypeScript passed and 20 pages exported, including `roofing/cost-guide.html`. Build ID `l-spB9zu77TJH808k5gaj`; page SHA-256 `6a66993cb9e73c22fd95b154169eba71480120f05ca61268976788a8cdb95031`.

Asset collision inspection: 42 staged static assets; 11 existing live asset paths match byte-for-byte, **zero** existing-path conflicts, and 31 assets are new unique hashes. This does **not** independently authorise a public upload.

A local real Chromium test of the isolated build confirmed all five guide cards, absence of subscriber forms when readiness GET returned 404, no synthetic POST, and only GET/HEAD browser requests. An initial smoke mistook HEAD for a write; this was diagnosed and corrected by logging HTTP methods.

**Existing source-owner content control remains enforced**: `public_gateway.py` is amended in the isolated branch to recognise the exact new roofing guide slug via its original `_STATIC_REVIEWED_ROUTES` and `public_roofing_guide` rules. Without the founder/editorial/privacy/approved-page-hash receipt, `GET /roofing/cost-guide` returns noindex 404. The production route currently returns HTTP 404. No production gateway, static site, buyer campaign or CRM service was changed.

## Actual remaining activation work, existing owners only

1. **Website/Editorial/Lead Smart owner:** review the exact wording, source neutrality, no unsubstantiated local prices, roofing coverage distinction and route metadata. Align the homeowner guide with the existing exact SHA reviewed-content release process and current flagship assets; preserve other owner changes. The current gateway's reviewed guide lane intentionally emits noindex and requires buyer/legal approval before public publication.
2. **Privacy/Legal owner:** establish and publicly review the privacy notice applicable to individual consumers, its retention, age/sensitive-data exclusions, unsubscribes, consumer deletion and any identity verification required. Do not assume the general /privacy page covers every new marketing purpose without review.
3. **EmpireDB/CRM owner:** use a dedicated consumer subscription consent store, not the B2B company prospects schema or legacy SQLite. Store the immutable original notice/checkbox evidence with restricted access and dedupe, correction, withdrawal and suppression. **Do not apply a migration without separate database activation approval**. Do not mix subscriber counts into saleable buyer leads.
4. **Email/Subscriber owner:** confirm sender authentication, email verification where selected, actual unsubscribe workflow, delivery receipts, suppression and sane anti-abuse rate limiting.
5. **Buyer Exchange/Sales owner:** a separate named-receiver and channel-specific agreement is needed to transfer any identified consumer to a roofing buyer. Guide download/own-brand subscription do not confer those rights. Buyer pricing, self-qualification, returns and fulfilment require independently agreed terms.

`empire_os/roofing_guide_optin_contract.py` provides a PII-free original-consent receipt reviewer and an activation evidence checklist; it never independently authorises a release, writes a database row or sends email.

## Acceptance commands

```bash
cd /home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_roofing_guide_optin_contract_20261020.py \
  tests/test_roofing_cost_guide_reviewed_release_20261020.py \
  tests/test_lead_smart_legal_review_copy_guard.py
```

**Commercial truth:** we have a complete informational lead magnet and an optional opt-in *interface*, but **no live email capture, subscribers, independent consent approval, buyer contact transfer, qualified lead or customer revenue**.


## 20 October continuation — staged subscriber DB + closed API

A **second additive implementation commit** adds original-purpose subscriber infrastructure without touching production:

- `migrations/empiredb/057_consumer_roofing_optin_staged_20261020.sql`: staged-only EmpireDB migration. It creates a dedicated single-purpose encrypted subscriber record, append-only consent history and keyed-HMAC suppression tombstones. It rejects unsafe database names, requires the existing restricted migrator role, enables and **forces RLS**, has **no policies and no runtime grants**, and cannot be automatically called by boot/deploy. Emails are represented as encrypted bytea with a private key reference; keyed lookup digests are never a substitute for legal consent. The migration was **not run**, even inside a rolled-back transaction, against production.
- `empire_os/roofing_guide_optin_api.py`: first-party GET readiness, POST optional own-brand opt-in, and POST opaque-token unsubscribe. It is mounted in the *isolated* `public_gateway.py` branch with **no private backend**, so live or test GET/POSTs return controlled 503 until a real privately configured service is approved. The POST requires same-origin, strict JSON, size caps, bounded syntax, the right original version and true brand opt-in. It rejects referral consent claims, honeypot fields, unrecognised payload keys and bot/rate abuse. It never sends email or returns the submitted address in responses.
- `tests/test_roofing_optin_api_and_storage_20261020.py`: real gateway fail-closed tests plus simulated private-backend signup, withdrawal and denial tests. These use only `.example.test` synthetic addresses in memory, without real email or DB calls. Any real withdrawal service must recognise purpose-scoped unpredictable unsubscribe tokens, record suppressions before future mail, and never expose person existence.

**Whole public-gateway regression passed: 66 tests** (one third-party Starlette deprecation warning). The protected guide release and other existing gateway flows remain intact.

### Production check, no writes

Original privileged read-only EmpireDB object inventory confirmed:
- `public.empire_consumer_subscriptions`: ABSENT
- `public.empire_consumer_consent_events`: ABSENT
- `public.empire_consumer_email_suppressions`: ABSENT

The live `https://empire-ai.co.uk/v1/consumer-optin/roofing/status` currently returns 404, because the new disabled routes were **not deployed to production**. The guide URL also remains 404, pending its independent exact-content and privacy release. Neither a live mailing list nor an unsubscribe endpoint has been claimed.

### Activation order (independent owners)

1. **Privacy/Legal + Founder:** review own-brand marketing purpose, named sender, exact unbundled checkbox, privacy notice and retention; independently approve a subscriber withdrawal/deletion route, including treatment of suppression tombstones. A guide download must stay free without an email.
2. **DBA:** review new SQL against present production migrations, verify a backup and ownership, then obtain **separate explicit privileged migration approval** before applying. After secure cipher/HMAC custody is designed, create minimal dedicated private-service roles and narrow RLS functions. Do not grant all access to `empiredb_app`, the public gateway, or B2B CRM.
3. **Subscriber service + Email owner:** build isolated authenticated private adapter, real double-opt-in or appropriate verification, actual provider receipts, consent/suppression/erasure and anti-abuse rate limiting. Configure sender domain, bounce handling, audits and unsubscribe. Implement purpose-scoped no-existence-leak token withdrawal. Synthetic approval flags cannot substitute for real transport readback.
4. **Website owner:** merge the guide against the **current** flagship assets, capture a byte-pinned reviewed-content release that includes independent homeowner/editorial/legal approvals, and smoke the public page while the opt-in status remains held. Do not overwrite active premium brokerage, existing roofing campaign or public product conversion fixes.
5. **Activation and measurement:** once first-party storage, privacy and sender verification are independently proven, connect the private backend and enable readiness. Verify the first genuine opt-in, receipt, cancellation and suppression safely; report **subscribers and confirmed enquiries separately**, and never count a newsletter subscriber as an Exchange buyer-referral lead.

**Current authority:** private build/test only. No production DB mutation, buyer contact disclosure, live email subscription, outbound mail or payment.


## 20 October continuation — purpose-bound confirmation and unsubscribe flow

A third additive source release implements the missing email preference **interaction** and purpose-specific token verification contract. This is **not** an activated emailing backend.

- `empire_os/consumer_optin_token_security.py`: cryptographically random 256-bit URL-safe tokens, separate HMAC keys/contexts for email lookup and confirmation/withdrawal tokens, enforced confirmation and withdrawal TTL, expiry/replay/suppression/purpose checks. Never stores the raw token in the database. It is pure domain logic; a live owner must implement atomic DB token consumption under row locks.
- `empire_os/roofing_guide_optin_api.py`: added POST-only confirmation endpoint. Neither following an email link nor loading a page can confirm a subscription. Signups, confirmations and withdrawals now have **independent** readiness controls; unsubscribing can continue if new signup delivery is paused.
- `apps/empire-public-site/src/app/roofing/email-preferences/page.tsx`: high-contrast customer preference page with explicit user-click confirmation/unsubscribe. Confirmation and withdrawal links use a URL fragment, not an HTTP-visible query; the fragment is cleared on page load. The code never puts tokens in analytics, localStorage, sessionStorage or person-readable responses. Invalid or missing tokens cannot enable a form. It handles another email link opening in an existing tab without automatic submission.
- `apps/empire-public-site/src/app/roofing/email-preferences/layout.tsx`: noindex metadata. The route is added to the original reviewed-page policy but remains **closed** until genuine editorial/privacy and exact-content publication receipts exist. The email preference path must remain accessible once subscribers exist, even when signups pause.
- `migrations/empiredb/057_consumer_roofing_optin_staged_20261020.sql`: added restricted one-time token custody with expiry and consumed state. Added an erasure path that requires clearing encrypted email bytes and key reference when permission state becomes `erased`. The initial migration is still **STAGED ONLY, UNAPPLIED**, has forced RLS and no runtime grants; an authenticated private repository with transactional state transitions is not yet implemented.

Rebuilt isolated production export ID `xCFk8qtjhEYecz7QRRlCY`, Next.js 16.3.5, TypeScript passed, 21 static pages. SHA256 guide page `ccd323a3e06fd297415494bcaf93f9245464b0f1aa841d7ff00b7f6112a6f8f2`; preferences page `4c9a235a790a587bb465ce5ebe4d47417f35b1facc00e9ea2218f39a94dd1dd8`. No existing static asset path hashes conflict with published content; 34 hashed assets are new.

A real headless Chromium test of **the isolated static export** verified that an unsubscribe link reveals only a user-initiated action and clears its fragment; an attempted POST is blocked by the local fixture, with zero persistence; then a separate confirmation link in the same browser tab also requires an explicit click. The entire relevant HTTP gateway / consent / token / website review suite passed **79 tests**, with only the existing Starlette third-party deprecation warning.

Original production readback still: `/roofing/cost-guide` HTTP 404; `/roofing/email-preferences` HTTP 404; `/v1/consumer-optin/roofing/status` HTTP 404; existing `/roofing` HTTP 200. The original live roofing campaign, gateway and database were **not** modified.

**Remaining practical implementation to activate, in existing owner order:** approved legal privacy/recipient purpose and content; approved DBA migration to a separate private consumer store; transactional encrypted email/token/suppression backend; verified private email delivery and unsubscribe service including real provider receipts; exact-content reviewed public guide and preferences release; then a strictly scoped live opt-in pilot with one consenting real person and independently checked withdrawal. Do not claim a customer subscriber, CRM lead, shared consumer contact or realised revenue before those receipts exist. The website's readiness GET must stay held until all relevant controls are complete.


## 20 October — private subscriber runtime and real-Postgres fixture

**Fourth isolated branch release.** The missing private subscriber implementation is now coded, not just an interface. It has not been wired into the live system.

- `empire_os/consumer_optin_private_service.py`: genuine AES-256-GCM authenticated encryption for private email bytes, independently keyed lookup and token HMACs, source+notice-scoped per-request evidence digests, cryptographic 256-bit confirmation and unsubscribe tokens, guarded verification-email initiation, explicit provider-acceptance receipt custody and confirmation/withdrawal operations. It has **no default network/database/provider connector**, no environment-variable activation or public buyer-sharing authority. The private sender is an injected protocol, not a production mail transport.
- `empire_os/consumer_optin_postgres_repository.py`: real parameterised PostgreSQL transaction adapter, with per-contact advisory locks, suppression checks, restricted pending subscriptions, immutable consent events, one-time token issue and expiry, pre-email suppression recheck and send claim, provider receipt attestation, original confirmation evidence, atomic unsubscribe and full token invalidation. Its `approved_custody` defaults to false; it still requires a separately reviewed narrow production role and row-level security policy before any deployment.
- `empire_os/consumer_optin_confirmation_email.py`: no-tracking first-party confirmation email and unsubscribe wording, with strict first-party confirmation/withdrawal URLs and **send_authorized=false**; formatting a message cannot trigger an email.
- Migration 057 staged schema now also includes a forced-RLS provider-delivery receipt and per-token `send_claimed_at`. No public or application grants are issued. The original-consent digest is distinct for each browser request rather than a repeat of identical static checkbox text.

### Stronger evidence: actual disposable PostgreSQL lifecycle

A reproducible, **fully isolated** PostgreSQL 18 cluster smoke is provided by `scripts/run_consumer_optin_ephemeral_db_probe_20261020.sh` and `scripts/probe_consumer_optin_ephemeral_db_20261020.py`. It creates `empire_consumer_optin_fixture` inside `pg_virtualenv`, adds test-only narrow RLS policies, executes the staging migration, and tears the cluster down automatically. It **does not connect to production EmpireDB**. The test uses a synthetic `.example.test` address, fixture-only encryption keys and a fake provider acceptance receipt. The exact executed scenario passes:

- 5 consumer tables, all FORCE RLS; no access for PUBLIC, zero default policies, one append-only trigger
- encrypted pending subscription with two one-use bearer-token HMACs
- a fresh suppression-safe confirmation send claim and a **synthetic provider acceptance**
- verified state only after the token and provider receipt match
- token replay blocked
- unsubscribe, real DB suppression tombstone and original consent event appended
- all outstanding tokens invalidated; repeating signup for suppressed person refused
- exactly three append-only consent events; attempts to UPDATE a consent event rejected by PostgreSQL
- no original personal email in storage, zero real messages sent and no production database mutation

The full selected unit, browser reviewed-content and public-gateway regression suite passed **112 tests** (one benign upstream Starlette deprecation warning). The SQL transaction tests are supported by the real throwaway Postgres fixture, not just mocked queries.

### Production boundary remaining

No production migration has been applied. The public guide, preference and opt-in routes are still unreleased. Nothing in this private code supplies real operator-approved encryption/HMAC key custody, narrow production writer privileges or source-rights/privacy review. It also has no actual sender provider (the synthetic sender is fixture-only) or provider delivery logs. Independent safeguards still need working real delivery, unsubscribe/bounce processing and observed receipts before connecting it to the public gateway.

To verify fully without affecting production:

```bash
cd /home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020
./scripts/run_consumer_optin_ephemeral_db_probe_20261020.sh
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
 tests/test_consumer_optin_postgres_repository_20261020.py \
 tests/test_consumer_optin_private_backend_20261020.py \
 tests/test_consumer_optin_confirmation_email_20261020.py
```

This backend intentionally does not treat list subscriptions as buyer-referral consent or generate Lead Exchange inventory. The Exchange still requires an independently consented named-buyer request before any person can be transferred.
