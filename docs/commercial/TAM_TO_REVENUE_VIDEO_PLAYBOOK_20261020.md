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
   per eligible email delivery. Supporting metrics: verified website
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
  The current read-only production evidence contains **23** shortlisted
  buyer targets, **261** researched/existing relationships and **0**
  contacts confirmed for outbound in the buyer qualification source.
  Permitted-email recipient count is **unknown**, not 23 or 261.
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
