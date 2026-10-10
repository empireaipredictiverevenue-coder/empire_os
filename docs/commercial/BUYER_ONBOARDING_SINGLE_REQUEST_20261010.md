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
