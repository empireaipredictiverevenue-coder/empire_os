# Empire AI Receptionist — Signed Inbound Call Controller (20 October 2026)

This is the ongoing **AI receptionist** product, not database or backup work.

## New commercial/product capability

- A standalone, signed HTTP Vonage inbound POST answer adapter and speech/DTMF input adapter, built on the existing receptionist policy. It is **not registered with any production telephone route**.
- Provider destination number resolves one server-owned tenant through the existing InboundNumberRegistry; external tenant IDs cannot change the selected customer.
- First turn generates a Vonage NCCO with AI disclosure, business greeting and speech/keypad choices. Second and subsequent (max three) turns process appointments, callbacks, human requests, emergency handling and opt-out.
- Records no audio. Never invents a booked appointment, confirmed transfer or delivered callback. In this stage the policy engine is deterministic, not an LLM or live speech model.
- Strict signed callback verification using the existing Vonage JWT/verifier with raw body integrity. JTI replay is idempotent and contradictory reuse blocked; per-call sessions and replay caches are bounded and in process only. These caches are **not** suitable for production multiworker/restart safety.
- Scriptable synthetic end-to-end demonstration exercises two signed HTTP callbacks through the real FastAPI routes. No phone call or telecom provider charges.

## Run immediately (synthetic local, no external network)

    cd /home/ubuntu/empire_worktrees/inbound_revenue_recovery_20261020
    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.demo_ai_receptionist_call_20261020 --synthetic-only appointment

Other synthetic choices: callback, human, stop, unknown. The output deliberately shows booking/callback/contact/revenue as false, because no customer call, consented booking or CRM delivery happened.

## Source

- empire_os/inbound_reception_call_flow.py
- empire_os/inbound_reception_voice_api.py
- scripts/demo_ai_receptionist_call_20261020.py
- tests/test_inbound_reception_voice_flow.py
- tests/test_inbound_reception_voice_demo_cli.py

Vonage API requires POST answer_method and signed webhooks for this adapter, with an independent input event URL under a trusted HTTPS host. Vonage input action supports speech and DTMF with an eventUrl array (see https://developer.vonage.com/en/voice/voice-api/ncco-reference).

## Clear next work to make the product customer-ready

1. A proper approved real DID ownership record and signed Vonage POST answer/input with durable replay and session state (native tenant isolation, no Supabase).
2. A useful consent-driven multi-turn intake that creates human-reviewable appointment/callback requests in the existing CRM under approved identity, with privacy minimization, expiry, opt-outs, one-click follow-up and no fabricated confirmed appointment.
3. Business-approved FAQs, staffed hours, human transfer number and escalation policy for first consented pilot.
4. Real Google Calendar consented availability and booking receipts; no booking until independently confirmed.
5. Consent/recording legal review, latency/telephony throughput smoke test and owner-approved supervised live pilot.
6. SaaS pricing/billing/fulfilment and measurement only after buyer terms and real outcomes.

Existing production Voice Lab outbound and Lead Smart roofing call routing must not be modified. The separate calendar staging at loopback 8794 is not a live voice receptionist.

## 20 October — multi-turn appointment/callback capture, human CRM-review envelope

Building on the signed Vonage answer → input → response controller, the
receptionist now continues the conversation instead of ending after the
caller asks for an appointment or callback.

The isolated, synthetic-only conversation asks:
1. What service is needed? Accept only reviewed tenant services or an explicit
   general-enquiry category. Unknown requests are clarified, not guessed.
2. What broad time-of-day is preferred? Morning, afternoon, evening, anytime;
   the answer is a preference, not calendar availability or a booked date.
3. Explicitly ask permission: "May the business team contact you about this
   enquiry?" Accept an unambiguous yes/DTMF 1, or no/DTMF 2.
4. On yes, prepare one scoped in-memory CRMEnquiryDraft with stable id, tenant,
   provider call ID, enquiry type, approved service code, preferred window
   and explicit review consent. A no, privacy stop, emergency, human request
   or repeated unknown answer creates **no draft**.

Source: empire_os/inbound_reception_intake.py integrated into
empire_os/inbound_reception_call_flow.py, demonstrated using the signed HTTP
test adapter in scripts/demo_ai_receptionist_call_20261020.py.

The draft is **not submitted to EmpireDB CRM**. A later CRM owner must verify
its canonical tenant association, signed evidence, suppression, identity
authority, expiry and accepted customer terms before independently approving
an ingest. No caller phone number, raw ASR transcript, name or speech audio
is placed in the draft. No real customer contacted; no real appointments,
outbound calls, calendar bookings, SMS, billing or revenue. The existing
voice/Lead Smart live services were not modified.

Synthetic demo:

    cd /home/ubuntu/empire_worktrees/inbound_revenue_recovery_20261020
    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.demo_ai_receptionist_call_20261020 --synthetic-only appointment

Expected: PASS_SYNTHETIC_SIGNED_WEBHOOK_CONVERSATION, review_draft_created
true, review_draft_service roofing, review_draft_window morning and
crm_write_performed false.

## 21 October — receptionist-to-existing-RevenueLedger review bridge

`empire_os/inbound_reception_recovery_bridge.py` links a consented in-memory
`CRMEnquiryDraft` (same exact tenant/provider call) with the **existing**
`RecoveryLedger` and `build_inbound_recovery_scorecard`. This is a local
read-only projection, not a parallel missed-revenue engine or a canonical
CRM write. It rejects unsafe/forged drafts, deduplicates one enquiry per call,
filters other tenants and checks signed-provider-origin/status only when
the calling adapter declares authenticated source custody (not independently
attested inside this function).

The review distinguishes:
- one AI-answered call (not a missed call);
- provider-authenticated unresolved missed call (not recovered);
- contradictory answered + missed state (manual reconciliation);
- no authenticated disposition (unknown; synthetic test default).

It deliberately **never** promotes the draft to a canonical CRM prospect,
contacts the caller, confirms a booking, registers payment, or claims recovered
revenue. Calendar and financial receipts require their existing independent
owners/readers. With only synthetic receptionist callbacks, both the
missed-call count and recovered-revenue count stay zero.

The existing signed synthetic demo now shows:
`recovery_bridge_enquiry_count=1`,
`recovery_bridge_new_crm_prospects=0`,
`recovery_bridge_missed_calls=0`,
`recovery_bridge_verified_recovered_calls=0`.

Next genuine capability: replace the in-process review packet with an
authenticated, durable tenant-scoped receipt in the **already existing**
EmpireDB CRM; no arbitrary new CRM table, public endpoint or caller message.
Independent CRM membership/identity, consent/retention and signed Voice event
proof must pass before calling that step active.


## 21 October — existing Revenue CRM authenticated owner review (candidate)

The old blocker was NOT an absent CRM implementation. The canonical Revenue
CRM has a read-only, dedicated PostgreSQL tenant transport with tenant scope
verified via session_user and public.empire_current_tenant_id(). The
`public.prospects` view concerns canonical commercial prospects; an
unidentified caller's in-memory receptionist request must not be promoted
to that B2B pipeline or treated as a verified person.

New source:
- `empire_os/inbound_reception_crm_owner_review.py`
- `empire_os/inbound_reception_voice_api.py` now takes optional
  `resolve_authenticated_crm_read` and `crm_owner_review_enabled=False`
- `tests/test_inbound_reception_crm_owner_review.py`

An authorised, separately configured candidate service can expose
`GET /v1/inbound-reception/crm-review/enquiries` **only** if explicitly
enabled with the existing `build_authenticated_revenue_crm_resolver`
(or equivalently trusted existing signed CRM resolver). It expects
`AuthenticatedRevenueCrmRead` bound to a dedicated
`PostgresRevenueCrmRepository`. It invokes the original repository's
read-only `prospects(limit=1)` to require existing EmpireDB login
tenant authority: authenticated session_user, SET LOCAL ROLE, matching
`empire_current_tenant_id()` and tenant-scoped rows. A customer-supplied
tenant header/query cannot select records. The same call engine and lock
used by signed Voice webhooks provide the in-process enquiry snapshot,
which includes service code, time preference, explicit review consent and
status PENDING_HUMAN_REVIEW_NOT_SUBMITTED. No raw audio or speech transcript,
customer telephone number, name, outbound authority or payment.

**Default is off** and no existing public or live CRM route was modified.
The candidate is only useful in the same single-process runtime until
the native EmpireDB receipt store for voice sessions and consent is
independently approved and verified. It does NOT constitute durable
customer enquiries, a real CRM receipt, canonical prospect conversion,
any completed appointment or generated revenue. It creates no DB table,
no financial actions, no customer outbound and no job/timer.

The first actual production admission must be wired to an existing
approved CRM/inbound intake owner with idempotent canonical receipt,
tenant membership verification, evidence provenance, contact consent
retention/revocation, operator attribution and readback. Until then
`canonical_crm_receipts=0` and `durable_queue_verified=false`.


## 21 October — restart-persistent *offline* receptionist enquiry receipt (not EmpireDB CRM)

The previously delivered signed Voice call engine and existing
\`OfflineRecoveryStore\` now have a narrow opt-in persistence bridge for
**dark/synthetic staging only**. We did not create another canonical database
or replace the native EmpireDB customer/CRM authority.

- The existing offline recovery SQLite store owns one additional
  \`offline_reception_enquiry_drafts\` local table. It stores only tenant ID,
  pseudonymous call ID, deterministic enquiry ID, appointment/callback type,
  an approved service code, broad time preference, explicit consent flag and
  pending review status — not ANI, caller name, email, speech/audio or notes.
- \`append_reception_draft_offline\` atomically inserts the first draft,
  returns False for identical retries and rejects contradictory same-tenant
  enquiry/call IDs. \`reception_drafts_for_tenant\` reads only that tenant and
  revalidates every reconstructed draft; it fails closed for absent/invalid
  or overflowing tables.
- \`InboundReceptionCallEngine(on_consented_draft=...)\` writes the local draft
  **before** acknowledging that it was prepared. On unavailable/read-only
  store the signed callback returns an error and leaves the consent step
  retryable rather than claiming an accepted enquiry.
- The opt-in owner-review HTTP app may use
  \`load_offline_drafts(verified_crm_tenant_id)\` to read this private local
  store through the **same existing canonical CRM tenant resolver**. This
  callback must acquire a fresh SQLite read-only connection per HTTP request;
  do not share a SQLite connection across TestClient/server threads.
  Unknown/untrusted/mismatched tenant results fail closed.
- A fresh application and a fresh read-only SQLite connection see the
  exact same persisted staging receipt. A different tenant does not.
  Synthetic signed webhook → explicit consent → local commit → new
  app → owner-only review is covered by
  \`test_same_existing_offline_store_survives_restart_and_crm_owner_can_read\`.

**Production boundary:** SQLite is not EmpireDB, the persisted staging item
is NOT a customer receipt accepted by canonical CRM, and the callback's
pending draft is not a prospect or verified revenue. A production
multiworker/restart-safe solution still needs native EmpireDB schema (057
is HELD/UNAPPLIED), a separately approved least-privilege write policy, a
signed event/call replay store, proper retention/erasure and private owner
readback. Neither the new local table nor the test app is installed as a
production web service. No phone route, canonical database, Calendar grant,
customer message or payment was activated.

The product next action is to implement and independently verify the
canonical approved native CRM/inbound receipt admission with identity,
revocation and operational delivery; only then run a supervised customer
phone-call-to-enquiry demonstration.
