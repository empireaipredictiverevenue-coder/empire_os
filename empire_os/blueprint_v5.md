# Empire OS — Billion-Scale Architecture Plan v5
Tags: empire-os, scale, architecture, plan, v5
Created: 2026-07-13
Updated: 2026-07-14 (v5 — carrier/DRP + homeowner matching added)

## TL;DR (v5)

$1B ARR = hybrid seat-fees + per-call + per-deal.
Pivot in v3/v4: we moved away from per-lead pricing. We charge
- $200-50,000/mo seat subscriptions (6 tiers)
- $15-250 per-call (5-headed monetization engine)
- 3-10% backend on contract closes (hybrid whale)
**v5 addition**: carrier DRP roster matching + homeowner<>contractor placement as a service tier.
Stack: 1 hub + N regional containers + 1 swarm per container.
All self-healing, no Coolify.

## Architecture (No Coolify, No Postgres — yet)

Single SQLite hub on empire-hub (10.118.155.218:8081) holds the
source of truth. Postgres migration is gated on crossing $5k/mo
MRR (manually curated migrate later). Each agent = 1 Incus
container with feedback_bind to /root/feedback/. OS upgrades
handled by os-upgrade-agent. Crashes handled by supervisor.

## 6-tier pricing model

- bronze $200/mo — 1 lane, $15/90s + $150 hybrid, 5% backend
- silver $500/mo — 5 lanes, $20/90s + $200 hybrid, 7% backend
- gold $1000/mo — 25 lanes, $25/90s + $250 hybrid, 10% backend
- diamond $5000/mo — 100 lanes, $12.50/90s + $125 hybrid, 7% backend + 4h SLA + contract required
- empire $15000/mo — 500 lanes, 0 per-call, 5% backend, 1h SLA + dedicated AE
- titanium $50000/mo — ALL 462 lanes, 0 per-call, 3% backend, 30min SLA + named CSM

Enterprise tiers gated by /v1/buyers/enterprise intake → KYC +
contract flow. Auto-emails founder@empire-ai.co.uk.

## 5-headed monetization engine (PPC router)

- Head 1: 90s sprint — $15-25 per call at 90s duration
- Head 2: hybrid whale — $150-250 connect + 5-10% backend on close
- Head 3: PPL — $45 per buyer (max 3) on form fill
- Head 4: PPS — $150 per AI-booked appointment
- Head 5: Native PPC CPC — $8 per click-through

AGI layer (agent_core.py) + SyntheticIntelligence wired into
switchboard.py for routing decisions.

## Fleet (current state, 2026-07-14)

44+ containers, agents:
- empire-hub (8081): single source of truth (SQLite)
- switchboard (9100): AGI+SI routing
- ppc-router (9200): 5-head billing
- scout-admin (9170), scout-intel: open-source repo ingest
- sales-agent (9150): funnel snapshot, dual-track (contractor + settlement)
- marketing-agent (9160): recommend-only
- commander-agent (9130): fleet ops daily brief
- outreach-agent (9120): Resend + webhook
- crawler-agent (9110): 6 free public-data sources
- sim-agent (9140): Monte Carlo (synthetic_simulation_layer)
- data-acq (9210): hot-lane aggressive scrapes
- media-buyer (9220): daily PPC budget plan
- vault-watch (9230): Helius vault monitor
- b2b-scraper (9240): OSM Nominatim + Overpass
- **contractor-scraper (9250): state license DB + carrier DRP roster scraping**
- satellite-strike (9260): NWS severe alerts + subscriber notify
- supervisor (9270): self-healing restart loop
- os-upgrade (9280): apt update + container image refresh
- innovator (9290): new product/feature ideation
- council (9300): judges innovations, decides ship/no-ship
- legal-compliance (9310): TCPA/GDPR/CCPA send-time guard
- finance (9320): USDC vault reconciliation
- **homeowner-matching (9330): matches homeowner jobs to carrier-approved contractors** (v5 new)
+ 21 legacy agents (mesh/business/growth/engineering/copywriting/
   email/scheduling/predictive/design/funnel/traffic/conversion/
   agi-marketing/agi-scout/seo-agent/ai-seo-agent/lead-filter/
   storm-agent/reddit-sniper/satellite-agent)

## Skills-library wired into agent SOULs

From anthropics/skills + crewAI + agency-protocol:
- skill-creator — meta, every new agent references
- brand-guidelines / theme-factory / frontend-design → design-agent
- canvas-design / algorithmic-art → design-agent visual
- pptx / pdf / docx → sales-agent (decks), legal-agent (contracts)
- internal-comms → marketing-agent (daily brief)
- webapp-testing → dogfooding surfaces
- mcp-builder → engineering-agent
- claude-api → engineering-agent LLM integration
- web-artifacts-builder → AEO page generator
- xlsx → finance-agent recon sheets
- doc-coauthoring → legal-agent KYC contracts
- slack-gif-creator → marketing-agent social snippets

## Replaced (v1-v3 items we removed)

- Coolify ← removed (occupies host ports 80/443, conflicts w/ Caddy)
- Postgres ← deferred until $5k MRR
- Kong API gateway ← replaced by Caddy + FastAPI bare
- Redis Streams ← not needed at this scale
- per-lead-only pricing ← replaced by hybrid seat+call
- Yelp scraping ← no free tier, replaced by 6 free OSS sources
- apify/Clay/Hunter/Apollo paid APIs ← not funded, replaced by OSM+Wikipedia

## Unit economics (v4)

Per buyer average:
- gold $1000/mo + ~30 calls × $25 + 0.5 close × 5% × $5k contract = $1000+$750+$125 = $1875/mo avg per buyer
- 500 agencies × $1875/mo = $937,500/mo = $11.25M ARR (just gold tier)
- titanium $50k/mo + heavy call volume ≈ $80k/mo avg → 50 firms = $4M/mo = $48M ARR
- empire $15k/mo + ded AE = $18k/mo avg → 200 firms = $3.6M/mo = $43M ARR
- Combined Empire+titanium+gold @ 5yr target = ~$300M ARR

Lead acquisition:
- 6 free sources deliver ~50 leads/day/metro = 1k/day/region
- b2b-scraper adds ~5k/day contractor discovery
- satellite-strike alerts drive 10x multiplier during severe weather

Realistic 5-year target: $400M-700M ARR, with titanium tier
scaling past $1B at full 50-state coverage.

## v5 Addition: Carrier DRP + Homeowner Matching

### Problem
Contractors need steady job flow. Homeowners need trusted contractors.
Insurance carriers (State Farm, Allstate, Farmers, Liberty Mutual, etc.)
maintain **Direct Repair Program (DRP)** rosters — pre-vetted contractors
who get first dibs on claims work. Getting contractors onto these rosters
= recurring work pipeline.

### Carrier Roster Module (contractor-scraper 9250)

Scrape carrier "find a contractor" directories:
- State Farm: `statefarm.com/claims/repair-service/find-contractor`
- Allstate: `allstate.com/claims/repair-center-locator`
- Farmers: `farmers.com/claims/repair-network`
- Liberty Mutual: `libertymutual.com/claims/repair-network`
- USAA, Nationwide, Travelers, Progressive

Each directory lists approved contractors by ZIP/metro.
Scrape → extract company name, license#, service area, specializations
→ store in hub as `carrier_rosters` table.

### Application Flow (contractor-agent)

For contractors NOT on a carrier's list:
- Auto-detect carrier partner programs (e.g. State Farm `contractor.sfncc.com`)
- Fill application forms with contractor's existing credentials
- Track application status per carrier
- Goal: get every vetted contractor on 3+ carrier rosters

### Homeowner Matching Module (homeowner-matching 9330)

- Homeowner submits job request (roof repair, HVAC, plumbing, etc.)
- System finds carrier-approved contractors in their ZIP
- Match based on: specialization, availability, rating, distance
- Queue for outreach-agent to send intro + scope + bid link
- Track from match → bid → accepted → settled → backend revenue

### Pipeline state machine (extended)

```
homeowner_job → discovered → matched_to_contractor → 
bid_sent → bid_accepted → work_scheduled → work_completed → 
settled → backend_collected
```

### Revenue model for this module

- Per-match fee: $15-50 (depends on tier)
- Backend on closed jobs: 5-8% (hybrid whale on placements)
- Carrier roster placement service: $500-2000 one-time per contractor
  (getting them listed with 3+ carriers)

## Pending (v4 backlog)

### Items not shipped from v1 plan (gated on revenue trigger):
1. Postgres per-region split ($5k MRR trigger)
2. Redis Streams for crawler_queue ($10k MRR trigger)
3. Kong auth gateway (replace w/ Caddy+FastAPI bare, deferred)
4. CAN-Toronto franchise onboarding (waitlist mode via /v1/buyers/enterprise)
5. 70/30 escrow logic (smart contract, frozen pending $50k MRR)
6. Cross-region aggregator (deferred — fleet is single-region now)
7. Hot-metro tier pricing uplifts (predictive-agent has formulas)

### New items from v4 expansion:
1. Wire b2b-scraper / contractor-scraper / satellite-strike — drafted, pending launch
2. Wire supervisor / os-upgrade / innovator / council / legal-compliance / finance — drafted, pending launch
3. Move skills-library from /tmp/repo_skills → /root/empire_os/skills_library/ + reference per SOUL
4. Complete cold-start funding — vault empty, no MRR yet
5. Push creative video production pipeline (cap-cut clones)
6. AI SEO agent budget — keyword targeting at scale
7. Outreach 50 KYC-verified prospects — founder already on it
8. Web app dashboards for buyers — currently no admin UI
9. SMS via Twilio (replace Resend broadcast for high-touch)
10. Backup / disaster-recovery for the SQLite hub DB

### v5 new items:
11. **Carrier DRP roster scraper** — statefarm.com, allstate.com, farmers.com, etc.
12. **Homeowner job intake + matching** — web form → match to carrier-approved contractors → bid workflow
13. **Carrier application portal auto-filler** — get contractors onto 3+ carrier rosters
14. **Pipeline extension** — add homeowner_job → settled states to existing traffic status

## Filing this blueprint as canonical

When $5k MRR achieved, the v5 plan will:
- Split SQLite into Postgres per-container
- Promote evaluator-agent + HybridEngine to top-level service
- Add CAN-UK-AUS regional hub blueprint
- Run franchise tier fully featured
- Multi-region failover via shared mesh
- Carrier roster as a standalone SaaS product tier
