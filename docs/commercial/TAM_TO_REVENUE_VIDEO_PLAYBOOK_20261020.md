# Empire AI — Taylor Haren TAM-to-Revenue Pilot

**20 October 2026 | Entire video strategy, not click-tracking alone**

Reference: https://youtu.be/jXxjKAz1Org

## The exact operating model we are implementing

**Qualified entire market → outcome-first offer → single email/ad creative
per person per 30–60-day wave → measurable click/onsite/opt-in/meeting →
same-business-day qualified action → verified customer/revenue → optimise.**

This is adapted from the video and the creator's published account; the
creator's sign-up, CPL and revenue lift figures are not Empire results.
Replicate the *method*, not scale or claims. Sending to an entire TAM is
conditional on each verified contact being lawfully addressable; the approach
is NOT authority to blast scraped personal addresses or evade deliverability
limits. Do not conflate a click, website visitor, accepted enquiry or revenue.

## Commercial pilot — ONE scoped wave, not another agent

Use existing **Sales Director / buyer-acquisition** owner. Primary cohort:
**UK solar lead buyers / qualified performance partners** only where buyer
criteria, willingness and lawful contactability are verified. Secondary
comparison cohort: **US roofing/home-services lead buyers** with separately
verified buyers and geographic scope. These cohorts have different regional
lawfulness and supply verification; do not combine into one email audience.

**Real readiness today:** the existing TAM market observation is 10 days old,
with 8 observed company entities, and `source_population_complete=false`.
This is a *research sample*, not all companies in the UK/US verticals and not
eight sendable contacts. The five ASTRA campaign assets are runtime-matched,
but there are **zero exact measured campaign outcome matches**. The adaptive
outreach optimiser is learning and has 4 labelled intent examples at current
snapshot time; it has no verified revenue winner.

## Three radically different offer tests (never fabricate evidence)

These are **draft hypotheses** for the existing offer/creative owner to attach
to genuine product proof and current commercial terms; no unverified promises.

| Arm | Buyer pain | Low-friction offer | CTA |
|---|---|---|---|
| A — buyer_inventory_fit_offer | Paying for leads without reliable territory/quality fit | Review available, verified supply categories and buyer criteria; say "no matching inventory" if none | Request buyer-fit check |
| B — revenue_leak_signal_offer | Demand exists but acquisition/response capacity is wasted | Source-grounded opportunity/coverage snapshot for the buyer's chosen territory | Request opportunity snapshot |
| C — verified_market_opportunity_brief | Can't tell which market/offer to enter next | Short independently sourced market evidence brief, including unknowns | Get the evidence brief |
| Control — no_marketing_holdout | Incrementality test | Do not send | None |

For each arm use the existing `outreach_message_optimizer` and
`adaptive_outreach_optimizer` to test **outcomes**: compare subject,
problem, short copy and CTA. Keep a simple B2B text email. No fake
personalisation, invented testimonials, fabricated buyer demand or vague
"AI-powered" claims. Different geography/language/business models are
separate audience segments, not arbitrarily mixed experiments.

Example copy concepts (never send without source/terms verification):

- A: "Buying [verified niche] leads in [verified territory]? We can check
  whether our current criteria and supply match yours. If they don't, we'll
  tell you. Would a buyer-fit check be useful?"
- B: "We're examining where verified demand may not be reaching local
  operators. We can share a short evidence snapshot for [territory],
  including gaps and uncertainty. Worth sending one over?"
- C: "Choosing the next territory is difficult without source evidence.
  We can assemble a short market brief with observed demand signals and
  caveats for [area]. Would that help your planning?"

These are **not** assertions that Empire has stock to sell, a paid product
price, a perfect buyer match or a real prospect pain.

## 12-week operating calendar

1. **Weeks 1–2: map qualified TAM.** Reuse
   `tam_market_runtime.py` and existing buyer scout. Define company,
   territory, buying role, sector, source timestamp, dedupe canonical
   identity, validated business email and lawful marketing basis. Keep
   separate market total, observed research population, eligible contacts,
   opted-out and undeliverable. Never turn observed sample into TAM.
2. **Weeks 3–4: build offer/creative experiment.** Existing offer book and
   account strategy establish real value proof. Reuse `experiment_engine`
   for stable 10% holdout / 3 experimental arms and current outreach
   optimiser for copy quality. Validate sender setup, bounce/suppression,
   per-market channel basis and website CTA before any actual launch.
3. **Weeks 5–8: first single-touch wave.** Sender owner controls permitted
   rate and delivery; one email per eligible person this wave, no forced
   multi-email sequences, no purchased addresses without evidence. Link
   destination points to an existing approved owned page. Collect real
   delivery and CRM receipts. The separate gateway/analytics owner brings
   signed-click, site analytics and consent proof online if authorised.
4. **Weeks 5–8: same-day signal handling.** A verified enquiry, meeting or
   permitted response moves to the existing Sales Director promptly.
   Click-only/unknown sessions create a *research/review* signal, never
   automatic cold calling, identity inference or ad audience exports.
   Site visit and re-targeting require their specific lawful permission
   and platform rules. Continue helpful owned organic content where valid.
5. **Weeks 9–10: analyse per-market arm.** Baseline and holdout observed
   over comparable windows. Primary metric = verified paying customers
   per randomly assigned eligible account (including the unsent holdout). Supporting metrics: deliveries, verified website
   sessions, server-accepted enquiries, meetings, bounce/opt-out rate.
   Click-only/positive replies cannot be declared winners. No uplift
   claim without integrity and enough independently observed sample.
6. **Weeks 11–12: second wave and commercial decision.** Eligible contacts
   can receive a different value proposition **only after ≥30 days** and
   renewed lawfulness, suppression and source checks. Promote only a
   commercially measured winner, otherwise keep testing. Future waves
   target every 30–60 days, not auto-scheduled until lawful sender is live.

## Required end-to-end measurement

`qualified TAM -> eligible contacts -> accepted/delivered -> verified
gateway click -> consent-qualified website session -> signup/enquiry ->
qualified meeting -> real buyer -> fulfilled order -> recognised revenue`

Revenue claim authority belongs to existing EmpireDB canonical payment /
commercial event receipts; no link or form completion is itself revenue.
Per-campaign results **unknown**, not zero, until the stage's own
independent receipts are connected. Record per-arm denominators and
evidence, not vanity open rates.

## Source integration — use existing owners

- **TAM owner:** `empire_os/tam_market_runtime.py`,
  `empire_os/tam_market_intelligence.py`; freshness/dedup/source audit.
- **Sales Director / offers:** `empire_os/gtm_offer_strategy.py`,
  `empire_os/commercial_offer_book.py` and existing buyer-acquisition CRM.
- **Creative test/assignment:** `empire_os/outreach_message_optimizer.py`,
  `empire_os/adaptive_outreach_optimizer.py`,
  `empire_os/experiment_engine.py`.
- **Distribution:** existing governed sender; do not call legacy
  `empire_os/campaigns.py.launch()` indiscriminately (it has a mutable
  legacy SQLite/deliverer side effect).
- **Click and site:** `empire_os/analytics/campaign_click_evidence.py`
  plus existing first-party event contract. These are **offline** until
  approved gateway/consent integration, NOT click or visitor collection today.
- **Sales feedback:** existing CRM / campaign output and
  `run_campaign_measured_outcome_resolver.py`. Verified customers/payments
  must be reconciled to canonical commercial receipts.

## Executable implementation in this branch

`scripts/review_tam_full_funnel_strategy_20261020.py` reads exact existing
snapshot paths **read-only** and produces an eight-step owner handoff,
12-week testing programme, actual source blockers and nine-stage measurement
contract without leaking raw contacts. It includes pure functions for:

- recipient suppression + cross-campaign 30-day cooldown + deterministic
  audience/holdout/offer assignment using existing experiment engine;
- same-day signal routing for click vs enquiry vs booked meeting vs revenue;
- evidence-gated descriptive customer-per-delivery arm comparison.

```bash
cd /home/ubuntu/empire_worktrees/campaign_click_intent_bridge_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_tam_full_funnel_strategy_20261020 --read-only
```

No production send, retargeting, tracking, public publication, API service,
database write, permission expansion or budget activation is hidden here.
The next *real* activation belongs to existing market, sender, website
and Sales Director owners, using current reviewed evidence and explicit
authority at the actual operational boundary. Incomplete source proofs
remain BLOCKERS, not silently waived.


## 20 October continuation — real eligible-cohort builder and offer creatives

This wave **implements** more of the video method, not a second tracking app:

- Reads only the existing private buyer qualification and commercial
  relationship snapshots; never logs/returns their personal/company rows.
  Same-day buyer-source reads have shown **22–23** shortlisted targets
  during concurrent owner refreshes, alongside **261** relationship
  records and **0** contacts confirmed outbound-ready. The live
  review command must be used for the current count; observed target
  totals are not permissioned email recipients. Permitted recipient
  count remains **unknown**, not an inferred count from either source.
- `assemble_verified_cohort_wave` accepts a bounded set of **opaque CRM
  contact keys** resolved by the existing owner's trusted private callback;
  validates tenant, vertical/country, company grouping, evidence freshness,
  offer proof, recipient-level lawful marketing eligibility, suppression,
  sender readiness and last-contact history. Does **not** accept browser
  self-asserted consent or raw personal email lists.
- Explicitly separates a lawful **scoped pilot cohort** from the claim
  that the **entire TAM** is covered. A complete TAM census is a scale
  objective, not a reason to prevent pilot tests of evidenced eligible
  contacts. The current observed TAM still has **8** stale sample
  entities and does not verify a sendable GB solar cohort.
- Reuses Empire's existing deterministic experiment engine to put
  **all people at the same company in one offer/holdout arm**, rather
  than sending mixed messages to coworkers. Repeat key inputs are
  deduplicated; suppression and 30-day last-contact policy hold sending.
- `review_three_offer_creatives` prepares the three actual plain-text
  campaign drafts: **A quick buyer-fit check**, **Local demand evidence**
  and **Choosing your next market**. Each is run through the existing
  `outreach_message_optimizer.review_message` hard copy-quality check.
  Current structural scores are 90/100/100. They are **drafts**, not
  personalised or proof-backed send assets; they make no inventory or
  paying-customer claims.
- The current real source read confirms **zero outbound-verified buyer
  contacts** and **zero exact campaign outcome matches**. Until a
  source-owned CRM recipient join and lawful approved campaign route
  exist, every contact and send action remains held. No paid-media
  audiences or browser analytics were activated.

### What the existing Sales Director and sender owner must connect

Supply its canonical signed/trusted recipient projection to
`assemble_verified_cohort_wave`, with current suppression, last-contact
and sender/offer evidence. Review and approve a truthful offer/landing
page and then use the existing governed sender with a separately
authorised first wave. Feed actual delivery, qualifying responses,
click/site receipts, meetings and *verified paying customers* to the
existing campaign outcome resolver. Continue same-business-day review
of confirmed enquiries. Do not activate a new marketing automation
from this source-only build.

### Inspect current real pilot truth

```bash
cd /home/ubuntu/empire_worktrees/campaign_click_intent_bridge_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_tam_full_funnel_strategy_20261020 --read-only
```

Field groups: `real_buyer_contactability`,
`first_pilot_offer_creatives`, `launch_blockers`, plus the existing
market, campaign, experiment and outcome review. The CLI does not send
messages or write to EmpireDB.

## 20 October — Advanced evidence intelligence expansion

The continuing feature now has **three connected, pure owner APIs** in
`empire_os/campaign_intelligence.py`, imported by the existing
`scripts/review_tam_full_funnel_strategy_20261020.py` entry point.
No separate autonomous agent, DB, paid provider, message sender or website
tracking service has been created.

### 1. Cross-channel account signal fusion

`review_account_intelligence` and `review_private_account_portfolio`
consume **only authenticated, typed, owner-supplied** signals for the
existing market/tenant/account/campaign. Inputs distinguish:

| Evidence kind | Commercial interpretation | Action |
|---|---|---|
| Email delivered | Delivery only, NOT intent | No sales signal |
| Signed/verified link click | Weak interest; scanners excluded upstream | Internal review only |
| Consented website/offer visit | On-site context, not identity | Internal review only |
| Independently sourced company growth/procurement | Account research, NOT permission to contact anyone | Internal review only |
| Verified enquiry, social inbound or buyer question | Explicit first-party intent | Same-day owner review **if inbound response basis exists** |
| Pricing request / booked meeting | Explicit commercial engagement | Same-day owner review |
| Accepted terms | Commercial-process evidence | Terms owner review |
| Ledger-verified paying customer | Actual customer evidence | Existing-customer/finance owner review |
| Unsubscribe / hard bounce / explicit rejection | Hard negative | Stop and suppress |

Repeated same-day clicks/reloads are score-capped and cannot escalate
passive browsing into sales authority. Stale positive observations expire
while supported negative events block regardless of engagement. Wrong
tenant, campaign, event source, owner-recipient binding, provenance,
consent purpose, or altered replay **fails closed**. The numerical
evidence breadth score is **not** buyer probability, LTV, or revenue.

### 2. Real customer + gross profit offer learning

`evaluate_real_customer_experiment` evaluates the same three-offer/
10% no-marketing control design. It **correctly divides paying customers
by randomly assigned *accounts*** rather than deliveries, because the
holdout deliberately has no messages. It validates the four arms'
assignment integrity, closed windows, source-bound buyer/commercial
receipts, positive samples and per-arm denominators.

When independently verified financial receipts exist, it may compare
**realized gross profit per assigned account**, including negative
profit, instead of only response or customer counts. High complaint or
opt-out rates hold an arm even when conversion looks high. Missing
settled receipts, poor assignment integrity or small samples mean
**no commercial winner**. Differences are descriptive; significance,
causal lift, incremental ROI and automatic scaling are **not claimed**.

**Account-level randomisation improvement:** one eligible person per
company per market wave is counted in the experiment; any additional
same-company contacts are held. That keeps the *experimental unit* the
same across the offer engine and the money calculation, avoids
inconsistent offers being sent to coworkers and limits repeated
company contact. The current deterministic fallback uses an opaque
stable key; a verified role-ranked primary recipient must be chosen
by the canonical CRM owner for a real launch.

### 3. Funnel and next-best-experiment diagnosis

`diagnose_campaign_conversion_bottlenecks` reuses the existing
`empire_os.conversion_intelligence.ConversionStageEvidence` and
`review_stage` rather than building a second analytics engine.
Verified, campaign-attributed and window-closed source receipts can
show whether the current bottleneck is:

- offer/landing conversion,
- delivered-email-to-reply audience, offer or copy relevance,
- reply-to-qualified-conversation sales handling,
- offer proof / terms conversion,
- acceptance-to-payment checkout friction,
- or payment-to-fulfilment delivery readiness.

The output suggests a **controlled test for the existing owner**;
conversion rates without trustworthy denominators/source provenance
remain unknown. No automatic marketing, checkout, fulfilment,
pricing or budget decisions.

### 4. One connected API / no extra sidecar

`review_authenticated_campaign_intelligence` (in the original TAM
strategy script) allows CRM/Analytics/Finance to provide existing
authoritative projections, and returns a compact combined read-only
analysis. If an owner has not supplied a real receipt stream, the
corresponding review stays `null`: there is no fixture, dummy person
or invented positive conversion in the production CLI.

`recommend_next_real_execution_focus` prioritises the **actual**
current commercial blocker before choosing another development project.
Today the verified buyer-source snapshot says **0 validated outbound
contacts**, so the next real task for the existing Sales Director
is to obtain a small legal/permissioned, product-fit first-wave buyer
cohort, validate the primary buying roles and connect its governed
sender. Not another broad social scraper or analytics installation.

### More intelligence to develop *after* live source wiring

1. **Company decision-maker / buying committee ranker:** use the existing
   `outreach_account_strategy.build_buying_committee` for verified
   primary role and source evidence, respecting company-level contact
   limits. No inferred identities.
2. **Market signal knowledge graph:** attach fresh permits, search
   demand, published tenders, company expansion and public purchasing
   requests through existing source owners, with timestamp/role/source
   provenance and direct-buyer-intent separation.
3. **Creative/offer optimisation:** learn by verified sector and buyer
   pain, retain holdout, prefer recognized gross profit/LTV over clicks
   when real financial feedback exists, and monitor opt-outs.
4. **Cross-channel distribution:** organic search, videos, owned social,
   email and partner channels each with consent/permission and
   channel-specific measurement. Paid retargeting requires separate
   user permission and founder budget; `£0` remains the default.
5. **Actual revenue loop:** existing canonical buyer CRM, fulfilment and
   EmpireDB commercial ledger must send reconciled payment/margin evidence
   to the owner API before we can automatically recommend profitable
   allocation. A payment request, click or offered deal is not profit.

### Source and tests

```bash
cd /home/ubuntu/empire_worktrees/campaign_click_intent_bridge_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
 tests/test_campaign_intelligence_20261020.py \
 tests/test_tam_full_funnel_strategy_20261020.py \
 tests/analytics/test_campaign_click_evidence_20261020.py
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 -m scripts.review_tam_full_funnel_strategy_20261020 --read-only
```

Current CLI keys to inspect: `decision_intelligence`,
`next_real_execution_focus`, `real_buyer_contactability`,
`experiment`, and `verified_commercial_feedback`.

**Unchanged operational truth:** the source is an isolated build, not
merged to production, and no mail, click collection, visitor tracking,
ad audience export, payment, CRM or live campaign was executed.


## 20 October — Account buying-committee and safe next-commercial-play integration

This continuation extends **the existing** full-funnel intelligence contract,
rather than creating a new account graph or another sales agent. Source:
`empire_os/campaign_intelligence.py`; integration:
`scripts/review_tam_full_funnel_strategy_20261020.py`.

### Implemented

`review_account_buying_route` consumes a bounded, tenant-scoped,
**owner-authenticated** canonical account projection and its verified
cross-channel commercial signals. It reuses the established
`empire_os.outreach_account_strategy` functions for:

- `build_buying_committee` — prioritises evidence-backed buyer roles,
  with **verified contact route** taking precedence over a higher-ranking
  person whose contactability is unverified
- `choose_introduction_path` — chooses a genuinely verified,
  permitted warm partner/customer introduction over unsolicited cold outreach
- `evaluate_contact_fatigue` — enforces an account-wide single-contact
  30-day wave cooldown, including across email campaign variants

Personal names, company identities, contact records, source URLs and
event tokens are **not returned**. Input people and relationships are
bound to the exact account/tenant; timestamps, provenance, permission,
duplicate receipts and identity mismatches are validated strictly.
Opaque test references do **not** create live prospects or verified
buyers.

### Human-review play classes (no auto-send)

| Verified situation | Play |
|---|---|
| Genuine inbound pricing question or opt-in | Same-business-day existing-thread sales review |
| Existing, verified paying customer | Customer/relationship-owner review |
| Commercial terms already accepted | Existing commercial terms review |
| Opt-out, hard bounce or suppression | Stop and suppress |
| Contacted within last 30 days | Hold company-wide wave cooldown |
| Missing account, marketing permission or product proof | Hold and verify the missing evidence |
| Verified warm introduction available | Prepare an intro draft for existing owner |
| Verified contact in buying committee | Prepare one-contact/one-company offer draft |
| No verified buyer contact | Research; do not send |

`review_account_route_portfolio` aggregates these plays into an
identity-free Sales Director queue and rejects duplicate accounts.
`review_authenticated_campaign_intelligence` accepts an optional
`account_route_packets` owner interface. **No packets are fabricated or
loaded from a public spreadsheet.** If the CRM owner has not supplied
authenticated account projections, `account_buying_committee_routes`
stays `null` in the production read-only review.

### Engineering and business boundaries

- This is tested **source**, not production release. Do not represent
  a mock buying committee as a live Empire customer.
- Existing Sales Director and CRM remain the contact/identity and
  outreach owners. No duplicate contact creation, campaign enrollment,
  email sending, public website change, ad budget or CRM mutation.
- The buyer qualification snapshot currently reports **zero verified
  outbound-ready contacts**, so the immediately useful next step remains
  producing one genuine, lawfully contactable, offer-fit buyer cohort.
  A verified warm introduction or real inbound message may deserve
  human review but does not automatically grant sender authority.

Regression:

```bash
cd /home/ubuntu/empire_worktrees/campaign_click_intent_bridge_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_campaign_account_route_20261020.py \
  tests/test_campaign_intelligence_20261020.py \
  tests/test_outreach_intelligence.py
```


**Scoped research counts from the latest read-only buyer snapshot:** 23
shortlisted target records, including 7 tagged roofing, 1 solar and
1 HVAC; classification tags can overlap, are **not** independent TAM
market totals, and have no verified geography, permissioned
recipient, active buyer demand or send authority. The
`research_target_sectors` field exposes only aggregate sector coverage
from the current source. Source refreshes may change these figures.
None of the 23 target records is promoted to a live campaign list by
this build.

The immediate blocker is therefore especially concrete for the
founder-prioritised **UK solar buyer** segment: current research
coverage and permissioned buying contacts need genuine source
verification by the existing buyer scout and Sales Director owners.
The account route API is ready to evaluate the resulting authenticated
records; it does not authorise outreach on its own.

## 20 October — Intelligent learning across successive market waves

**This is an upgrade to the same TAM-to-paying-customer strategy**, not a
second predictive agent, CRM, database or email sender.

### What has been implemented

`empire_os/campaign_intelligence.py` now includes
`TrustedCampaignLearningWave` and
`review_multiwave_commercial_learning`. The full-funnel entry point
`review_authenticated_campaign_intelligence(..., learning_waves=...)`
accepts an authenticated in-memory owner projection when it becomes
available. With no real source connected, the output is **null**, not
an empty synthetic customer history.

It compares up to 12 independently evidenced waves of the *same*
tenant, region/sector, four-arm experiment and closeout policy.
Inputs must carry canonical, attested campaign receipts and support:

- a **10% no-marketing holdout** with approximately balanced offer arms;
  no email is delivered to the holdout
- paying customers **per randomly assigned company**, never
  per-click or per-delivery for the unsent holdout
- closed and sufficiently mature outcome windows, source freshness and
  verified experiment assignment/replay integrity
- verified cross-wave company-identity deduplication and market-cohort
  comparability, to prevent inflated experimental denominators
- per-wave customer-rate baselines; a materially different control
  rate holds pooled results for possible seasonal, market or source drift
- safety holds for opt-outs, complaints, overlapping waves, duplicate
  evidence keys, mismatched markets and contaminated experiment groups
- **realised gross profit** per assigned account, *only* when owner
  financial evidence is verified. Loss-making offers cannot be promoted
  as profit winners, even when click/reply/customer counts look positive.

Where all comparison evidence is valid, it reuses
`empire_os.predictive_intelligence._wilson_interval` with a more
conservative confidence setting to screen differences from the
contemporaneous holdout. It then **requires replication across at
least two comparable market waves** before proposing an offer to the
**existing causal experiment specialist** for human review. The
interval screen is *not* a significance or causal-lift claim.

### Learning states

| Evidence | Recommended next action |
|---|---|
| No authenticated receipts | Await genuine campaign/customer data |
| Only one clean market wave | Repeat a comparable, approved wave |
| Stale, duplicate, mismatched or contaminated evidence | Repair source/assignment before making claims |
| Control group changes materially | Review market and instrumentation shift |
| Consent complaints or opt-outs deteriorate | Hold campaign expansion and review safety |
| Repeated offer advantage and finance evidence | Human causal and profitability review |
| Verified realised losses | Review margin before recommending any expansion |

### Integration + scope

The existing read-only CLI stays:

```bash
cd /home/ubuntu/empire_worktrees/campaign_click_intent_bridge_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_tam_full_funnel_strategy_20261020 --read-only
```

The returned `decision_intelligence.multiwave_campaign_learning`
remains `null` until the existing CRM, send and finance owners supply
**actual authenticated account-level event/outcome projections**.
Synthetic fixtures live only in
`tests/test_campaign_multiwave_learning_20261020.py` and do not imply
live conversions, simulated production success, or revenue.

**No external messages, retargeting, public tracking, new cron jobs,
model retraining, audience export, budget movement or production deploy.**
Output is recommendation-only and evidence-provenance bounded.


## 20 October continuation — Adaptive buyer journey, channel and offer intelligence

**Implemented within the existing campaign intelligence owner** rather than
creating another CRM, automation scheduler or buyer agent.

The two compositional APIs in `empire_os/campaign_intelligence.py` are
`review_adaptive_buyer_journey` and
`review_adaptive_buyer_journey_portfolio`. They reuse these pre-existing
EmpireOS owners:

- `revenue_crm_journeys.preview_crm_journey` for the real canonical CRM
  lifecycle (engaged conversation, proposal, awaiting payment, fulfilment,
  contact hold). A stage is never a payment or consent receipt.
- `revenue_crm_channel_evidence.review_channel_evidence` for separately
  authenticated, tenant-and-prospect-bound email, SMS and web-push consent,
  canonical suppression, proof freshness and provider authority.
- The owned campaign buying committee, same-day signal review, company
  cooldowns and multi-wave customer/profit experiment learning.

**Information boundaries:** CRM UUIDs and opaque campaign account identifiers
are distinct identity systems. The canonical CRM owner must attest their exact
join before this adapter will use either. Unknown/stale source joins hold
rather than silently matching a domain or email address. No names, emails,
recipient tokens, company identifiers, case IDs or original CRM records are
returned. Aggregate portfolio views block repeated account or canonical
CRM prospect identity across records.

**Example stage choices, all owner-review only:**

| Evidence-backed stage | Recommended internal play |
|---|---|
| Unsubscribe, suppression or CRM contact hold | Stop contact |
| Existing customer evidence | Customer relationship review |
| Canonical order under fulfilment | Fulfilment owner review |
| Canonical case awaiting payment | Payment-status owner review; do not invent a payment |
| Canonical proposal ready | Proposal / terms review |
| Verified buyer enquiry or engaged CRM conversation with reply basis | Same-business-day sales conversation review |
| Verified and permitted partner introduction | Warm-intro preparation for human review |
| Fit and buyer route verified, channel consent/suppression reviewed | Review one offer experiment with the existing sender owner |
| Missing consent, identity, contact basis or sources | Hold, or internal account research |

**Channel and timing decisions:** Each channel requires its own fresh
authenticated first-party opt-in and a matching suppression check. A legitimate
email opt-in does **not** become SMS or push consent. A verified inbound
conversation may merit human same-business-day review without authorizing
a separate marketing subscription. A first-touch offer may only be proposed
for owner review where the channel evidence preconditions are present;
there is still no send authority. Global suppression removes any apparent
preferred outbound channel. Timing is an owner-review priority, never a
scheduling instruction.

**Offer adaptation:** A replicated profitable offer outcome from the existing
multi-wave engine is exposed only as a candidate for existing-owner causal
review, not an automatically selected creative or swapped experiment arm.
Missing learning receipts, small/incompatible tests or financial losses cannot
train a fictitious winner. No autonomous nurture sequence is activated.

`review_authenticated_campaign_intelligence` now accepts optional
`adaptive_journey_packets` and shares the same authenticated learning
wave input with both engines. No real connector means
`decision_intelligence.adaptive_buyer_journeys = null` in the current
read-only report; never manufacture counts.

**Verification:**

```bash
cd /home/ubuntu/empire_worktrees/campaign_click_intent_bridge_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_adaptive_campaign_journey_20261020.py \
  tests/test_campaign_account_route_20261020.py \
  tests/test_revenue_crm_journeys.py \
  tests/test_revenue_crm_channel_evidence.py
```

**Still excluded:** production sender/provider configuration, real buyer
acquisition by this owner, paid traffic, publishing, public tracking, lead
admission, customer billing, automatic subscriber enrollment and changes to
another agent's CRM/Finance source files. Live buyer verification remains
assigned elsewhere, as directed by the founder.


## 20 October — REAL EmpireOS observer connections (no mock production outcomes)

This is the first **live source-level integration** into the existing
full-funnel command, not an additional analytics application. The
`review_authenticated_campaign_intelligence` entry point now accepts
`observer_snapshots`; the original read-only CLI automatically loads
six **existing production-owned observer snapshots** from hardcoded
EmpireOS runtime paths using `read_real_commercial_observers` and
reconciles them with `review_real_commercial_observers`.

| Existing observer | Live integration | Interpretation |
|---|---|---|
| Next-Best Action | Connected, freshness checked | Existing human/operator actions, NOT contact permission |
| Account/Buyer Digital Twin | Connected with stale-data hold | Historic identity/history preview; NOT independently recognized money |
| Consent/Outcome Linkage | Connected, source-governance checked | Globally linked event records; NOT equivalent to campaign customers |
| Campaign Output/Outcome | Connected, independent linkage check | Verified output-quality counts, separate from payments and revenue |
| Campaign Measured Outcomes | Connected, independent linkage check | Exact campaign outcome links, must agree with output observer |
| Orders/Payments/Revenue control | Connected, source-governance checked | **Payment evidence only for the observed control population**, not an Empire-wide sales census |

The existing TAM, message optimiser, owned asset/campaign runtime
and buyer qualification/relationship snapshots remain in their
original read-only adapters. This additional reconciliation avoids
duplicate readers and does not change another department's source
files, database schema or service endpoint.

### What was actually observed on 20 October

The connected runtime observations contained **two** existing
Next-Best Action recommendations: one internal decision-maker
verification and one internal research review. **Five** campaigns
had output-quality evidence; the independently observed
**exact campaign outcome match count was zero**. The global
consent/outcome observer recorded **eight linked event records**
from `public.outbound_intents`; these are **not recognized
revenue, fulfilled buyers or paid customers**. The checked
order/payment control population contained zero current transaction
rows and no observed real payment in *that population*. The older
Account Digital Twin snapshot, from **1 October 2026**, was
held as stale instead of being used for current buyer decisions.

These are snapshot observations, not guarantees that no other
sales or payments exist elsewhere in the company.

### Hard boundaries of this connection

- Reader only accepts six fixed allowlisted paths, bounded JSON
  size, known schemas, OBSERVE mode, freshness and non-world-writable,
  non-symlink files. Other files and source content are never searched
  to fill gaps.
- A malicious or incompatible source, count mismatch, stale clock,
  unauthorized execution flag or disagreement between campaign
  observers returns a **hold** and unknown outcome, never a positive
  customer claim.
- No company, contact, prospect, thread, event identifier, source
  raw row or private CRM name is exported. Only coarse counts and
  approved internal action classifications are returned.
- The actual per-tenant Revenue CRM HTTP API requires its
  authenticated dedicated tenant repository. This independent
  command is **not** granted that authentication. Consequently
  `decision_intelligence.adaptive_buyer_journeys` and
  `decision_intelligence.multiwave_campaign_learning` remain null
  until their existing data owners provide authenticated
  `adaptive_journey_packets` and closed-window `learning_waves`.
- The typed journey/channel adapter is built and tested. Claiming
  arbitrary JSON, website clicks or snapshots as a CRM identity join
  is specifically prohibited. The other Sales Director/buyer agent
  retains responsibility for authenticating the account routes.
- No live marketing dispatch, sender reconfiguration, user-tracking
  endpoint, audience export, publisher enrolment, finance mutation
  or database write was performed.

### Read the live evidence

```bash
cd /home/ubuntu/empire_worktrees/campaign_click_intent_bridge_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 -m scripts.review_tam_full_funnel_strategy_20261020 --read-only
```

The evidence is inside `decision_intelligence.real_existing_source_connections`.
An exact consumer should check every field in `source_health` and
`source_holds` before acting; this remains an **operator-review API**
rather than a new sender or authorization source. Regression tests:
`tests/test_tam_real_observer_connections_20261020.py`.


## 20 October — Existing authenticated tenant Revenue CRM handoff

The same campaign intelligence module now exposes
`review_authenticated_crm_campaign_handoff` and the existing
`review_authenticated_campaign_intelligence` accepts
`authenticated_crm_owner_read`, `account_projection_owner` and
`signal_owner`.

This deliberately **reuses** the existing
`revenue_crm_api.AuthenticatedRevenueCrmRead` and
`revenue_crm_transport.PostgresRevenueCrmRepository`:
the CRM owner must first authenticate the tenant through the existing
HTTP/server resolver, which enforces a dedicated database login,
read-only SQL, tenant-bound RLS and role checks. We never create or
obtain a new database credential in this build.

The new adapter calls only `repository.prospects(limit=...)` for at
most 500 rows, verifies each tenant/prospect UUID, deduplicates
prospects and passes each row to a **trusted owner-controlled canonical
account join**. Missing source-attested joins are counted as held;
no contact identity is guessed from a name, company, email, domain,
AI content or website click.

The owner must also provide actual verified signal receipts. The
result runs through the existing adaptive journey, channel-consent
and sales-review logic. Any changed CRM stage, altered UUID,
cross-tenant record, bogus permission, duplicate prospect or
unauthenticated repository is rejected before commercial learning.
The adapter returns **only counts and internal next actions**.

The existing standalone read-only CLI has no authenticated tenant
principal, so its
`decision_intelligence.authenticated_tenant_crm_handoff` remains
`null`; this is not a connection failure or zero CRM buyers.
The callable owner-integration path is implemented and tested, but
actual production tenant reads must be invoked by the Revenue CRM
owner's authenticated request/service workflow. No other agent's
CRM API/router files have been modified or deployed.

**Source tests:** `tests/test_authenticated_crm_campaign_handoff_20261020.py`.

**No new database role, credentials, tenant bypass, unapproved send,
nurture schedule, spend, automatic marketing subscription or payment.**


## 20 October — Buyer-value-first conversion intelligence

**Commercial objective:** become easier to say yes to by demonstrating real
relevance, verifiable capability and low-friction next steps. Do not pressure
people with false urgency, invented savings, made-up ROI or unsupported
personalized "pain." The user-approved commercial rule is
**rapport and useful value first; introduce a sales CTA only after
a genuine verified buyer request or other independently authenticated
commercial intent**.

This release extends the existing `empire_os/campaign_intelligence.py`
owner with `review_buyer_value_first_offer` and an aggregate
`review_buyer_value_first_portfolio`. The first-party source adapters
are built into the **same** `review_authenticated_campaign_intelligence`
entry point through optional `value_case_packets` and
`value_case_owner` (from the existing tenant-authenticated Revenue CRM
handoff). There is no new CRM, outbound worker, sender, scheduler or agent.

### Offer fit, proof and actual delivery

| Buyer-stated problem | Three-arm campaign value offer | Required matching current source |
|---|---|---|
| Buyer needs supply and territory/acceptance fit | A buyer inventory-fit check | Canonical inventory acceptance and available supply proof, no older than 7 days |
| First-party evidence of demand-to-response leakage | Measured response/coverage opportunity check | Verified analytics or conversion bottleneck evidence, no older than 30 days |
| Buyer asks which market or territory to prioritise | Bounded territory evidence brief | Verified public market source and limitations, no older than 30 days |

A matching account/tenant/market source receipt is required. The
**buyer must have actually stated the problem** in a fresh canonical
CRM record; a site visit, company growth observation, search result
or AI-inferred need does not pass. Proof must confirm current
deliverability and market fit. All source timestamps, source types and
evidence identifiers are validated before an offer can be suggested.
A product requiring paid commercial terms additionally uses the existing
`commercial_offer_book.product_ready` readiness check.
**No price, guaranteed outcomes or revenue claims** are inserted by
the suggestion engine, regardless of whether a catalog item is ready.

### Value/rapport before CTA

The selector produces a private owner-review brief containing:
the buyer problem category, supported offer arm, scoped sample/value
deliverable, independently checked source status, one verified
buying objection/risk resolution (if stated) and the next controlled
experiment. It reuses `gtm_offer_strategy.build_demo_asset_plan`
for a bounded evidence-led screen-demo outline. **The video is
planned, not rendered or published.**

The decision states are:

- **Research buyer need** when no first-party buyer problem exists.
- **Verify proof or fulfilment** if supply/capacity, market match,
  approved paid product or evidence recency is missing.
- **Prepare proof-first brief, no sales CTA** for a real buyer need
  and real source-backed deliverability but no buyer request.
- **Same-day response with value, then review a CTA** only after a
  verified buyer question, pricing request, appointment or similar
  authenticated direct inbound evidence and lawful response basis.
- **Stop and suppress** immediately on account suppression, opt-out
  or a verified do-not-contact signal.

The value brief is also composed into
`review_adaptive_buyer_journey(..., buyer_value_case=...)`,
so it cannot appear as an aggressive acquisition recommendation
beside an existing customer's fulfilment, payment, contact hold
or CRM stop state. The authenticated CRM adapter enforces that the
value case and account share an exact canonical identity.

### What this does and does not do

This is real, test-backed business decision software. It prepares
a stronger, evidence-led commercial conversation and a useful sample
to show the buyer. It **does not** create the inventory, run the
advert, fabricate a verified buyer conversation, send the
email, launch a site, manufacture ROI or move a prospect through
a payment stage. It operates only where existing sources provide
authenticated, tenant-bound first-party evidence. The current
production read-only CLI has no tenant CRM principal; therefore
`decision_intelligence.buyer_value_first_offer_review` remains
`null` until the source owner supplies that evidence.

Tests are in
`tests/test_campaign_buyer_value_first_20261020.py`,
`tests/test_adaptive_campaign_journey_20261020.py` and
`tests/test_authenticated_crm_campaign_handoff_20261020.py`.


## 20 October — Private proof-backed offer experience renderer

**Scope:** The campaign-intelligence owner now builds actual **offline,
review-only HTML offer experiences** from trusted, source-attested
`TrustedBuyerValueCase` evidence. Website publishing, design, domain
routing, legal copy, tracking, analytics, lead forms and brand deployment
remain with the existing flagship website and consent owners. Nothing
has been installed into their worktrees or into the live website.

### Implemented source

`empire_os/campaign_intelligence.build_private_buyer_offer_experience`
reuses `review_buyer_value_first_offer` and the existing
`gtm_offer_strategy.build_demo_asset_plan`.

For a genuine canonical buyer problem and a matching current
verified/deliverable capability, it returns:

- a complete, **self-contained responsive HTML5 preview** with
  editorial design, no external scripts, tracker or network dependency
- a relevant offer story and buyer-language headline
- a three-step evidence-review journey, anchored in exactly the
  market and commercial problem proven by the source
- clear FAQ and buyer friction/objection text, but only for a
  *documented* buyer concern
- a 3-minute storyboard split into three 60-second segments,
  each with a concrete proof surface that the owner can demonstrate
- a **proof review date**; inventory evidence older than 7 days
  and other offer evidence older than 30 days are held
- a next-step recommendation that explicitly does not send,
  quote, enrol, publish or bind the buyer

The preview has `noindex,nofollow,noarchive`, a restrictive
local-only CSP and **no form, CTA URL, marketing pixel,
cookie, outbound email, auto-follow-up or interactive purchasing
button**. Its content never includes company/contact identity,
private CRM case data, opaque proof IDs, source URLs, invented
inventory quantities, financial claims or customer testimonials.

### Acceptance / abstention

`HOLD_NO_SUPPORTED_PUBLIC_FACING_VALUE` is returned, with
`private_html=null`, when the canonical buyer problem is absent
or not genuinely buyer-stated, when the matching value has no
current verified delivery proof, or when the account is suppressed,
unverified or cross-tenant. In particular, a public permit/hiring
signal, a click or a sales score is **not** a verified buyer problem.

Only source-grounded proposals can generate an operator preview.
The selected offer has to match the stated need exactly; the
existing commercial product-book check rejects unapproved paid
catalog promises.

### Owner handoff

The original `review_buyer_value_first_portfolio` and
`review_authenticated_crm_campaign_handoff` now include
`proof_first_private_page_candidate_count`: a privacy-safe **count
of source-backed candidates**, not a published page count.
When the existing CRM owner supplies an authenticated tenant
read, a canonical account join and authenticated value evidence,
that owner can call the renderer directly for an individual
review case, inspect the produced HTML and hand it to the
flagship website team.

**Publication prerequisites remain separate:** actual approved
first-party landing route, current source-publication rights,
privacy and consent wording, approved site design, security
headers, tested functional CTA, founder/business sign-off and
campaign evidence attribution. This code does **not** turn
private previews into active websites or take over those owners.

### Verification

```bash
cd /home/ubuntu/empire_worktrees/campaign_click_intent_bridge_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
 tests/test_campaign_buyer_value_first_20261020.py \
 tests/test_authenticated_crm_campaign_handoff_20261020.py \
 tests/test_adaptive_campaign_journey_20261020.py
```

The real CLI continues to print `null` for buyer-value and CRM
per-contact owner projections until authenticated receipts exist.
This is truthful proof of **readiness without manufacturing conversions**.


## 20 October — Prospect questions and actual first-party conversion journey

**Founder insight:** Before asking a prospect to buy, check whether the
offer answers the questions already in the buyer's mind: relevance,
deliverable, proof/trust, business value, price and risk, delivery
timing, differentiation, and next step.

### What the source-grounded page currently answers

`review_prospect_question_coverage` runs on the **existing**
`review_buyer_value_first_offer` proof and is included in
`build_private_buyer_offer_experience`, not a second offer generator.

| Prospect question | Readiness of a currently verified private proof preview |
|---|---|
| Is this for my business? | Answered at **review** level only; individual buy box still needs confirmation |
| What will I initially get? | Answered at review level by the sourced proof-first brief |
| Can I trust these claims? | Partial: capability source date and limitations are available; no independently substantiated customer case study |
| Will it improve business outcomes? | Partial: practical decision usefulness explained, no measured ROI or lift |
| How much will it cost and what is the risk? | **Open:** commercial catalog/terms owner must verify price, exclusions, acceptance and cancellation terms |
| How soon will it be delivered? | **Open:** fulfilment owner must verify capacity and timeframe |
| Why Empire AI? | Partial: explain evidence-first method without invented competitor advantage |
| What exactly is the next step? | **Open for these new proof assets:** website owner must publish an approved form/CTA and confirm it works |

This is **2 review answers, 3 partial and 3 outstanding owner questions**.
The eight actual questions and honest answers now appear in every
generated private proof page. No claim that the page is publication-
or conversion-ready is made.

### Genuine first-party site path — verified

Existing website owner code is **already deployed**, with routes:

- `GET /research/{campaign_id}` — released, immutable campaign page
- `GET /research-runtime.js` — owned first-party runtime script
- `POST /api/research/enquiry` — exact campaign/asset-bound enquiry;
  same-origin, size/rate-limit and canonical EmpireDB intake protections
- `POST /api/research/event` — separately bounded organic campaign events

The currently signed site release validates **five** research paths
through `owned_campaign_release.load_release`. A read-only HTTP
GET to `https://empire-ai.co.uk/research/campaign_3438b6c3b110f941407ce1dd`
on 20 October returned **200 HTML**, a form action at
`/api/research/enquiry`, the existing expected fields and the
explicit **not a marketing subscription** privacy notice.
A HEAD request on the POST-only enquiry route returned **405**, as
expected for an unsupported method; **no enquiry POST** was made.

This live finding is independent of the new offer preview. The new
private value-first pages are **not published on any of those five
routes**, and no new production conversion claims were inferred.

The read-only full-funnel CLI now includes
`existing_first_party_research_release` with these verified
release counts (HTTP is intentionally a separate observation).

### Exact source-bound enquiry → CRM → order → money

The **existing campaign intelligence owner** now exposes:

- `review_released_research_route`: independently validates the
  signed, immutable website release, exact campaign and landing
  asset ID, existing privacy text and zero automatic outbound
- `reconcile_first_party_conversion_journey`: re-reads that
  unchanged release and joins **canonical reader-owned receipts**
  through first-party enquiry acceptance, an authenticated tenant
  CRM/prospect binding, a verified settled payment and fulfilment,
  a separate revenue-recognition event, and verified actual costs

Typed input contracts: `TrustedResearchEnquiry`,
`TrustedResearchCrmAttribution`,
`TrustedResearchCommercialOutcome`.

An enquiry is **not** a buyer. A CRM prospect is **not** a sale.
A paid order is **not** recognized revenue. Recognized revenue is
**not** verified gross profit when independently evidenced costs
are absent. Attribution needs exact campaign/asset/receipt/tenant/
prospect/order linkage with chronological source records. Duplicate
enquiries, duplicate orders, mismatched tenant IDs and spoofed
paid/delivery values are rejected. Results disclose **only aggregate
counts and cents**, not contact or payment receipt IDs; no causal
advertising lift is asserted.

This bridge is available from the same
`review_authenticated_campaign_intelligence` API using the optional
website release root, source enquiry receipts, authenticated CRM
links and Finance-owner outcome receipts. These are *owner-attested*
typed data projections, **not arbitrary browser JSON** and not a
new route for accepting payments or declaring source authenticity.
The source-owning teams must verify their own ledger, principal,
settlement, fulfilment and accounting custody before passing
any "verified" flags. A closed Finance receipt window is also
owner-supplied; this function cannot independently assert it.
When receipts are not connected, the current live CLI returns
`null` for those figures, not fake customers or zero profit.

### Owner pickup / same-system integration

**Existing flagship/website owner:** Review the new private
source-backed offer experience and eight buyer questions. Resolve
specific missing approved terms/fulfilment facts, integrate only
approved HTML/copy into their own existing public site release, and
test the existing same-origin enquiry route, privacy text and
submission receipt. Do not overwrite existing home page or
campaign release, and do not publish unverified claims.

**Existing Revenue CRM owner:** Read a real `owned_campaign_enquiries`
receipt using its approved reader, authenticate the tenant CRM
prospect, and pass only an independently proven exact linkage.
A submitted email/domain is insufficient to manufacture an
account join or opt-in.

**Existing Revenue Pulse / Finance owner:** Supply actual canonical
settlement, delivery and recognized-revenue events plus actual
cost receipts and a closed outcome window. The campaign intelligence
owner does **not** query Finance under a privileged identity,
recognize revenue, initiate a refund or move funds.

**Campaign intelligence owner (this branch):** Consume those
independent receipts, compute privacy-safe funnel and realized
margin diagnostics, adapt the proof-first experience where actual
buyers demonstrate friction, and maintain attribution unknown
until a verifiable causal lineage exists.

### Runtime and tests

```bash
cd /home/ubuntu/empire_worktrees/campaign_click_intent_bridge_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 -m scripts.review_tam_full_funnel_strategy_20261020 --read-only

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
 tests/test_campaign_real_conversion_journey_20261020.py \
 tests/test_campaign_buyer_value_first_20261020.py \
 tests/test_owned_campaign_runtime.py
```

Live posting, website deployment and payments were **not** exercised.
All fabricated fixture email/UUID/payment rows are isolated to
tests, never written into production CRM, buyer or finance.

## 20 October continuation — Conversion owner release board, live catalog and held SEO aggregate

The existing research form routes, public site, catalogue, Sales Director,
CRM and Finance remain with their **existing assigned owners**. The campaign
intelligence code now reuses those source contracts and produces one
machine-readable, zero-PII handoff instead of another CRM, SEO probe,
offer catalog, or payout ledger.

### Verified live-source findings

- The current immutable first-party research release identifies **five
  signed /research/campaign_* pages**. Earlier live HTTP verification
  confirmed a working HTML form structure pointing to /api/research/enquiry.
  This is not evidence that the new value-first pages were published.
- The commercial catalog snapshot from 20 October 12:50 UTC projects
  **86 products, 35 active, 26 verified for commercial terms**, checked
  independently through the existing commercial_offer_book.product_ready
  function. These are catalog readiness counts, not buyer-specific
  product matches, published prices or verified delivery dates.
- The existing SEO research-enquiry count-only operator is held for an
  authorised privileged database owner. Its unprivileged invocation
  currently returns AUTHORIZED_LOCAL_READONLY_OPERATOR_REQUIRED. We
  did not elevate privileges, query the private table or report zero
  enquiries from an inaccessible source.
- The new aggregate adapter accepts the original count-only observation
  only when the authorised owner attests a fresh run (under 24 hours),
  with consistent receipts, verified privacy holds and no contact
  disclosure. Browser page views and CTA clicks are event counts, NOT
  unique visitors, buyer identities, lead conversion percentages or sales.
- Authenticated enquiry-to-CRM linkage, settlement, recognised revenue
  and actual cost receipt joins remain unknown until their owners provide
  real evidence.

### Scoped existing-owner actions

1. Flagship website owner — review, legally approve and publish the
   proof-first experiences through the EXISTING first-party form
   and immutable release path, with accurate claims and consent.
2. Commercial catalog and fulfilment owner — approve exact buyer-offer
   contract, risks, price/scope, acceptance criteria and realistic
   turnaround; the 26 verified catalog products are not blanket
   fulfilment or publication approval.
3. SEO/database owner — run the already-existing privileged count-only
   research intake observer when authorised. Do not expose contact rows.
4. Tenant CRM/Sales Director owner — authenticate exact enquiry receipt,
   prospect identity, reply basis and consent; do not match by an email
   address or domain guess.
5. Finance/Revenue owner — reconcile settled orders, fulfilment,
   recognised money movements and actual costs with a closed financial
   event window. A payment is not profit.

### Read-only command for other owners

    cd /home/ubuntu/empire_worktrees/campaign_click_intent_bridge_20261020

    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
      -m scripts.review_tam_full_funnel_strategy_20261020 \
      --read-only --owner-board

The original --read-only command remains intact with the board nested
in its JSON response. This does NOT automatically send owner messages,
assign work, move funds, grant DB permissions, merge branches, or deploy.
Tests: tests/test_tam_conversion_release_owner_board_20261020.py.

**Production completion still requires** an approved proof experience
published by the website owner, a genuine enquiry in canonical intake,
an authenticated CRM join, and independently verified finance and
fulfilment evidence. Current branch readiness is code-tested and
source-audited, NOT a paid customer or a completed deployment.

## 20 October — Production research-site QA and exact signed product mapping

**Verified by read-only HTTP GET**, no forms submitted or tracking
events deliberately posted. All five pages returned HTTP 200,
each with precisely one form using POST /api/research/enquiry,
the expected six field names, the owned /research-runtime.js script
and the notice that a research enquiry is not a marketing subscription.

The independently signed releases are:

| Published research subject | Objective | Catalog mapping |
|---|---|---|
| Denver roofing coverage gap | Research enquiry | No product claim |
| Atlanta class-action research | Product enquiry | managed_service — matching product terms currently verified |
| NYC general-contractor evidence chain | Research enquiry | No product claim |
| Dallas–Fort Worth HVAC opportunity pilot | Product enquiry | managed_service — matching product terms currently verified |
| Denver HVAC acquired-records research | Research enquiry | No product claim |

Only the *existing signed page metadata and catalog readiness* support
the two exact product matches. This does not prove buyer need,
source publication rights, fulfilment capacity, exact approved
price disclosure, or conversion. The newly generated private
proof experiences for GB solar are **not** published on those
US research routes; no automatic product-to-offer substitution
is allowed.

The existing read-only owner-board CLI now includes
website.product_enquiry_pages_with_verified_catalog_terms and
website.research_only_pages_not_product_offers to catch future
misalignment between the signed page objective and the verified
commercial catalog. Duplicate product codes, incorrect paths,
missing product terms and stale/untrusted source snapshots fail
closed. The source-owned pages, deploys, CRM, Finance and buyer
data are untouched.

**Next owner action:** Existing flagship website owner should
review the private proof-first experience and approve a distinct
publication route (or deliberately revise an existing signed campaign)
only after product/fulfilment/legal source approval. Existing
CRM/Finance owners must independently verify real enquiry
and payment receipts. No live POST, public deploy, payment, or
customer contact occurred in this review.
