# EmpireOS — cross-department automation and content hooks

**17 October 2026 | Existing 14 departments and 48 Control Fabric components | No new infrastructure**

## What we mean by hooks

**Operational hooks** are triggers when a real event requires an existing department to review or prepare the next step, including SEO gaps, enquiries, buyer replies, email suppressions, content drafts, quality failures, commercial outcomes and system incidents.

**Attention/content hooks** are truthful opening angles in titles, introductions, narration, email subjects, ads, social posts, sales proposals and website CTAs. They attract the right audience, but they cannot substitute for facts, helpful content, correct targeting, verified buyer signals or consent.

Use the existing Control Fabric registry, Marketing & Growth department, Search Intelligence, Keyword Universe, Revenue CRM, Media OS, Revenue Pulse, Operations, model router and department-cycle timer. **Do not introduce another event bus, NATS/Temporal/n8n/Zapier platform, scheduler, database or supervisor agent.**

## Existing route examples

| Department / purpose | Existing event | Existing owner | Review action |
|---|---|---|---|
| SEO/AEO/GEO | organic_gap_observed | search_intelligence | Evidence-linked keyword/content gap |
| Market research | search_gap_detected | search_fabric | Confirm competitor opportunity |
| Multi-channel repurposing | search_opportunity_ready | media_os | Adapt useful research to media |
| Newsletter/content briefs | campaign_brief_ready | demand_genesis | Compare truthful subject/CTA hooks |
| YouTube improvement | youtube_observation_ingested | media_os | Review actual retention and opening |
| Social questions | media_comment_observed | media_os | Respond to observed problems |
| Conversion optimisation | funnel_change_observed | conversion_intelligence | Review CTA/form friction |
| New prospects | prospect_ingested | revenue_pulse | Check real first-party prospect evidence |
| Buyer email replies | buyer_reply_received | buyer_reply_operations_agent | Buying signals, objections, STOP |
| Email deliverability | provider_delivery_event_observed | deliverability_sender_reputation_agent | Bounces, complaint, suppression |
| CRM segment reviews | customer_state_refresh_requested | revenue_crm | Segment hypothesis, not marketing consent |
| Partnerships | partner_research_requested | strategic_partnerships | Relevant, evidence-based draft |
| Buyer acceptance | buyer_capacity_refresh_requested | buyer_capacity_readiness | Capacity and buyer-route proof |
| Product economics | margin_evidence_required | commercial_product_catalog | Scope and margin review |
| Model calibration | calibration_review_requested | quant_brain | Predicted vs observed performance |
| Outbound safety | outbound_intent_proposed | outbound_governor | Sender, suppression, consent, approval |
| Customer delivery | fulfilment_completed | revenue_pulse | Verify fulfilment evidence |
| Verified commercial events | payment_verified, revenue_recognized | revenue_pulse | Economic memory, not estimated revenue |
| Service reliability | service_degraded | ops_sentinel | Incident review |
| Founder finance decisions | capital_review_requested | capital_allocator | Explicit financial approval |

The machine-readable catalogue has **34 review hooks covering all 14 departments**: 30 currently match existing Control Fabric event-to-component routes, four do not. A route is a static *candidate*, not proof that an upstream event is actively produced or that it is safe to execute.

## First real evidence replay and existing department cycle

The new read-only revenue-first replay uses the existing loopback Search Intelligence summary, Search Console daily observations, conversion and reply snapshots, Revenue Pulse, and optional four first-party website GET requests. It does not call a model or emit events.

The existing department-cycle source now includes a passive revenue_first_hook_review summary, without another timer. This is committed only to the isolated feature branch until coordinated source promotion; the live production timer has not been changed.

Actual evidence on 17 October: 4 priority reviews; GSC 5 daily rows / 15 impressions / 0 clicks over 10-16 October, but zero Search Intelligence repository opportunities or indexed-page records; conversion 52 delivered-to-reply stage entries, 0 recorded transitions; canonical reply collector 0 canonical messages proven in that observer; Revenue Pulse recognized revenue 0. A zero in one observer is not a statement about the whole business. See docs/architecture/REVENUE_FIRST_HOOK_EVIDENCE_20261017.md.

## Four genuine UNWIRED trigger gaps

1. newsletter_subscription_confirmed — no canonical verified marketing-purpose consent/confirmation handoff. Current Resend newsletters are drafts and CRM segments are review-only.
2. owned_article_live_verified — no verified publication-to-Google/Search Intelligence handoff for this exact event. Publishing is not indexing.
3. media_draft_ready — no current Control Fabric consumer for this exact event. Reuse existing Media OS workflows, not a duplicate publisher.
4. email_opt_out_verified — canonical verified unsubscribe / STOP event needs bridging to existing suppression readers; do not introduce a second suppression database.

These remain **UNWIRED_NO_EXECUTION**. Do not silently activate them by writing an event name into configuration.

## Ten content-hook lenses

Pain; proof; outcome; question; contrast; mistake; timely; reassurance; curiosity; accurate call-to-action.

Use them as editorial drafting tools across **SEO article, SEO title, landing page, newsletter, video script, social post, sales deck and partner outreach**. Example review angles:

- Commercial roofing SEO: “How do you tell a genuine roofing project from an unqualified enquiry?”
- US dental: “Which appointment qualification signals are worth paying for?”
- Predictive Revenue: “Which assumption should you verify before forecasting pipeline growth?”
- Newsletter: “Five checks before you publish another SEO page.”
- Founder-narrated YouTube: “Can your AI system prove that the opportunity became revenue?”
- Partner email: “What qualification evidence would make your client referrals more valuable?”

Use relevant query terms in the actual SEO title, and accurately answer the question in the article. Do not manufacture results, reviews, Google rankings, testimonials, buyer intent or urgent deadlines.

## Model hooks — where Ling 3.1 Flash belongs

Ling is **only an unactivated candidate** for deeper interpretation of verified research, competitor comparison, semantic gaps and higher-value content brief generation. The existing EmpireOS model router and LLM gateway already provide selection/adapters. Benchmark against current low-cost models on anonymised UK roofing, US dental and enterprise examples. Verify provider availability, current cost, usage limits and factual quality first; do not send private CRM or buyer email bodies to hosted inference. No automatic API charges were created by this work.

## Hook safety contract

Observed signal → canonical source reference → existing Control Fabric route → existing department → reviewable recommendation/draft → existing quality/consent/founder gate → independently verified action/outcome → actual Search Intelligence / CRM / Economic Memory observation.

No hook may itself expand another subsystem's permission. A supplied evidence reference is not automatically verified; idempotency must be enforced by the canonical action service, not merely a local review fingerprint. Unknown status is not zero performance. Explicit STOP, bounced recipients, missing mailing consent, missing routing acceptance and unverified revenue are all reasons to hold.

EmpireDB is canonical. Older Search Intelligence material mentioning Supabase is stale and should not drive new implementation.

## Priorities

**P0 revenue:** buyer reply prioritisation, live website enquiry bottlenecks, actual search opportunities, buyer acceptance and consent/suppression. This supports the first genuine commercial conversation.

**P1 consent and media continuity:** wire the four missing event connections only after verifying exact data source/provenance and existing owner, with no new scheduler or infrastructure. Keep marketing subscription separate from general business enquiry.

**P2 content quality:** compare three genuine audience hooks for each approved SEO page/video/newsletter; rank usefulness, truthfulness and qualified enquiry value, not clickbait CTR.

**P3 operational assurance:** service health, calibration, delivery, verified revenue outcomes and finance gates.

## Delivered in this change

- Pure offline cross-department coverage review in empire_os/cross_department_hook_review.py; no network, queue, model inference, CRM writes or dispatch.
- A read-only JSON reviewer in scripts/review_cross_department_hooks.py.
- Ten editorial lenses and eight draft-only channel types.
- Regression tests for every existing Control Fabric route, all 14 departments, four unwired triggers, refusal of money/outbound side effects, missing evidence and PII-free preview output.
- No production services restarted, mail delivered, page published, funds transferred or model credits used.

The next operational step is to replay a bounded set of *real observed* SEO, site-conversion, buyer-reply and opt-in evidence through this review surface, and only then connect an existing draft-only department task after separate source/permission verification.


## Production promotion checkpoint — 17 October

The scoped 34-hook catalogue and revenue-first review were promoted to the canonical existing EmpireOS department cycle in commit 86b41e46. The timer ran successfully, displaying four passive review candidates with zero dispatch, model invocation, outbound or payments. A further read-only comparison of Founder Mailbox records and actual Gmail source scope prevents a canonical-reply zero from being confused with absence of real email conversations. See the Buyer Reply and SEO Evidence Reconciliation document for source and commercial details.
