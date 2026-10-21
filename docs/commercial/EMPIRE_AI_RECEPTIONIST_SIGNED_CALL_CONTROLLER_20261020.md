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
