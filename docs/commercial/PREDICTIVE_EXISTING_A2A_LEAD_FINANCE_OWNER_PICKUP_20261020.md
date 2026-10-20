# Predictive Commercial OS — Cross-Agent Owner Pickup and Source Evidence

**Date:** 20 October 2026
**Worktree:** `/home/ubuntu/empire_agents/predictive_decision_control_20261018`
**Authority:** OBSERVE; existing Predictive integration owns the *coordination review*, not other agents' queues, Finance records, buyer contracts, CRM, campaigns, source code or schedules.

## Integration added

`empire_os/predictive_existing_owner_pickup.py`

The existing multiregion commercial intake operator now composes the real source interfaces:

1. **Original commercial requirement** (`predictive_commercial_requirements`): exact customer-entered industry, country, region, city, target, policy and open acceptance/tenant/source proofs. No default geography or market.
2. **Existing Lead Supply/Buyer Scout/Buyer Capacity** (`predictive_commercial_supply_readiness`): reads original aggregate owner snapshots in `/srv/empire_os/runtime`. Counters are original research and cross-industry totals, **not matched consented consumer leads or a buyer order**. Missing sector/market yields `null`, not zero deliverable leads.
3. **Existing A2A Commercial Signal Miner original owner**: read-only `buyer_owner_research_handoffs_v1.json` and `owner_signed_receipts_review_v1.json` under `/home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020/runtime/a2a_commercial_signal_mining/`. Owner branch `f5e3028d` at source inspection; the miner has other uncommitted research work. No external collector or A2A worker started by Predictive.
4. **Existing Finance evidence readiness** (`enterprise_finance_evidence_readiness.review_finance_source_readiness`): original bounded Revenue Pulse, Economic Memory and Buyer Capacity source reviews plus seven unauthenticated finance proofs. No direct database access or financial posting.
5. **Owner-specific research ticket preflights** (`predictive_commercial_fulfilment.prepare_owner_handoffs`): eight existing departments, their original idempotency keys and an explicit dependency/prerequisite queue.

The integrated operator adds:
- `original_a2a_owner_research_overlap`: schema and authority-checked A2A original ticket overlap **only if exact industry, city and state match**, with original source age and original receipt review status.
- `existing_finance_proof_gate_status`: source observation freshness, count of independent Finance proof gates, unverified customer profit.
- `department_owner_acceptance_and_next_actions`: eight existing owner tickets keyed to the original requirement revision, assigned original source readiness and **precise independent proof needed before each owner may accept**, with no actual dispatch or confirmed owner acknowledgement.

### Exact target scope: no false joins

- A2A's previous founder profiles are *its own historic targeted research*, not a generic validated commercial requirement. Overlap is shown only when source sector and source city, state match the exact new requirement, e.g. `roofing` + `tampa, fl`. Similar industries, metro nicknames, other cities and other states are *not inferred as identical*. This is intentionally conservative until an original canonical geocoder and A2A source owner attest equivalences.
- Even **two matching research tickets are not two leads, buyers, supplier quotes or owner approvals**. The original agent tickets have `PREPARED_NOT_DELIVERED`. Receipt counters are not accepted by this consumer as independently signed tenant- and original-requirement-bound receipts.
- The report refuses duplicate original A2A ticket IDs; incorrect owner, destination, execution mode; forged contact, campaign, CRM or money authority; missing/stale owner source, untrustworthy source counts and inconsistent reported receipt counts.
- The source owner file root is read-only, bounded to 120 KB per JSON input and symlink/source-staleness protected. It reads no raw company names, names, phones, emails or domains into its output. No direct Buyer Scout database row or customer contact is imported.

### Tested real readback (source snapshot, 20 October 2026)

An **explicitly labelled illustrative** Tampa roofing request found in the existing A2A owner worktree:
- 3 source target profiles / 6 prepared existing A2A owner research tickets
- **2 exact roofing Tampa FL source tickets**
- owner receipt source review says **0 authenticated owner replies**, **no configured production trust-store keys**, and **no owner research task dispatch**
- **8 newly proposed departmental review tickets** from the distinct original Predictive requirement, **0 dispatched**
- Finance **7 independent proof gaps remain open**, no authenticated same-customer paid profit outcome
- No authenticated booked client agreement or verified geographically consented and billable lead inventory.

The exact A2A source report currently references older original owner observations. Before any real action, the **original owner** must refresh and authenticate source data and own its source rights. No source evidence is promoted to a customer order or actual lead allocation.

An HVAC Phoenix request can match A2A's independently reported HVAC Phoenix profile **only when the original A2A owner has such an exact source record**. If not, output is `NO_EXACT_PREEXISTING_A2A_SECTOR_CITY_REGION_PROFILE`. This is not proof that no HVAC prospects exist. No market is prioritised because it appeared in an old founder illustration.

### Industry-aware action queue

Eight retained department owners, with original idempotency keys:

| Owner | Evidence/decision needed |
|---|---|
| A2A Commercial Signal Miner | Source-rights permitting exact target/niche research, owner source acknowledgement |
| Buyer Scout | Canonical business buyer roles, buying terms, real capacity and duplicate history |
| Lead Supply | Original consent, unique event identity, ZIP-specific eligibility, permitted exclusive/shared sale |
| Marketing/SEO | Founder/customer approved channel and spend, measurable CAC and permitted traffic sources |
| Procurement | Real measured project need, product/code specification, actual supplier quotation, freight and approval |
| Finance OS | Original contracted price, source-authenticated payments, refunds, landed cost, labour and settlement |
| Quant | Prospective original profit forecast register and independently attributed commercial outcome |
| Predictive Cloud | Evidence-scope-safe downside, budget and capacity constrained scenario IR; no automatic allocation |

For agencies, data brokerage, software, insurance and other nonphysical services, the Procurement owner ticket is explicitly `NO_PHYSICAL_MATERIAL_RFQ_REQUIRED`; no phantom roof-supplier research is advanced. Other owners still hold their own contract acceptance. Draft SHA keys do **not** establish persisted replay protection.

### Reproduction

```bash
# Deployed allowlisted read-only operator; no implicit market or example
~/.local/bin/empire-predictive-observe commercial

# Example is requested expressly, never silently
~/.local/bin/empire-predictive-observe commercial-example

# A specific tenant/business original intake packet; still unverified as a customer order
~/.local/bin/empire-predictive-observe commercial-intake /path/to/original-owner-intake.json
```

The script accepts an optional `--a2a-owner-root` for isolated/offline fixture testing or reviewed source relocation. The default original owner path is the existing A2A worktree. No source file is copied, mutated or attached to a marketing/sales activity.

### Production readiness

- **Implemented and tested:** exact-sector+market A2A source report admission, receipt/no-dispatch contract checks, Finance readiness composition, deduped source ticket review, original eight-owner proof queue.
- **Connected read-only:** existing A2A, Lead Supply, Buyer Scout, Buyer Capacity and Finance aggregate owner source artifact paths, when present/fresh.
- **Still blocked:** independent original A2A task acceptance, production A2A trust keys and replay store, first-party customer authorisation, product-specific consented inventory, approved lead price/terms, supplier originals, independent Finance cash and variable-cost truth, registered Quant gross-profit forecast and actual matched outcomes.
- **Not deployed/activated:** production agent task routing, A2A message send, external search, customer contact, CRM writes, ad campaigns, procurement, invoices, Cloud allocation and model training.

**Success criterion:** source evidence → original owner acceptance → real commercial feasibility → source-authenticated customer economics → prospective registered profit prediction → genuinely realised gross profit and forecast error → governed allocation. Missing source is a hold, never an invented zero or fake revenue.
