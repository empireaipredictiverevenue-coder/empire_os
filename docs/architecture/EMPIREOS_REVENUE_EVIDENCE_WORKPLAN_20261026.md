# EmpireOS V2 — Deterministic Evidence Work, Not Another Agent
**26 October 2026 | Single original EmpireOS/EmpireDB/Smart CRM, OBSERVE-only release candidate**

## What genuinely changed
The existing revenue-completion supervisor now builds a source-linked `evidence_workplan` from the SAME observation cycle's whole-system snapshot and exact per-candidate Opportunity Factory review. The original unified review command also merges bounded authenticated publisher-reply proof tasks, where these are available.

Each work item has: stable digest identity (`evidence_work:...`); existing owner; exact evidence source; required proof; priority; explicit research/privileged-proof state; and every execution gate FALSE. Duplicate timer observations produce the same work keys. No second queue, timer, agent, database or CRM is created. This module does **not** enqueue jobs into the existing `empire_os.department_work_queue.DepartmentWorkQueue`. The existing queue remains the sole authorised future transport; unsupported actions must not be silently dispatched.

## Priorities and decision rules
1. **BuyerAcquisition**: one REAL paying buyer, signed buy box, actual accepted event, verified purchasing capacity, territory, price and refund/settlement terms. Research records ≠ verified buyers.
2. **SmartCRM**: original authenticated EmpireDB tenant/business binding; no caller-declared tenant ID or public domain-to-tenant inference.
3. **OpportunityFactory**: at most 3 exact research records per cycle, including source-row rights and validated quant/offer/distribution evidence. Stable `research_review:` refs are REVIEW ONLY, never opportunity UUIDs.
4. **Existing source owner**: when a source is stale/missing/unsafe, restore the original bounded producer before proposing downstream promotion.
5. **BuyerAcquisition for genuinely observed publisher mail**: only bounded, recognised, authenticated reply codes and exact Gmail provider message receipts may yield the specific task `VERIFY_ONE_CONTRACTED_INSTALLER_BUYBOX_AND_PRICE`. This is not authority to quote commission, send another email, or allocate a lead.

## One exact existing buyer reply (not an automatically approved customer)
The existing buyer relationship registry already has a founder action for `lead-smart`: stage `INBOUND_REVIEW_REQUIRED`, recorded inbound 23 October **after** the latest outbound, and action `REVIEW_EXISTING_ROUTING_RECORDING_REPLY_NO_REPEAT`. The cohesion reader now surfaces only bounded **recent exact same-entity** reply reviews with newer authenticated inbox observations, bounded allowed action and outbound disabled. The original Buyer Reply Operations owner receives `founder_review:lead-smart` in the work proposals. This DOES NOT attest the Ringba buyer leg, ANI pass-through, recording consent, buyer commercial terms or available capacity, and must not trigger another email, traffic routing or fulfillment.

## Race-condition fix: compare one generation
The whole-system view and Factory candidate reviewer may read at different moments while the original Factory's timer replaces its snapshot. Both readers now compute the exact source-byte SHA-256. The work planner requires those digests to agree before proposing per-candidate handoff work. On mismatch it emits a higher-priority `RECHECK_COHERENT_FACTORY_GENERATION` HOLD; it does NOT dispatch tasks based on mixed generations. SHA-256 is a **consistency marker**, not evidence that the source claim is true, lawful or contractually approved.

## Observed source-quality correction
Original Buyer Scout output contained `gmail.com` as a company research candidate. The existing non-prospect discovery host filter now excludes exactly this generic email platform host alongside previously filtered infrastructure. The change does not blacklist legitimate companies with free-mail contact addresses, alter recipient suppression policy or delete historical data. Tests assert no site probe or artificially inflated business-candidate count.

## Real read-only acceptance evidence
Current original runtime preview returned:
- 9 whole-system source artifacts current.
- 12 commercial lifecycle stages represented, none attested end-to-end.
- 18 recent Factory research records (count varies as the original timer updates), zero promoted commercial handoffs.
- 6 deterministic source-linked evidence work proposals: first buyer contract verification; **Lead Smart's independently recorded inbound routing/recording reply requiring review**; original CRM binding; then 3 Factory validations.
- Same-generation Factory fingerprint verified. Existing Astra queue writes **0**; outbound sends **0**; real payment execution **0**; database writes **0**.
- Commercial customer conversion/revenue still not proven. This feature does not manufacture capacity or paid customers.

## Operational release boundaries
- The existing `empire-revenue-completion-supervisor.timer` may automatically refresh these read-only work proposals when the original protected deployment channel installs the exact reviewed code.
- The original `empire-buyer-gmail-evidence.timer` can refresh the bounded publisher evidence recognizer only after its **separate protected mail-cycle release review**.
- Only once an existing vetted department worker adapter supports a specific `authority=observe` proof task, a separate owner-authorised queue bridge may enqueue it. The current code deliberately keeps `enqueue_authorized=false`. Unsupported action names must never enter the worker queue; do not create a second worker.
- Avoid copying these files into the active checkout while unrelated agents are editing it. The review branch is not a substitute for tested release, service smoke test and rollback readiness.
