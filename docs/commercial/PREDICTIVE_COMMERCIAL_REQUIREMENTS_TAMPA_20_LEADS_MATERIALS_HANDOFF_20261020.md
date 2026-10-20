# EMPIRE AI — Commercial Requirement, Predictive Lead Fulfilment & Material Sourcing

**Date:** 20 October 2026
**Owning worktree:** `/home/ubuntu/empire_agents/predictive_decision_control_20261018`
**Mode:** OBSERVE / RECOMMENDATION ONLY — isolated feature, **not deployed**
**Founder example:** Tampa FL roofing company requests **20 qualified leads plus competitive material sourcing**.

## Actual code ownership map inspected

| Existing owner | Existing component/source inspected | Predictive consumption, not duplication |
|---|---|---|
| Predictive Intelligence | `empire_os/predictive_intelligence.py` | Reuse product/market estimates only as existing evidence where properly scoped; no second forecasting worker |
| Predictive Cloud | `empire_os/predictive_cloud_scenario_optimization.py`, `empire_os/predictive_cloud_fabric.py` | Reuses original scenario compiler for **explicit shadow-only** owner assumptions; no production optimizer run or allocation |
| Buyer Scout | `runtime/buyer_acquisition/scout_latest.json`, Buyer Demand Graph `empire_os/buyer_demand_graph.py` | Research counts are **not** buyer contracts or accepted lead capacity; read-only |
| Buyer Capacity | `runtime/buyer_capacity_readiness/latest.json` | Existing owner activation, terms, verified capacity and allocation gates |
| Lead Supply | `/home/ubuntu/empire_worktrees/lead_supply_intelligence_20261019/empire_os/lead_supply_intelligence.py`; `runtime/lead_supply/private_leadgen/research_queue_latest.json` | Existing collector/qualified prospect/inventory boundary; no parallel supply collector or transfer |
| A2A Commercial Signal Miner | `/home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020/docs/commercial/A2A_BUYER_SCOUT_SOURCE_OWNER_HANDOFF_20261020.md`, reported commit `08e33378` | Adopts target-specific niche/location owner-task *draft* semantics, **no A2A delivery or trusted external agent assumed** |
| Marketing/SEO/Campaigns | Existing authorised market/source/campaign owners | Research permitted channels only; no ads, SEO publish or budget authority |
| Lead Smart | `empire_os/lead_smart_predictive_revenue_adapter.py` | ZIP coverage and payout priors are not a guaranteed payment, payable probability or accepted billable lead |
| Procurement/Supply | `empire_os/data_exchange_procurement_context.py` and existing Material/Finance source custody | UK public tender OCDS is not a Tampa US supplier quote or purchase-ready material list |
| Finance OS | `enterprise_finance_evidence_readiness.py`, `predictive_four_stage_economic_custody.py` | Actual supplier/job expenses, contracted prices, paid settlement, refunds remain independently unverified |
| Quant/Economic Memory | `original_conversion_registry.py`, `predictive_original_profit_forecast_preflight.py`, `economic_memory.py` | Original prediction-before-outcome registration and authenticated cohort outcome remains open; **no fake calibration or cash receipts** |
| Canonical Revenue Reader | `/srv/empire_os/empire_os/predictive_revenue_canonical_reader.py` | Exists in production but not in isolated feature tree; **not invoked or rewritten** by this integration |

**No changes were made to these source owners.** Canonical source releases, live source provider authenticity, licence, role and tenant permissions stay with the existing owners.

## New implementation

### 1. Structured commercial requirement — `empire_os/predictive_commercial_requirements.py`

Normalizes an exact customer/founder *intent* as a typed contract. It stores country/state/city, typed industry and service requirements, ZIP/postcode list, customer target (20), delivery deadline/cadence, accepted event types, explicit valid/billable lead class, shared/exclusive terms, contracted minor-unit budget, price/accepted lead, replacements/refunds, tenant/company opaque original refs, purchasing/consent owner receipts, service capacity and material-spec owner receipts.

Absent information remains **null, `unconfirmed` or an explicit open proof gate**. The Tampa founder example does **not** self-certify customer identity, budget, 20 available leads, original consent, ZIPs, service specifications or roofing measurements.

The requirement gets a deterministic revision SHA256 and draft idempotency key. A repeat produces the same key; a changed target/terms produces a different revision. The key is **not** a durable commercial customer ID, authenticated tenant scope or signed A2A admission token.

The contract also handles other industries (HVAC, solar, construction, insurance, agencies, data brokerage, services, software), US states and GB regions, with country-specific postal/currency checks. For non-roofing work, product/material scopes remain generic or industry-specific until the original product/operational owner supplies requirements.

### 2. Authentic live source readiness — `empire_os/predictive_commercial_supply_readiness.py`

Reads three **existing** source-owner aggregate snapshots only. Validates source schema, OBSERVE/read-only authority, bound integer counts and owner freshness (48h); **never reads private lead/contact rows**, never enumerates personal contacts and never writes/contacts buyers.

Readback (source snapshots on 20 Oct 2026):

| Source claim | Verified observation | What this does NOT mean |
|---|---:|---|
| Founder customer target | 20 qualified leads | Not 20 available leads or signed purchase |
| Lead Supply roofing sector research records | **56** | Not Tampa-specific consumer enquiries, billable leads or delivery inventory |
| Lead Supply canonical selected inventory *research* records across sectors | **175** | Not 175 ready for sale |
| Lead Supply immediately sellable inventory **across checked source** | **0** | Not proof no roofing demand exists in Tampa |
| Lead Supply verified global buyer capacity (count) | **0** | Not the company's verified capacity to handle 20 jobs |
| Buyer Capacity: canonical buyer records observed | **1057** | Not 1057 committed paying buyers |
| Buyer Capacity: verified capacity buyers / terms / activated | **0 / 0 / 0** | No approved delivery, payout, buying role or terms established by this review |
| Buyer Scout research candidates | dynamic (varied as source owner refreshed) | Not evidence of a customer order or signed capacity |
| **Authenticated Tampa-qualified available leads** | **UNKNOWN / null** | Can't subtract 0/56 from 20 and call it a proven shortfall |

If original source becomes stale or changes execution authority, the corresponding values revert to **unknown** rather than a fabricated zero. An aggregate inventory source *never* allows a Tampa ZIP, lead exclusivity, consent or customer-match claim without a source-owner canonical per-lead readback and duplicate check.

### 3. Governed Tampa lead fulfilment plan

`empire_os/predictive_commercial_fulfilment.py`

Emits an explicit `INSUFFICIENT_EVIDENCE_NOT_READY_TO_PROMISE_OR_FULFIL` plan with:
- target 20, verified Tampa deliverable inventory `null`, independently proven lead deficit `null`;
- Lead Supply source research counts plus unverified capacity; no promise to deliver 20;
- possible source-permitted channels for existing Marketing/SEO/Inbound/Partnership owners, but no campaigns or contact orders;
- accepted/billable lead definition, ZIP, customer authorisation, exclusions, exclusive/shared payout, budget, due date and replacement rules **awaiting original customer/company owner**;
- requested original A2A/Buyer Scout/Lead Supply owner reviews prepared but **not dispatched**.

### 4. Preliminary roofing procurement / RFQ

The sourcing plan covers **roof covering systems, waterproofing/underlayment, flashing, ventilation/ridge accessories, fasteners, optional insulation and delivery/freight**. It refuses to produce a quantity or supplier-price estimate without real measured roof area/pitch, surface/roof type, local wind/fire/code/permit and original specification. No project is assumed merely because 20 leads are requested.

Optional owner-supplied project surveys require stable source/project digests; their measurements remain **unverified claims**, not signed professional estimates. Optional supplier owner quote rows require original opaque supplier/quote/project IDs, USD/GBP source match, original observed time (<=30 days), exactly stated cost/freight/tax/delivery, duplicate quote rejection and no authenticated purchase claim. If source-reported quotes can be compared under the same project reference, the system orders their *unverified landed-cost claims* for research; **like-for-like comparability, confirmed price, delivery reliability and purchase readiness remain false/null**.

UK public contract notices cannot be passed as US supplier quotes. No RFQ messages or purchase orders are sent.

### 5. Predictive Cloud compatibility

`review_cloud_commercial_research` reuses **`predictive_cloud_scenario_optimization.build_predictive_cloud_scenario_problem`**, without introducing another forecast/scenario solver.

By default, with missing original lead economics, buyer terms and inventory, the Cloud review returns:

`CLOUD_SOURCE_ECONOMICS_AND_CAPACITY_MISSING`, `scenario_ir=null`

Only an **explicit operator-supplied what-if** with complete scenario probabilities, source-referenced action values, a bounded hypothetical research budget, and a **research-action** capacity group is allowed to compile into the original optimization IR. The result is labelled `HYPOTHETICAL_RESEARCH_CLOUD_IR_NOT_ALLOCATION`; it never executes the solver or authorises client delivery, marketing spend, buying leads or buying materials. An assumed budget is not approved customer money. The Cloud compiler's research-action constraint is **not a constraint on delivered lead units**; real unit-level lead capacity must be validated and encoded by the original service/Cloud owners before any operational optimization.

### 6. Agent handoffs / exact ownership, idempotency and replay policy

Produces **eight** typed PREPARED_NOT_DELIVERED owner review tickets:

1. A2A Commercial Signal Miner — source-rights and local buying-signal research
2. Buyer Scout — company role/identity/verified capacity and duplicate review
3. Lead Supply — canonical consented matching/ZIP inventory and dedupe
4. Marketing/SEO/Campaigns — allowed channels and proposed budgets
5. Procurement/Supply — original measured specs and supplier quote comparison
6. Finance — contracted unit price, payment, settlement, costs, refund/chargeback
7. Scientific Quant — prospectively original prediction and outcome custody
8. Predictive Cloud — research-only scenario review within resource constraints

Every owner ticket is keyed with deterministic `SHA256(requirement_revision,owner,task,contract_version)`. Duplicate original requirement → same eight ticket keys. Keys are **draft idempotency proposals**, not a proof of durable dedupe/owner acknowledgement. All receipts, signatures and tenant A2A trust are NULL or FALSE. Dispatch, sending, creating CRM records, purchasing, campaign creation, payment and production Cloud scheduling require the **existing** source-owner signed task and replay-prevention authority. No current buyer, lead or quote is reserved.

### 7. Read-only reproduction

```bash
PYTHONPATH=/home/ubuntu/empire_agents/predictive_decision_control_20261018 \
  /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_commercial_requirements_20261020 \
  --read-only
```

Optional flags `--requirement-intake`, `--original-roof-survey`, `--supplier-owner-quotes` and `--cloud-what-if` accept **explicitly provided approved typed owner JSON only**; they do not fetch, authenticate or commit external third-party data. `--supplier-owner-quotes` wraps the list as `{"source_owner_quote_claims":[...]}`. All paths are bounded, symlinks rejected and source records remain read-only.

## Production-readiness inventory (not a production deploy)

| Capability | Current stage | Remaining original owner acceptance |
|---|---|---|
| Typed commercial requirement | Implemented/tested in Predictive branch | Tenant/customer authenticated company acceptance and original order intake |
| Live Lead Supply/Buyer Scout/Buyer Capacity aggregates | **Connected read-only** to existing source snapshots | Canonical Tampa ZIP-level consented lead inventory, duplicates, exclusivity, business capacity and payout terms |
| 20-lead Tampa readiness | Implemented, `INSUFFICIENT_EVIDENCE` | Billable specification, buyer identity/consent/contract and lead inventory |
| Roofing materials scope / RFQ preflight | Implemented, **preliminary only** | Original measured BOM, US suppliers, code compliance, comparable approved RFQ responses |
| Owner handoff request contracts | Prepared, **not dispatched** | Trusted production A2A agent identity, signature, replay store, owner request acceptance and receipts |
| Existing Predictive Cloud scenario compilation | Optional **research-only** IR | Authentic available lead capacity, budget, source-cost/accepted-price economics and registered prediction; no auto execution |
| Actual customer revenue/unit margin | **Unverified** | Finance seven original proof gates; independently signed accepted price, paid transaction, refunds, costs and source cohort |
| Outcome learning | Blocked | Original Quant registration, same-cohort independently authenticated outcomes and source rights |
| Production deployment | **Not performed** | Reviewed owner merge, security/provenance, staged readback, approvals and service monitoring |

## What fills the structural and revenue gap next

**Demand:** Buyer Scout and A2A must prove the business can and wants to purchase accepted leads for **specific Tampa ZIPs** and terms. Lead Supply must then identify real, consented, unique, qualified, geographically eligible and not-yet-sold enquiry records; an aggregate research count is insufficient. Marketing can propose approved content/inbound/paid tests only after customer ownership, verified economics and original permission.

**Supply:** Project scope must establish roof specs/measurements, US material/vendor scope, contractor capacity, supplier delivery radius, scheduling constraints and verified like-for-like landed quotes, with permits/code review. Product procurement is not automatically required for every lead; material purchases should only link to independently identified real projects.

**Finance:** Verify price paid per accepted lead, rejected/refunded share, qualified appointment and job outcomes, CAC, cost allocation, materials labour/freight, fees, cash collection and relevant forecasting horizon. Compare **incremental risk-adjusted gross profit after costs** rather than number of leads sent. Do not infer a cash margin or conversion success probability from news, lead research or a hypothetical Cloud IR.

**Timing:** Link consent/acceptance windows, delivery deadlines, verified contractor/supplier availability and material lead times. Missing dates are `null`, not optimistic same-day delivery promises.

**Precision:** Register original predictions *before* first outcomes; measure calibration and historical cohort forecast error only from independently authenticated original Commerce/Finance records, including lost/rejected/duplicate leads. No synthetic commercial outcomes or automatic training.

## Test / approval boundary

Run the new contract tests plus original Cloud/Buyer/Lead Smart/Procurement tests. The owner modules and live DB remain unchanged; no CRM/contact communications, model training, supplier RFQ, payment, worker schedule, campaign, purchase or production deploy.

**Next actual operational milestone:** source-owner verified Tampa company, ZIPs, billable lead definition, capacity and terms; exact lead inventory readback; verified measured real roof project for sourcing. In their absence, source evidence does **not** prove 20 deliverable leads.


### 8. New per-lead duplicate, ZIP and consent research custody

`empire_os/predictive_commercial_lead_eligibility.py` consumes an **optional original Lead Supply source-owner** preview `empire.lead_supply.owner_eligibility_preview.v1`. This is the **first typed per-lead record contract** for the new commercial requirement, not a new collector or a bypass of the existing Lead Supply system.

- Requires exact original requirement revision, source owner and OBSERVE-only authority; bounds freshness (48 hours), individual event age (90 days), number of rows (100) and hashes of original lead and provider-event identity.
- Rejects repeated lead identities and repeated provider-event identities even if the attacker changes one of the two references; these cannot count as two independent potential billable leads.
- Checks postcode/ZIP against an explicit owner/customer-requested ZIP list, where present. If ZIPs are absent, exact geographic eligibility is **unproven**.
- Separates source-owner labels `owner_claimed_billable`, `research_unqualified`, `duplicate_suppressed`, `rejected` and `withdrawn`.
- Rejects any source packet self-claiming authenticated consent, customer acceptance, final delivery or A2A signed message. **There is no trusted external owner signature/readback in this feature branch.**
- Returns only aggregate owner-reviewed preview counts, a revision digest and **`eligible_and_independently_authenticated_customer_leads=null`**. It does not return contact data, verify a customer consent history, allocate an inventory record or assume a first-party transaction.
- Until actual original Lead Supply/Commercial owner sources implement per-lead tenant/consent/duplicate/exclusivity and acknowledgement readbacks, this remains an explicit **preflight** and not verified 20-lead inventory.

Optional input to the live operator:

```bash
PYTHONPATH=/home/ubuntu/empire_agents/predictive_decision_control_20261018 \
  /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_commercial_requirements_20261020 \
  --read-only --requirement-intake /path/to/owner-intake.json \
  --lead-owner-eligibility-preview /path/to/lead-owner-preview.json
```

Without an original source-owner preview, this new instrument reports `PER_LEAD_OWNER_AUDIT_NOT_AVAILABLE`; it does **not** invent zero leads or deduce 20 leads are required to be newly generated from a global count.

**A2A dispatch, customer entitlement, compliance and money remain governed by their existing owners.**
