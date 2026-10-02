# Revenue Inventory Ladder v1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Owner: Sales & Revenue / Autonomous Revenue OS

## Goal

Maintain multiple monetizable inventories from the same canonical prospect stream:

1. RAW_LEAD
2. PREQUALIFIED_LEAD
3. QUALIFIED_CALL
4. BOOKED_APPOINTMENT
5. CPA_OUTCOME

The same prospect may advance through the ladder only when stronger observed
evidence exists. Higher stages never infer or overwrite lower-stage truth.

## Existing canonical owners reused

- prospects + identity links: canonical identity
- qualification_v2: lead quality / evidence confidence
- conversation_qualification: inbound transcript-backed qualification signals
- voice/conversation events: observed calls
- commercial_products: PPL / call / appointment / hybrid products
- Buyer Allocation: qualified supply -> activated buyer
- Commercial Exchange / Revenue Exchange: market matching and economics
- fulfilment_orders + commercial_events: delivery / payment / outcome
- payment_governance + bsc_usdt_verifier: USDT/BSC settlement
- Economic Memory / Cortex: observed outcomes and learning

No parallel CRM, marketplace, timer, payment ledger or synthetic price engine.

## Promotion rules

RAW_LEAD
- canonical prospect exists.

PREQUALIFIED_LEAD
- latest qualification status=scored;
- tier is warm or hot;
- score >= existing allocation floor;
- v2 evidence confidence >= existing decision-confidence floor;
- active canonical identity link exists.

QUALIFIED_CALL
- PREQUALIFIED_LEAD gate passes;
- observed conversation/call exists;
- inbound transcript evidence exists;
- at least one explicit qualification signal exists;
- call outcome is not inferred from outbound attempt alone.

BOOKED_APPOINTMENT
- QUALIFIED_CALL gate passes;
- explicit booking/meeting evidence exists;
- booking identifier/time evidence is present;
- appointment is not inferred from intent, reply or call alone.

CPA_OUTCOME
- BOOKED_APPOINTMENT or other explicitly permitted conversion path;
- explicit buyer/customer outcome evidence exists;
- conversion/closed/won event reference exists;
- never infer outcome from appointment attendance or payment request.

## Monetization mapping

RAW_LEAD -> not sold by default unless product explicitly allows raw supply.
PREQUALIFIED_LEAD -> PPL.
QUALIFIED_CALL -> pay-per-call / qualified-call.
BOOKED_APPOINTMENT -> appointment / per-schedule.
CPA_OUTCOME -> CPA / performance outcome.

Commercial price remains NULL/unknown until a verified buyer/product price exists.
Public observed ranges are not binding prices.

## Agentic loop

OBSERVE -> classify all canonical prospects into highest evidence-backed inventory
stage -> compare supply with verified buyer/product demand -> produce bounded next
actions -> Gauntlet -> internal execution or Founder Gate -> VERIFY -> RECORD ->
repeat.

Typical automatic internal actions:
- source/enrich/score prospects;
- refresh qualification;
- classify inventory;
- match to verified buyer capacity;
- prepare call/appointment review packets;
- capture observed reply/call/booking evidence;
- refresh read models.

Founder-gated:
- live outbound send/call unless separately authorized;
- binding terms;
- funds/mainnet;
- irreversible revenue/accounting;
- destructive infrastructure.

## Truth invariants

- no synthetic buyer, price, capacity, call, appointment or conversion;
- unknown stays null/unknown;
- one evidence item must not promote multiple stages unless it explicitly proves them;
- outbound attempt != qualified call;
- positive reply != booked appointment;
- booked appointment != CPA outcome;
- delivery != payment;
- payment request != verified payment;
- verified payment != realized margin until fulfilment/outcome rules pass.
