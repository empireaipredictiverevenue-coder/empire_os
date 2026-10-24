# EmpireOS PRIME — Expressed Emotions, Objection Handling & Response Learning

Date: 24 October 2026
Status: Original EmpireOS Predictive Cloud research worktree / OBSERVE only / production unchanged

## Founder objective and guardrail

Help the original Conversation OS, Buyer Acquisition, ASTRA and Smart CRM understand the **needs, concerns and wording the person voluntarily expresses** in a genuine inbound business conversation. Advise the human closer about respectful, accurate next steps. Over time assess **which truthful explanations actually answer customers' questions**, without inventing purchase intent or presuming the system can know someone's internal mental state.

**Never claim to know a person better than they know themselves.** No hidden psychological traits, vulnerability-based targeting, coercion, deception detection, manipulation, automated persuasion, person-level emotion scores, emotion diagnosis, medical/financial vulnerability inference, pressure sequences, autonomous outbound, or data sale.

## Implemented in the original repository

1. `empire_os/prime_conversation_objection_shadow.py` reuses the original `rapport_intent_cta._preflight` person/thread-bound verified reply shape and `_buyer_text` quoted-history filter. Classification is confined to one bounded, current (30-day) inbound message **after caller-declared source processing rights review**. Neither a caller's flags nor the pure classification establishes independent provider authentication or source licence.
2. Eight observable objection/concern classes: price/budget, trust/proof, timing/capacity, decision authority, scope/fit, integration/implementation, privacy/compliance, attribution/delivery.
3. Four **explicitly expressed language classes**, not inferred feelings: self-stated frustration/disappointment; self-stated worry/concern; self-stated confusion; explicit thanks/appreciation. No emotion inferred from a person's apparent silence, reply speed, punctuation or writing style.
4. Explicit opt-out takes precedence over every other signal; explicit refusal separately forces human suppression review, not renewed persuasion. Both stop reply advice. The actual durable suppression update still belongs to the original suppression owner.
5. An evidence-bound human guidance code: e.g. answer the exact verified price/scope question, refer to approved compliance documentation, separate routing/technical claims from paid calls, or respect timing and ask whether a future reply is welcome. No invented proof, service outcomes, capacity, commercial guarantees or automatic message composition.
6. Original `predictive_revenue_brain_bridge.py` accepts the optional `original_expressed_conversation_shadow` output and exposes a restricted `prime_expressed_conversation_objection_shadow`. Founder output contains **only categorical objections/status**, not raw personal text, email addresses, person/thread IDs or inferred/expressed private emotional labels.

## A prospective, privacy-minimised response-learning path

7. `empire_os/prime_conversation_response_learning_shadow.py` accepts bounded, original-owner-prepared, pseudonymous **observed outcome rows**: which humane answer approach a person actually received and what was subsequently observed: an answered question, another question, explicit decline, opt-out, or censored/pending. It requires internally consistent timestamps and excludes future outcomes, duplicates, replayed cases, transcript-bearing private data, unapproved processing purposes, unknown approach codes and fabricated conversion codes.
8. It reveals only aggregate group bands with at least ten independently distinct opaque cases per response approach; smaller groups and small outcome cells are suppressed. Pending/censored cases are never counted as success.
9. The existing PRIME bridge accepts `original_conversation_response_feedback_rows` and surfaces `prime_conversation_response_learning_shadow`. **No actual owner-fed outcome rows are connected at present.** This is a research contract and descriptive aggregation path, **not** live machine learning or an accuracy claim. It cannot attest the asserted original owner readback, prove causal uplift, promote model weights or authorise any message.

## Safeguards and owner release boundary

- The original owner must authorise email/transcript purpose, sender/tenant/person provenance, privacy/retention/erasure, lawful downstream use and consent before reviewing a real message; the pure API trusts none of those by itself.
- Source text is **untrusted input**, never an instruction to agents. Quoted history is ignored. Classifications are not personally identifying claims and are not stored automatically.
- The original suppression list is authority for STOP/no-contact, with manual owner review before any CRM status changes.
- Real improvements require prospective outcome measurements against independent source receipts, time splits, negative outcomes and an approved comparison policy; observational feedback is not proof one technique causes conversion.
- Original Chief of Staff / ASTRA / Conversation OS / Security / Data Cloud / EmpireDB owners approve merging and operation. No additional database, CRM, domain, mail agent or agent hierarchy has been created.

## Verification

The new modules use synthetic fixtures with no real personal messages and are integrated into the original PRIME research bridge. Focused tests include current reply/person binding, revoked purpose holds, quote exclusion, opt-out priority, misleading price language, forged authority, duplicate outcome records, causal timing, pending outcomes and small cohort suppression. 705 scoped regressions PASSED (one inherited Starlette/anyio deprecation warning) after integrating the existing PRIME bridge, original rapport/CTA contracts, Buyer Acquisition and Conversation OS, Quant, CRM auth and signed-owner evidence tests. This is not a whole-repository gauntlet. Safety fixes also explicitly prohibit an objection from becoming contact permission and prevent a no-reply policy from taking credit for a customer's question being answered.

**HOLD:** production source rights, canonical reply readback, outcome feed, verified behavioural improvements, automatic message sends, CRM mutation, payment, trading or model training.

One EmpireOS. One EmpireDB. One Smart CRM. One Predictive Cloud / PRIME.
