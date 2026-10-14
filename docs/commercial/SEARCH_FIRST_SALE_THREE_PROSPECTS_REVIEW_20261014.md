# Empire AI — Three evidence-led search product prospects, 14 October 2026

**State:** FOUNDER/OUTREACH-OWNER REVIEW ONLY — UNSENT. Not a CRM lead import, automated campaign, authorised recipient or forecast. Never use this research packet to bypass the other agent's one-to-one outbound control.

> **14 October rapport-first correction:** The previous offer-led first-touch drafts have been superseded. These introductions are for rapport, not conversion. Source-of-truth code: `empire_os/outbound_department.py`; existing-policy adapter: `scripts/review_search_first_sale_rapport.py`. A sent message, a marketing-email open, an unverified positive label or silence NEVER establish rapport or permit a product pitch. Once the buyer genuinely engages, respond to their actual topic. Only a verified, explicit product request may advance to human commercial review; there is still no autonomous send authority.

## Production products

- Technical Search Audit (`technical_search_audit`): USD 299 one-time, public `https://empire-ai.co.uk/buy`.
- Search Opportunity Map (`search_opportunity_map`): USD 249 one-time, same checkout.
- Claims must be scoped to deliverable evidence; no traffic uplift, rank, lead or conversion predictions.

## 1. Green Coast Roofing & Solar — prioritize first

**Domain:** `gogreencoast.com` (Naples/Southwest Florida)

**Named counterpart:** Brian Sujevich — owner/manager. The company's 4 October 2026 redesigned-site announcement explicitly lists Brian as media contact. Direct business-associated email **`brian@gogreencoast.com`** is corroborated in a published 2026 realtor directory; note that the directory also connects his email to real-estate activity. Use **only** after reconciling contact identity, permissible sales use, exact-address suppression and send authority.

**Sources:**
- Company-announced 4 October site relaunch: https://www.prweb.com/releases/green-coast-roofing-and-solar-marks-more-than-five-decades-of-family-owned-roofing-in-southwest-florida-302897553.html
- Public media-contact email (syndicated press release): https://www.nativo.ventures/2026/10/04/green-coast-roofing-and-solar-marks-more-than-five-decades-of-family-owned-roofing-in-southwest-florida/
- Independent named-address listing: https://www.pgpcnprealtors.com/member/brian-sujevich/
- Current site/contact: https://gogreencoast.com/contact/

**Trigger:** New website launched 4 October. Reason for written audit: confirm post-launch crawl/indexation, metadata/canonicals, roofing/solar service pages, quote-path instrumentation. No finding, broken tracking, migration loss or customer budget has been proved.

**Current governed stage: RAPPORT-FIRST / DRAFT REVIEW ONLY — source-backed greeting, NO commercial offer.**

To: brian@gogreencoast.com — public name/address research; canonical identity, suppression, consent, and sender gates NOT cleared.
Subject: Green Coast's website launch

Hi Brian,

I saw Green Coast Roofing & Solar announced its redesigned website this month. Bringing roofing and solar into one clear experience for customers looks like a substantial project. Thought it was worth recognising the work behind the launch.

Best,
Phil
Founder, Empire AI

**Policy proof:** existing `plan_outbound_account` returns `DRAFT_RAPPORT_TOUCH`; `review_outbound_draft` passes this text; `send_authorized=false`. There is no audit, price, booking invitation, checkout link or follow-up sequence in this introduction.

## 2. RoofElite — content quality hypothesis, NOT a proven current defect

**Domain:** `roof-elite.com` (Tampa Bay / Lutz, FL).

**Named counterpart:** Trey Gifford, owner/co-founder/COO. The site lists him, but NOT a personal verified email. `info@roof-elite.com` is publicly published as the **general/media inbox**, not a unique route to Trey. A 28 April 2026 company press release names Pamela Ames as media contact at that general inbox.

**Sources:**
- Current blog landing (opened 14 Oct, latest posts on-topic; archived posts not independently recovered): https://roof-elite.com/blog/
- Older crawled blog result (June indexed/cached off-topic titles, NOT proof they currently resolve or remain indexed): same blog URL, archive observation.
- Named owner: https://roof-elite.com/about-us/
- Company growth announcement/new 6,000 sq ft facility: https://www.globenewswire.com/news-release/2026/04/28/3283294/0/en/RoofElite-Expands-Tampa-Operations-With-New-6-000-sq-Ft-Facility-Strengthening-In-House-Capabilities-and-Capacity.html

**Trigger:** Website has expanded commercial-roofing content and an April operation expansion. Earlier crawler versions of the blog showed unrelated posts; new front page appears updated. First verify old URLs independently before claiming any defect. Buyer pain and rankings unknown.

**Current governed stage: RESEARCH / NO RECIPIENT / RAPPORT COPY ONLY.**

To: UNVERIFIED — do not infer Trey's personal email from the general `info@` inbox.
Subject: RoofElite's Tampa expansion

Hi Trey,

I saw RoofElite's update about expanding Tampa operations and bringing more work in-house. Supporting a growing team across commercial and residential roofing is quite a shift. Thought the expansion was worth acknowledging.

Best,
Phil
Founder, Empire AI

**Policy proof:** `RESEARCH` because current person-bound recipient evidence is missing and the April expansion is not fresh enough by itself. No offer, diagnosis or follow-up authorised.

## 3. Aastro Roofing — verified category expansion

**Domain:** `aastroroofing.com` (Deerfield Beach / Broward & Palm Beach, FL)

**Named counterpart:** Jason Blair, founder/president. Public company pages and 16 September 2026 company press release confirm role, but **no verified Jason-bound email** found. Press contacts offer a general phone/website, not explicit marketing-consent or an individual mail route. Email-first preferred; do not call or guess address.

**Sources:**
- Expansion announced 16 September 2026: https://www.prnewswire.com/news-releases/aastro-roofing-expands-into-full-service-general-contracting-offering-more-than-just-roofing-302880457.html
- Leadership page: https://aastroroofing.com/aastro-roofing-team/

**Trigger:** Added building/remodeling/painting/doors-windows/concrete restoration to roofing. Hypothesis: separate location/service intent map across Broward and Palm Beach; no visibility deficiency established.

**Current governed stage: RESEARCH / NO RECIPIENT / RAPPORT COPY ONLY.**

To: UNVERIFIED — Jason's verified, current personal business email is not established.
Subject: Aastro's wider service mix

Hi Jason,

I saw Aastro Roofing's announcement about adding general contracting alongside roofing. New types of projects bring different decisions for homeowners and property teams. It was interesting to see you broadening the work you take on.

Best,
Phil
Founder, Empire AI

**Policy proof:** `RESEARCH` until a correct person-bound route and canonical history are established. No Search Opportunity Map offer, price or meeting ask at first touch.

## Coded rapport-first control — outreach agent integration

- **Existing engine:** `empire_os.outbound_department.plan_outbound_account` and `review_outbound_draft`. There is NO new scheduler, database, CRM, or send provider.
- **Strict per-account switch:** `verified_reply_required_for_followup=True`. An unanswered first touch returns `WAIT`, not a second timed sequence. Unverified positive classifications return `WAIT`, not a commercial stage.
- **Genuine reply evidence for strict mode:** caller must establish `reply_id`, `provider_authenticated=True`, `same_thread_verified=True`, `counterpart_identity_verified=True` from the canonical original email thread; never fill these booleans from LLM sentiment or public website information.
- **Rapport escalation:** authenticated commercial reply → `CONVERSATION` human discovery and no price. Only an independently verified explicit request for the exact account `product_code` (`explicit_product_request_verified=True`, matching `requested_product_code`) → `COMMERCIAL_READY` human closer review. Even then, `execution_authority=none`; approval and send are independent.
- **First-touch copy guard:** `review_outbound_draft` rejects prices, product names, `we offer`, checkout links, calls/meeting CTAs, generic opener, fake familiarity and repeated/unsourced insight before authorised commercial interest.
- **Reproducible read-only preview:** `/srv/empire_os/.venv/bin/python -m scripts.review_search_first_sale_rapport`. Green Coast produces `DRAFT_RAPPORT_TOUCH` with eligible *copy* but `send_authorized=false`; RoofElite and Aastro produce `RESEARCH` until missing contact/freshness evidence is resolved.
- **Send-side integration ownership:** the **other outbound/mail agent** must invoke these existing planning and copy gates immediately before sending each exact prospect intent, then independently re-check canonical suppression, prior contact, mailbox identity, sender authorisation and founder approval. This code **has not been wired into or activated as a global send-adapter interceptor**, and an offline copy pass must never be labelled mail-send clearance.
- **No autopilot follow-ups:** if there is no authenticated incoming response, hold. If the buyer says no, later, unsubscribes, is OOO, or is not the right person, pause/suppress/research as appropriate; no looping.

## AI buying-intent detection → context-appropriate CTA (14 October upgrade)

**Existing architecture, no duplicate agent:** `empire_os/rapport_intent_cta.py` supplies a typed-intent adaptor to the **existing** `outbound_department.plan_outbound_account` and uses `empire_os.typed_decision_provider` (ASTRA/JEV/resident model if and when separately supplied and tested). The existing prospect review adapter `scripts/review_search_first_sale_rapport.py` exposes `intent_cta_review` only when original prospect and reply evidence has been supplied. It does not instantiate a model or read a live mailbox by itself.

| Evidence from the prospect's authenticated reply | AI candidate | Safe CTA trigger |
| --- | --- | --- |
| Generic thanks, silence, quote from a forwarded thread, unsubscribed, objection with no request | No intent / conflicting | WAIT/SUPPRESS; **no CTA** |
| They describe a genuine business problem | `problem_discovery` | `DISCOVERY_QUESTION`: one relevant question, no pitch |
| They explicitly ask how we would help / request a written outline | `solution_evaluation` | `WRITTEN_SCOPE`: offer a concise scoped explanation, no price or checkout |
| They ask about purchasing/pricing a **named** catalogue product, independently verified and bound to that order prospect | `explicit_product_purchase_request` | `PURCHASE_REVIEW`: propose the approved scope, price and secure checkout details for human review; **never auto-send** |

**Release contract:**
- The model's advisory result must be a valid `TypedDecisionResult`, confidence **at least 0.85**, `shadow_only=true`, `execution_authority=none`, and strictly bound to `canonical:reply:{id}:sha256:{current message}`. It cannot create its own canonical evidence.
- Canonical **tenant, prospect, original sent intent, exact person email, authenticated provider, same-thread inbound and nonsynthetic text** must all match, and suppression must be independently cleared before any inference. Public posts, opens/clicks and sender-reported events are not enough.
- The deterministic checker corroborates the actual **new** message (not quoted history) and rejects old model scores, contradictory negative replies, mismatched products, missing exact purchase proof, and attempts to turn generic curiosity into procurement.
- A `CTA_DRAFT_FOR_HUMAN_REVIEW` is only an **internal recommendation**, not a mail instruction. Existing closer, consent/suppression, current professional-mailbox sender, founder approval, catalog, terms, delivery and payment gates retain their authority. No auto follow-up, phone call, meeting booking, live paid spend or checkout activation.
- AI inference is **adapter-ready, not independently enabled in production**; a trusted operator must pass the existing authorised **resident** typed provider. The other outbound/mail agent owns final integration into authenticated reply consumption and governed send review, not this prospecting worktree.

**Regression evidence:** isolated unit/provider fixtures check all CTA tiers, precise reply body hash, person and tenant mismatches, prior unsubscribe, spoofed or changed model results, suppression holds, absent/unavailable resident inference and no-send invariants. These tests do not prove a production buyer, live AI execution, permission to contact or realised revenue.

## Context-aware natural CTA reply after verified buyer intent

**Existing module upgraded:** `empire_os.rapport_intent_cta.compose_contextual_cta_reply_for_review`, wired into `outbound_department.plan_outbound_account` as `intent_cta_reply_review`; `scripts.review_search_first_sale_rapport.review_candidate` surfaces the same. These are offline **drafts**, not a new sales runtime, provider or send adaptor.

- **Problem discovery**: one useful question about the priority service/location. No sale or product mention.
- **Solution evaluation**: answer the buyer's request **now**, in plain English, using the existing Search Intelligence product's scope. Describe a written, sourced deliverable and what cannot yet be verified. One narrow question; no price or link.
- **Explicit named-product purchase**: only where independent exact product request evidence, typed-AI corroboration, original authenticated reply, independent suppression clearance, and a supplied **currently verified** catalog row all match. Propose the verified **USD one-time** catalog price, existing product scope and official checkout page, **for human review only**; no newly created order or automatic email.
- **No verified catalog**: `HOLD_REVIEW`, `body_text=null`, no invented quote. Caller-reported catalog status is **not** an attestation of source: `catalog_origin_verified_by_this_module=false`; original DB readback, product terms, sender and recipient proof must be checked by the existing outbound/commercial owner before release.
- **Solar Opportunity Map**: its separate prospect-based builder is not yet bound to the standard Search Intelligence report contract. Hold `product_scope_not_verified` for the reply composer rather than invent deliverable wording.
- **Explicit negative, opt-out, later or unrelated replies**: rejected *before* calling resident AI. Quoted older email history and an altered-model message digest cannot become new buyer intent.
- **No sender connection**: no SMTP/IMAP credential, timer, DB changes, website change, customer contact, commitment or financial action. Drafts stay `send_authorized=false`.

**Test evidence:** the targeted checkout/catalog, Search Intelligence, existing closer/outbound, new intent classifier and contextual reply suite checks cover 219 regressions (one non-blocking library deprecation warning). They do not prove a live buyer reply or live model inference.

## Dedupe, gates, operational owner

- 14 October snapshots checked: `runtime/revenue_distribution/latest.json` (snapshot last generated 10 Oct) and `runtime/buyer_acquisition/scout_latest.json` (14 Oct). None of the three exact domains appeared. **This is not a canonical EmpireDB prior-contact/suppression proof.**
- Connected Gmail search across these domains from 1 August to 14 October returned zero matches; **professional mailbox and all legacy sends not audited**.
- Live `scripts.verify_founder_mail_end_to_end_readonly` readback on 14 Oct: `ready_for_prospect_outbound=false`, `relay_send_authorized=false`, direct founder inbox not verified; independently confirmed in this session. Other agent owns completing the mailbox/outbound programme.
- Each prospect still needs canonical exact person/domain suppression; prior send/reply/bounce reconciliation; recipient-person identity and permitted route; current mailbox-provider send authority; founder-authorised single intent; no repeat/loop/automatic follow-ups.
- Do not claim any of these is a willing buyer, qualified payable opportunity, forecast, accepted scope, or sale.
- No emails, forms, calls, orders, payment actions, service restarts or database writes undertaken to prepare this packet.
- Sequence by `validated contact route + trigger`: **Green Coast first**, RoofElite second, Aastro third; only outreach owner should move a cleared packet to send, and must revalidate current evidence.
