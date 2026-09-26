# Historical MRR Product Recovery — 2026-09-23

Status: **RECOVERED / CLASSIFIED — LEGACY PRICING NOT CURRENT**

The older EmpireOS recurring-revenue catalogue was not deleted. It became
fragmented across legacy SQLite billing, marketplace, tenant plans, SKU seeding,
white-label, affiliate and recovery code. This document restores the product
lineage into the current canonical roadmap.

## What was found

### Platform SaaS subscription plans
Historical source: `empire_os/tenants.py`

Old plans:
- Starter
- Team
- Enterprise
- Scale
- Whale
- Sovereign

The plan/seat/quota concept survives. The old SQLite subscription state and old
prices do not.

Modern destination:
- Phase 8 Productisation
- Supabase tenant/entitlement truth
- canonical usage metering
- governed commercial terms
- USDT/BSC settlement
- Revenue Truth

### Buyer lane-seat MRR
Historical source: `empire_os/marketplace.py`

Old tiers:
- Bronze
- Silver
- Gold
- Diamond
- Empire
- Titanium

This is the strongest MRR product that belongs in the current Phase 4
Commercial Exchange.

Recover:
- recurring buyer seats;
- corridor capacity;
- included capacity/usage;
- overage;
- territory and exclusivity;
- enterprise seat packages.

Do not recover unchanged:
- SQLite marketplace;
- direct delivery as allocation truth;
- historical prices;
- old USDC/Solana settlement;
- fabricated/unverified buyer capacity.

### Historical software/SKU subscriptions
Historical source: `empire_os/seed_sku_products.py`

Recovered SKUs:
- Empire Leads Engine
- Hermes Framework
- OpenCut Studio
- Empire Templates
- MarketingSkills
- Satellite Idle Watch
- SkillSpector Audit
- Synthetic Agent
- AEO Monitor
- Agent Co-Pilot

Disposition:
- Empire Leads Engine → merge into Commercial Exchange + Managed Growth.
- Hermes Framework → rebuild later as governed private-agent platform.
- OpenCut Studio → incubate as creative automation if current capability proves sellable.
- Empire Templates → merge into SaaS/white-label/managed-growth tiers.
- MarketingSkills → merge into Autonomous GTM / Managed Growth.
- Satellite Idle Watch → merge into Industrial/Satellite Intelligence.
- SkillSpector Audit → incubate inside Commercial Diagnostics.
- Synthetic Agent → retire legacy SKU; synthetic production behaviour conflicts with truth rules.
- AEO Monitor → already superseded by verified AEO/GEO/Search catalog products.
- Agent Co-Pilot → rebuild later on current agent authority controls.

### White-label
Historical source: `empire_os/whitelabel.py`

Recover:
- tenant branding;
- custom domains;
- tenant config;
- reseller/enterprise packaging.

Rebuild storage on canonical tenant-scoped Supabase state. Do not restore the
SQLite table as production truth.

### Affiliate / referral
Historical source: `empire_os/affiliate.py`

Recover:
- referral attribution;
- partner slugs/links;
- commission policy;
- partner dashboard.

Commission must only be created from verified canonical commercial events and
Revenue Truth. Old invoice-driven commission code is reference only.

### Evaluation / value-meter subscription
Historical source:
`docs/LEGACY_COMMERCIAL_INTELLIGENCE_RECOVERY_INDEX.md`

Recover:
- Omega evaluation;
- per-use billing;
- credit packs;
- outcome/value billing;
- duplicate-charge protection.

Modern destination:
Omega 2 → observed usage/value event → verified terms → USDT/BSC payment →
outcome → Revenue Truth → learning.

### Intelligence retainer
Historical product: Hourly Intelligence Retainer.

The product concept survives. The historical $150/hour price is legacy
evidence only and is not approved current pricing.

## Current governed products

The current commercial catalog now has 13 verified products:
- the 12 founder-approved pricing-ladder products; plus
- the existing $1,500 Opportunity Intelligence Pilot.

These are current commercial truth. Historical MRR products outside that
catalog remain recovery candidates until separately governed.

## Migration order

### Phase 4 — now
1. Buyer lane seats / corridor subscriptions.
2. Capacity / overage economics.
3. Overflow marketplace/feed monetisation.
4. Buyer Acquisition Team.
5. Demand pre-selling / reserved capacity.

### Phase 6
1. Satellite / physical intelligence subscriptions.
2. Industrial / idle-asset intelligence.
3. Revenue Pulse / Revenue GPS intelligence.
4. Vertical/private feeds.

### Phase 8
1. Platform SaaS plans.
2. White-label / reseller.
3. Affiliate / partner program.
4. Managed Growth tiers.
5. Commercial Diagnostics.
6. Omega Evaluation / value meter.
7. Usage/API bundles.
8. Creative automation where capability proves sellable.

### Phase 10
1. Hermes private-agent product.
2. Agent Co-Pilot.
3. Empire Coder / specialist-agent subscriptions.
4. Enterprise private agent teams.

## Truth rules

- Legacy price is not current price.
- Legacy subscription is not current entitlement.
- Legacy SQLite is not commercial truth.
- Legacy USDC/Solana settlement must not return.
- Current settlement is USDT on BSC.
- No synthetic buyer, usage, revenue or outcome data.
- Recovered product ideas must enter the governed commercial catalog before
  becoming sellable.


## New MRR product added during Phase 4

### Tag Intelligence & Revenue Measurement Monitor

This is a new current product, not a restored legacy SKU.

It monitors:
- search/social/schema metadata;
- indexing/control tags;
- Google/Meta/LinkedIn/TikTok/Microsoft/Reddit/Pinterest measurement tags;
- conversion-event declarations and duplicates;
- consent/server-side measurement evidence;
- Revenue Truth attribution linkage;
- configuration/tag regressions over time.

Commercial state:
- monthly subscription;
- Buyer Acquisition demand research active;
- pricing not yet approved;
- no binding price claim;
- OBSERVE-only execution.
