# Empire AI — One complete buyer onboarding request (10 October 2026)

**Purpose:** move a buyer who has engaged with Empire AI through one complete fact-finding email, a documented answer matrix, a buyer-specific approved campaign and one attributable paid event. Reuse the existing commercial relationship registry, lead/call product catalog, partner technical review packet, Deal Room, Documenso and founder approval gates. No new platform, timers, automatic sends, contracts or payment instructions.

## Operating rule

1. **Cold prospects:** use the existing `rapport_first_human_specific_v1` policy. Do **not** send a transactional questionnaire, prices or a meeting CTA as a first touch.
2. **Engaged partner:** send *one* consolidated requirements email only after identifying which answers they have already supplied. Store the exact thread, message ID, timestamp and any attachments as evidence. A public website or unrelated buyer's terms do not answer their buyer-specific questions.
3. **After replies:** classify every field as `REPORTED`, `DOCUMENT_RECEIVED_UNREVIEWED`, `INDEPENDENTLY_VERIFIED`, `MISSING` or `CONFLICT`. Do not turn an email claim into one of the nine launch gates until independently verified.
4. **Missing follow-up:** list only unanswered or contradictory fields in **one** grouped response. If the buyer promised documents, wait for them rather than re-sending yesterday's same questionnaire.
5. **Never request API passwords/tokens in ordinary email.** Obtain connection information and setup documentation first, then exchange actual secrets through the approved protected configuration channel. No credentials in Gmail summaries, Git, CRM previews or exported archives.

## One-pass buyer information contract

| Group | What the buyer needs to provide | What counts as proof |
| --- | --- | --- |
| **A. Live buy-box & capacity** | Programme/campaign name and format (Direct pay-per-call, RTB, CPL/form, transfers), live verticals and jobs accepted, homeowner/lead eligibility, active states/metros and **ZIPs or postcodes**, genuine available buyer capacity, caps, exclusion areas, opening hours and timezone | Current buyer/campaign specification tied to this partner |
| **B. Quality & payable event** | What precisely makes a call/lead payable: min connected seconds, live agent or IVR completion, unique caller/repeat lookback, exclusions, transfers/recordings, returns, replacement, disputes, lead deduplication and chargebacks | Contract/programme rule and provider-side acceptance-event definition |
| **C. Unit economics & settlement** | Payout or rev-share basis, **variable-bid vs fixed**, currency, fee deductions, minimum payout, settlement schedule and method, invoicing/statement process, refund windows, whether source-exclusive or shared | Specific partner offer, signed terms and provider statements; **never infer from public ranges** |
| **D. Source/legal/compliance** | Explicit acceptance of **Empire-owned first-party organic/SEO** traffic (not paid or sub-affiliate), site/landing approval requirements, precise disclosures/consent and tracking/recording/privacy rules, relevant US/UK consumer/marketing law, permitted content and any geographic restrictions | Buyer-source written approval + compliance/landing review, legal review as required |
| **E. Technical & pilot operations** | Named commercial and technical owners; route format and documentation; tracking-number allocation, caller-ID/ANI pass-through, ZIP IVR/RTB choice, events/webhooks/postbacks, duplicate events, campaign IDs, routing tests, test-call and failure procedure, support/escalation; exactly **one** first permitted corridor and controlled nonbillable test method | Buyer-specific provider configuration evidence and successful governed testing |
| **F. Onboarding & signatures** | Correct contracting entity, legal agreement/insertion order/MVA, applicable W-8/W-9/tax details, onboarding form, privacy/SLA terms, approved signature process (use existing Documenso once founder-approved), payment/statement reconciliation contact | Received documents, explicit approvals, signed versions and authorised account binding |

**Internal response matrix:** each field needs `partner_key`, `question_key`, `status`, `source_thread_id`, `source_message_id`, `answered_at`, `independent_verification_ref` (nullable) and `remaining_task`. Never store unsanitised email bodies or login secrets in the commercial registry.

## Reusable warm-buyer email — only after a genuinely positive conversation

**Subject:** Empire AI — one complete pilot setup pack

> Hi [first name],
>
> Thanks for the conversation. To avoid sending you several rounds of questions, could you send one current campaign/partner onboarding pack for a **small Empire-owned organic/SEO pilot**? A programme PDF, spec sheet or your usual onboarding form is absolutely fine; no need to retype anything it already covers.
>
> **1. Current buyer demand:** one live campaign to start with, accepted job types, active ZIPs/postcodes or preferred metro, qualifying caller/lead criteria, hours/timezone and caps.
>
> **2. Payable event and commercials:** connected-call/lead qualification, duplicates/returns/disputes, the *actual* payout or rev-share calculation, currency, settlement dates and minimums.
>
> **3. Source and compliance:** written acceptance of our own first-party organic landing pages and calls, required landing copy/disclosures, consent and recording rules, plus any excluded traffic or geographies.
>
> **4. Technical:** Direct/RTB/API or transfer format, tracking number/ID, ZIP handling, original caller ID, reporting/postbacks and the agreed **nonbillable** test procedure. Please identify your technical contact; no passwords or API secrets by email.
>
> **5. Onboarding:** the agreement/insertion order and any MVA, tax or onboarding form, the contracting entity and preferred approved signing workflow.
>
> We can then return one corridor-specific pilot sheet for your review. We won't enable traffic, sign terms or treat a test as payable until everything is verified and agreed.
>
> Thanks,
> Phil
> Founder, Empire AI
> https://empire-ai.co.uk

**Use this after rapport**, not as unsolicited cold outreach. Shorten for buyers whose existing documents already cover these items.

## Actual current conversations — do not repeat answered questions

| Partner | Relevant authenticated email evidence | Answered / buyer-reported | Outstanding, grouped once | Next permissible action |
| --- | --- | --- | --- | --- |
| **Lead Smart / Seth** | Seth `gmail:1a10c6b2530f2951`; support `gmail:1a12229d9d3ffe75` | Empire-owned SEO calls accepted for named nationwide roofing offer; Ringba number assigned; Direct IVR collects ZIP; RTB off; original caller ID required; America/Chicago with DST; indicative connected-call window/deduplication described. | **Seth's explicit approval or requested edits for exact `/roofing` page**; independent buyer-routing proof; original caller-ID transport test; founder publication/traffic authority. | **WAIT FOR SETH.** Do not resend timezone/Direct ZIP questions. Call button OFF, no consumer traffic. |
| **LeadBank / Eleonora and Mahad** | Founder all-in-one follow-up `gmail:1a122fc6010e3b5b`; Eleonora's reply `gmail:1a1230003eb39320` | Interested in onboarding; Eleonora promised agreement and onboarding form and forwarded technical questions to Mahad; initial source described as organic roofing inbound calls. | **Actual documents**; buyer-approved live roofing ZIP/metro corridor; billable qualification, hours/caps; payout/settlement/duplicates; source & landing approval; Mahad's route and test spec. | **WAIT FOR DOCUMENTS / TECH RESPONSE.** Do not resend the same request. Review documents immediately on receipt. |
| **Validated / Zach** | Founder consolidated follow-up `gmail:1a122fc70c9614c1`; Zach response `gmail:1a114d6b9b33e40b` | Genuine interest in consumer-initiated roofing/HVAC/restoration, first-party source attribution essential; founder stated Empire-owned organic calls. | One **current** accepted roofing corridor + ZIPs, payable event, rev-share, accepted consent and landing rules, source approval, route/test instructions and applicable partner agreement. | **WAIT FOR ZACH.** The forwarded generic address historically bounced; do not retry it. |
| **Connexis / Kieran** | Founder consolidated follow-up `gmail:1a122fc85a098bea`; earlier Kieran reply `gmail:1a0e6d76dbe29583` | Two-way discussion; Kieran promised publisher programme details. | **Pick one live UK/US call programme** with job/geography/buyer rules, connected-call acceptance, payout/settlement and actual applicable agreement (do not mix website API/CPL terms with call terms); tracking route and source approval. | **WAIT FOR KIERAN.** Do not propose ZIPs/postcodes until named programme confirmed. |

**The last three comprehensive partner follow-ups were sent on 9 October 2026.** There is no evidence of approval to send duplicates or any new unsolicited outreach on 10 October.

## Email evidence saved, with original messages preserved

- **Gmail label:** `EmpireOS/Buyer Partnerships`; all 45 messages in the above four complete warm buyer threads labelled successfully on 10 October 2026. The original emails, quoted history and two older PDF attachments remain in Gmail.
- **Private indexed message archive:** `runtime/buyer_network_intelligence/buyer_partner_message_index_20261010.json`, permissions `0600`. It contains four thread records, original message IDs, dates, subjects, participant headers where available, attachment filenames and Gmail source links. It **does not contain message bodies or credentials**.
- **Original broader 57-thread relationship summary:** `runtime/buyer_network_intelligence/gmail_relationship_evidence_latest.json`, `0600`. This is a separate past import; do **not** update its original capture time just because these four threads were rechecked.
- **Continuity:** `runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json` remains the existing automated review queue. Its latest evidence is snapshot-derived, not live Gmail polling. A connected Gmail scan does not mean the EmpireOS server has independent direct Gmail login or a configured own-IMAP mailbox.

**Business completion standard:** one buyer-specific accepted buy-box + terms + legal source/consent + correctly tracked/routed eligible event + approved launch + verifiable payable conversion and reconciliation. Read-only evidence, approved campaign enrollment and a draft email are not realised revenue.


## Mandatory one-email launch contract (12 October 2026)

This **enforces** the existing 10 October single-request policy. The earlier Lead Smart row above is historical: Seth approved the revised buyer page on 11 October; it is now published. Founder scope approval and the 27,100-ZIP production refresh are also complete. Do not request these again.

**Do this once for each genuinely engaged buyer BEFORE committing to a launch date:**

1. **Extract existing answers first.** Read the complete current thread, existing agreements, buyer specifications and runtime observations. Mark each below as `ANSWERED_REPORTED`, `PROVEN`, `UNANSWERED`, `CONTRADICTED` or `NOT_APPLICABLE` with exact message/document references. Never reask the first two categories.
2. **One consolidated buyer email.** Ask only for `UNANSWERED/CONTRADICTED` items that are genuinely buyer-controlled; group them in one numbered reply with a **yes/no/not-available** response and a source document/redacted screenshot where necessary. Permit one attached existing programme PDF/spec instead of retyping the facts. Do not ask for secrets, raw caller ANI, call recordings or customer personal data.
3. **Keep our own work off the buyer's plate.** Deployment, source checks, website legal drafting, campaign landing hashes, payment wiring, integration tests, SEO, supervised monitoring, internal stop control, CRM and founder approval are **EmpireOS-owned**, not questions for Seth.
4. **After their reply, update the same matrix.** Accept evidence once; branch only on genuine contradictions. Never send a status/thanks email that contains new technical questions. If one indispensable proof is still missing, send at most **one concise delta** with its exact owner and acceptable artifact; otherwise escalate through the named technical owner or advance another already engaged buyer, preserving the hold. The one follow-up is not permission for unapproved or duplicate outbound.
5. **Measure the process:** initial request count, repeated-question count (target **0**), time from first engaged reply to complete buyer packet, verified proof coverage, blocker owner, and time to first eligible commercial event. No recurring timer, new provider, message automation or outbound authority introduced.

### Required evidence to request up front

| Contract | Exact buyer questions | Sufficient buyer answer / proof | Owner |
| --- | --- | --- | --- |
| **Buy box and source** | Campaign, specific payable vertical/service, accepted geo ZIPs, hours with DST, capacities/caps, accepted Empire-owned organic/SEO source, banned traffic | Named current campaign rules plus explicit owned-source acceptance | Buyer commercial |
| **Payable event and money** | Required connected seconds, IVR/ZIP steps, live agent status, unique/repeat rules, invalid reasons, payout **for this route**, currency, rate variability, settlement timing, disputes and reconciliation | Contract/IO or programme offer and reporting definitions for exact ID (not public bid ranges) | Buyer commercial/payments |
| **Live routing and attribution** | Campaign and tracking number, enabled Direct buyer/target and caller ANI preservation, target evidence, test-call interpretation, call/status event columns, source/subsource, retry and escalation path | Dated redacted provider admin screenshot/configuration or provider-authoritative event matching exact campaign; no raw phone numbers | Buyer technical |
| **Call privacy and recording** | Recording **on/off**; which party decides/controls it; caller notice/consent and where delivered; access and sharing; retention/deletion process; international parties and state-specific conditions | Written real configuration/roles and reviewed disclosure or confirmed disabled recording for the pilot, with legal assessment where applicable | Buyer compliance + Empire legal |
| **Paperwork and launch** | Legal contracting entity, insertion order/MVA/onboarding requirements, reviewer/technical contact and support path | Current partner docs and named operator | Buyer partner manager |

**An onboarding email can collect facts; it cannot independently verify buyer-side routing, certify US recording law or create binding terms.** Store proof status and references separately. Send policies for final review only after the factual data-flow and recording answers are known. The first real connected call is verified **during a separately approved limited pilot**, not fabricated from a hung-up test.

### Reusable single-pass buyer message — for the NEXT engaged partner

**Subject:** Empire AI — one reply to finalise our first inbound-call pilot

> Hi [name],
>
> To get the first campaign running without a long email chain, could you send your current programme/spec and answer only the missing points below? A redacted screenshot, agreement or a link to your approved onboarding pack is fine. Please mark anything unavailable **N/A** and name the person who can confirm it.
>
> **1. Campaign and eligible traffic:** exact live programme/campaign ID, jobs and ZIPs accepted, hours/timezone and caps; confirm Empire-owned first-party organic/SEO traffic and our landing/source are permitted.
>
> **2. Payable event and settlement:** call/IVR/connected-seconds rule, repeats/rejections, exact campaign payout or variable-rate basis, currency, settlement and disputes.
>
> **3. Routing and attribution:** assigned tracking number, enabled buyer target, original caller-ID pass-through, exact call-status/postback/report evidence fields, and your technical escalation contact. A dated, redacted configuration screenshot is enough; please send **no personal caller data or credentials**.
>
> **4. Recording/privacy:** is recording enabled? If yes, who controls it, what pre-call/in-call notice and consent is used, who can access it, and the actual retention/deletion process? If a capped trial can run **without recording**, please confirm that instead.
>
> **5. Documents:** current agreement/IO and any required partner forms plus the person authorised to approve the pilot.
>
> We will handle our website, internal controls, compliance review and technical checks. One consolidated reply or your existing onboarding pack is sufficient; then we'll send one precise pilot confirmation.
>
> Thanks, Phil — Founder, Empire AI

### Lead Smart current delta — **DO NOT SEND AGAIN**

- **Already answered and verified:** Seth's landing review `gmail:1a12bc009d04fcc9`; founder launch scope; installed roofing page and ZIP checker; 27,100 public provider ZIPs; America/Chicago hours; Direct IVR ZIP; consumer organic channel approved.
- **Last buyer reply:** `gmail:1a12d44d7e2f46a8` states recording **ON** and that Seth hung up **before connection**. It proves **neither** an enabled connected buyer leg nor actual ANI at that buyer destination.
- **Already requested:** `gmail:1a12d47934923a1d` asks the admin to evidence the enabled Direct target, original ANI preservation, and recording disablement for a capped pilot **or** actual recording notice/retention/access/deletion. No duplicate new email while this is pending.
- **EmpireOS-only:** publish legally approved exact content when settled; maintain the first-party gating and five-site-handoff control; verify authenticated tracking and the provider connection before enabling calls. Do not make Lead Smart repeat our own execution steps.
