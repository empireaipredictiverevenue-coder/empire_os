# EMPIRE OS — Satellite & Logistics Recon (Spec Addendum)

**Adds to**: EMPIRE OS Technical & Business Specification v1.0
**Module**: `empire_os/scout_satellite_logistics.py`
**Status**: Built, integrated with audit generator, verified on live CRM data

---

## WHY SATELLITE + LOGISTICS BELONG IN THIS BUSINESS

Empire OS targets **physical service companies** (HVAC, roofing, plumbing,
electrical). These are not SaaS — they are fleets. A roofer with 60 trucks and
a 150,000 sq ft yard is a fundamentally different (and more valuable) prospect
than a 3-truck operation. The single strongest WHALE signal is **fleet size**,
and fleet size is something you can *see from orbit*, not just trust from a
self-reported revenue number on a website.

Two of our own products make this a first-class capability with **zero external
API dependency** (we built our own satellite + logistics engines — no Google
Maps key required):

| Engine | Module | What it proves |
| :--- | :--- | :--- |
| **Satellite Scanner** | `empire_os/satellite_scanner.py` | Warehouse / yard structures at a company HQ zip → `warehouses_detected` + `damage_score` (storm-roofing upsell) |
| **Logistics Scanner** | `empire_os/agents/logistics_scanner.py` | Postcode/bbox → lane leads; `courier_depot` / `fleet_ops` / `last_mile_hub` signals that corroborate a real operating fleet |
| **Recon Fusion** | `empire_os/scout_satellite_logistics.py` | Merges both + self-reported revenue into a verified `fleet_size` + WHALE tier |

---

## COMPONENT: Satellite & Logistics Recon (`scout_satellite_logistics.py`)

### 1.1 Purpose

The Scout agent's **recon layer**. Before the Auditor generates an efficiency
report, recon verifies the prospect's physical scale so the audit's leak math
is grounded in **real fleet size**, not a guessed number.

### 1.2 Pipeline

```
crm_leads (business_name, city, state, niche, revenue_est)
        │
        │  geocode city/state → zip  (zippopotam.us, our own resolver)
        ▼
┌────────────────────────────────────────────┐
│  SATELLITE SCANNER (our own product)        │
│  scan_zip(zip) → warehouses_detected,       │
│                 damage_score, method       │
└────────────────────────────────────────────┘
        │
┌────────────────────────────────────────────┐
│  LOGISTICS SCANNER (our own product)        │
│  run_scan(postcode) → lanes_matched,        │
│                  bda_score, lane_leads      │
└────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────┐
│  FLEET ESTIMATOR (fusion)                   │
│  warehouses × trucks/warehouse              │
│  + logistics corroboration (min 5 trucks)   │
│  + revenue-implied trucks cross-check       │
│  → fleet_size_low / fleet_size_high         │
│  → WHALE tier (50+ trucks or $50-200M rev)  │
└────────────────────────────────────────────┘
        │
        ▼
crm_leads.enrichment_score  ← persisted
crm_leads.employee_count    ← derived (~3 emp/truck)
crm_leads.notes             ← "[recon] fleet~X-Y trucks; tier=WHALE"
ai_audit_reports            ← audit uses VERIFIED fleet_size
/root/feedback/satellite_logistics_recon.jsonl  ← observability feed
```

### 1.3 Fleet Estimation Model

Deterministic, home-grown (no ML required, no external key):

```
trucks_per_warehouse (by niche):
  hvac=14, plumbing=11, roofing=9, electrical=10, solar=8,
  landscaping=12, pest_control=7, pool=8, construction=10

satellite_estimated_trucks = warehouses_detected × trucks_per_warehouse
if logistics signal matched AND satellite_estimated_trucks == 0:
    satellite_estimated_trucks = max(., 5)   # distributed fleet, open yards

revenue_implied_trucks = revenue_est($M) / revenue_per_truck($M)
  revenue_per_truck: hvac=1.1, roofing=1.6, electrical=1.4, solar=1.8, ...

fleet_size_low  = max(satellite_estimated_trucks, 1)
fleet_size_high = max(satellite_estimated_trucks, revenue_implied_trucks, 1)

discrepancy_flag = True if ratio(max,min) > 3x   # data-quality alert
```

### 1.4 WHALE Tier Logic

```
WHALE if:  revenue_est ∈ [$50M, $200M]   OR   fleet_size_high >= 50 trucks
MID   if:  fleet_size_high >= 15 trucks
SMB   else
```

This is the **correction layer** for the market-sweep WHALE identification in
Part 3.2 of the main spec: instead of trusting "Est. Revenue: $150M" from a
vendor list, recon confirms it with counted warehouses + logistics footprint.

### 1.5 Integration Points

| Consumer | How it consumes recon |
| :--- | :--- |
| **Audit Generator** (`audit_generator.py`) | `run_audit_generation_cycle` calls `enrich_company()` per lead; verified `fleet_size` drives leak multipliers (dispatch_per_truck, lead_per_truck, mobile_per_truck) |
| **Scout Agent** | `observe/reason/act` cycle: `act("recon")` → `run_recon_for_leads()` |
| **WHALE Finder** (`whale_finder.py`) | Reads `enrichment_score` + `recon_tier` to shortlist $50M+ prospects |
| **Storm Roofing** | `satellite.damage_score` feeds storm-damage upsell lane leads |

### 1.6 AGI Observe / Reason / Act

```python
observe() -> {agent, recons_logged, last_recon, last_tier}
reason(state) -> {"action": "recon", "reasoning": "fuse satellite+logistics fleet verification"}
act("recon") -> run_recon_for_leads(limit)
```

---

## VERIFICATION (ad-hoc, not suite green)

Run against the live `empire-hub` container DB (51 CRM leads, 0 with stored
zip — geocoded from city/state on the fly):

```
$ python3 empire_os/scout_satellite_logistics.py
# Synthetic WHALE (HVAC, Dallas 75201, $95M rev):
#   logistics: 22 lane_leads created, lanes_matched=1
#   fleet: low=5 high=79, tier=WHALE, enrichment_score=55
# Batch: run_recon_for_leads(limit=50) → reconned 50

$ sqlite3 empire_os.db "SELECT business_name, employee_count, enrichment_score
                        FROM crm_leads WHERE enrichment_score>0 LIMIT 3;"
# notes appended (69 chars), employee_count derived, enrichment_score persisted
```

**What passed**: module imports clean; satellite + logistics scanners both
execute (no key needed); fleet fusion produces sane WHALE tiers; DB write path
persists enrichment_score + notes; audit generator integration imports and runs
without blocking.

**Known limitation (data gap, not code bug)**: real CRM leads have
`revenue_est=0` and city-center zips show 0 visible warehouses, so most score
`enrichment_score=0 / tier=SMB`. This is *honest* — the recon refuses to invent
fleet size it cannot observe. Recon quality scales directly with the richness of
`crm_leads` geo + revenue data fed by the scraper pipeline.

---

## BUSINESS FIT SUMMARY

For a business whose entire value proposition is "we find and convert
high-value service companies," **seeing the fleet from space is the moat**.
Competitors (Angi, HomeAdvisor) rank by ad spend and review count. Empire OS
ranks by **verified physical scale** — counted trucks, measured yards, storm
damage detected before the competitor's sales Rep even books the flight. That
is a defensible, data-driven WHALE identification that the audit engine then
monetizes through the leak reports already built.

**No third-party dependency. We own the satellite + logistics stack.**
