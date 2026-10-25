# Empire AI — Rapport → Value → Verified Buyer Signal → CTA

**25 October 2026 | first-revenue commercial workflow | explicit root-cause fix**

This is not a change in advice or copy style. It is a **default enforcement policy** to stop the original no-reply follow-up worker from silently reverting to an offer.

## Observed concrete bypass

The existing live hourly `empire-outbound-followup.timer` runs `scripts/run_outbound_followup_worker.py` → `empire_os/outbound_followup_worker.py` → `empire_os/conversation_value.py:build_followup_copy`. Before this patch the function unconditionally called `_entry_offer_for_followup`, selecting a **$199 gap, $249 map or $1,500 pilot** on review counts, scores or ad observations — even when there was no verified inbound buyer reply. Step 2 explicitly urged an offer/CTA by default. The legacy message path was inconsistent with the existing `rapport_first_human_specific_v1` rules and `rapport_intent_cta` intent reviewer.

## New hard restriction on this no-reply path

- **Pre-signal nurture is informational only**, and contains no price, product, checkout, meeting invitation or sales CTA — irrespective of company score, a pricing flag or a recommendation from a model.
- A follow-up must contain a **fresh (<30-day), time-bound public-source trigger with an evidence reference**. Generic ratings, lead scores, hypothetical research or a company name alone will not create an invented value touch.
- A second no-reply follow-up requires explicit evidence that its source reference differs from previously used references; missing prior reference tracking holds the candidate.
- The existing source and original opt-out statement remain in drafted messages. The original governed intent proposal and send stages remain independent.
- The outbound builder is a no-reply worker and cannot authenticate a buyer signal. Commercial CTAs must be proposed in the **separate existing authenticated buyer-reply review** and approved by the founder under canonical suppression and terms policies, not inferred from prospect scores.

This patch does not rewrite prior messages or invent customer replies. It does not activate live money, prospect sends or model weights.

## Important other channel still to govern

This change covers the concrete **no-reply follow-up** regression only. It **does not prove** that all other proposal generators, Gmail manual drafting, adaptive first-touch experiments or enterprise sales channels enforce the same rule. In particular, `empire_os/outreach_message_optimizer.py` and `gtm_pipeline_worker.py` include first-touch soft asks and adaptive variants; those require separately verified enforcement at their own final proposal boundary. Do not claim a global fix or presume this one code patch controls ChatGPT Gmail draft/send tools.

## Acceptance

Tests enforce zero pricing/offer/CTA even with extreme account scores, source required, replayed source held, stale/future source held, and opt-out retained. No remote recipient, bank, production PostgreSQL DDL or outbound network action is part of this change.

**First revenue remains the goal; rapport and useful evidence precede any sales ask.**
