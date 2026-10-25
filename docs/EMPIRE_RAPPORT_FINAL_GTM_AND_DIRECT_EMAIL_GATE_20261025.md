# Empire AI rapport-first governance: final proposal and manual email boundaries
**25 October 2026 | First-revenue build; original Smart CRM, EmpireDB, EmpireOS**

## Production defect removed

The previous no-reply follow-up regression was fixed in PR #108; however, the independent GTM standing-authority path used `optimise_first_touch` and optionally **adaptive subject/body experiments** which could still inject `Want me to send it?`, sales language or another CTA *after* a template-level fix. Meanwhile an operator using the Gmail plugin could author and send a priced pilot directly, without traversing EmpireOS's existing authenticated `rapport_intent_cta` reviewer.

**No unverified buyer reply shall yield commercial CTAs or prices at the first-touch proposal boundary.** This release adds a separate final payload gate to `gtm_pipeline_worker.build_outbound_payload`, after any optimizer/arm selection and before the proposal is submitted. It authors the actual final cold message from the canonical source-observation record, not by deleting sales words from an unrelated optimizer result. The existing adaptive selection may continue for internal research, but its suggested sales ask cannot reach the final outgoing payload. The message carries a source reference, observed public activity, a calibrated explanation (not a fabricated pain/buying-intent claim), the canonical postal signature and opt-out.

**Cold send rules:**
- Dated and non-future source event within the canonical freshness window, with a nonempty evidence reference, original tenant/recipient review and locale/optout rules. Generic ratings, high `buy_signal_score` or synthetic events are not a substitute for actual observed source evidence.
- The final message must contain **zero questions, priced offers, pilots, sales CTAs, checkout links or claims of readiness to buy**.
- Final code validates the exact body **after** adaptive selection; any prohibited message fails closed before proposal. Missing or inferred source is classified as a governed *defer* rather than a system failure.
- `final_message_gate` and `final_message_stage=RAPPORT_VALUE_NO_BUYER_SIGNAL` appear in the outgoing proposal metadata. Earlier copy optimizer metrics are separately marked **pre-boundary** and are not a review of the final delivered words. The copy fingerprint is computed after final authoring on the live advanced pipeline.

## Direct Gmail / manual writing review

`scripts/review_rapport_email_draft_20261025.py --read-only` takes exact JSON from stdin with subject, body and evidence_ref. It flags missing source evidence, price/pilot/offer/CTA, missing opt-out and hard-selling language, **without displaying the email**, looking up or sending to the recipient, storing a file, or touching EmpireDB.

A caller-supplied `verified_inbound_review` flag **cannot** create commercial authority: purchase/price CTA replies still require the original provider-authenticated same-thread counterparty evidence, canonical suppression, appropriate product/terms review and explicit founder send approval. No new sending service is created.

**Crucial limitation:** this review utility and EmpireOS code cannot intercept a person manually clicking Send in Gmail or a direct third-party Gmail plugin action. For that boundary, the active working procedure is to run and obey the review first and separately verify replies through `rapport_intent_cta`. Until there is an installed gateway/enforced Gmail send adapter, we must not claim the external Gmail button or connector is technologically blocked.

## Regression coverage

The tests exercise ordinary and adaptive GTM proposal finalisation, extreme prospect scores, forged `cta_allowed`, `price_allowed` and buyer-signal flags, stale/future/inferred/synthetic source events, promotional injected source summaries, direct manual-email pricing and CTA attempts (including the prior $600 Acolite pilot scenario), and read-only manual JSON review. Output never grants send authority. No marketing traffic, mailbox message, payment, live training, production schema or existing timer schedule is modified.

**Next: return to first-revenue build** — track genuine buyer replies, provide useful source-backed sample work, and make a scoped commercial proposal only after independently corroborated commercial interest and approval.
