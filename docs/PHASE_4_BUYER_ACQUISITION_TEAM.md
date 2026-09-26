# Phase 4 Buyer Acquisition Team

Status: **ACTIVE BUILD — OBSERVE / INTERNAL AUTOMATION**

The Buyer Acquisition Team is the demand-side counterpart to Empire's
continuous acquisition engine. It is not limited to B2B leads.

## Buyer pools

### Local and small businesses
Contractors, dentists, clinics, accountants, estate agents, garages, cleaners,
landscapers, gyms, salons, local legal firms, independent retailers, home
services and professional services.

Potential products include local/exclusive leads, calls, booked appointments,
Search/SEO intelligence, commercial diagnostics, managed growth and
lightweight SaaS.

### End-service buyers
Roofing, HVAC, plumbing, solar, restoration, legal, insurance, mortgage,
debt, Medicare, landscaping, cleaning, gutter, general contractors and future
verticals.

### Direct demand buyers
Lead buyers, lead aggregators, call buyers, performance marketers, affiliate
networks and lead marketplaces.

### Agencies and resellers
Marketing, lead-generation and growth agencies plus white-label/reseller
partners.

### Enterprise and data buyers
Private equity, property groups, logistics/warehouse operators, financial
services, enterprise sales teams and other buyers of intelligence/data/API
products.

### Software and advisory buyers
Sales and marketing teams, operators, agencies and multi-location businesses
buying SaaS, commercial diagnostics, managed growth and Predictive
Intelligence.

## Products are broader than lead inventory

The team consumes both:
1. corridor demand gaps from Commercial Exchange inventory; and
2. product demand from the canonical commercial product catalog.

Catalog products with verified binding terms may enter sell-now research.
Products with unknown/unverified terms may be market-validated, but the system
must not invent or claim a binding price.

## Team roles

1. Demand Gap Analyst
2. Buyer Scout
3. Decision-Maker Resolver
4. Contact Verifier
5. Buyer Qualifier
6. Outreach Preparer
7. Buyer Conversation Intake
8. Commercial Evidence Verifier
9. Seat Readiness Agent
10. Buyer Success / Capacity Agent

## Automated internal loop

Recurring internal automation may:
- refresh the restricted commercial product catalog;
- refresh qualification and identity catch-up;
- discover/review evidence-backed buyer candidates;
- enrich deferred buyer identities and contacts;
- refresh buyer capacity readiness;
- verify only deterministic buyer-stated commercial evidence;
- refresh Commercial Exchange inventory/seats/overflow;
- reprioritize corridor and product demand;
- prepare governed review/outbound intents.

The internal automation does **not send** email, SMS or voice calls.

Live outbound remains separately governed and is not part of the Buyer
Acquisition Team production-readiness requirement.

## Commercial evidence captured from buyer conversations

- purchased unit;
- niches/products;
- territories;
- daily/monthly capacity;
- exclusive/shared preference;
- acceptance criteria;
- delivery method;
- price/rate;
- return/replacement terms;
- compliance requirements;
- payment terms;
- settlement rail.

Only explicit evidence may be promoted. Unknown stays unknown.

## Core invariants

- Buyer capacity gates delivery only, never acquisition.
- Full buyer seats do not stop lead acquisition.
- Overflow remains Empire-owned.
- Source-ranking heuristics are not buyer-intent proof.
- Historical pricing is not approved current pricing.
- No product without verified terms may claim a binding price.
- Canonical settlement is USDT on BSC.
- Legacy Solana/USDC buyer-hunter assumptions are reference-only.
- No synthetic buyers, capacity, prices or revenue.


## Recovered EmpireOS MRR product lineage

The historical recurring-revenue catalogue is preserved in
`docs/MRR_PRODUCT_RECOVERY_2026-09-23.md` and
`empire_os/mrr_product_recovery.py`.

Phase 4 actively recovers these Commercial Exchange products:
- Commercial Exchange Starter Seat;
- Commercial Exchange Growth Seat;
- Commercial Exchange Pro Seat;
- Commercial Exchange Enterprise.

These products are now included in Buyer Acquisition product-demand planning.
They remain `MARKET_VALIDATE_TERMS_REQUIRED` until a separately governed
pricing ladder is approved and verified in the canonical commercial catalog.

The remaining historical recurring products are not discarded:
- Platform SaaS tiers → Phase 8;
- Empire Leads Engine → merged into Commercial Exchange / Managed Growth;
- Satellite Idle Watch → Phase 6 industrial intelligence;
- White-label platform → Phase 8;
- Affiliate / referral → Phase 8;
- Omega Evaluation / Value Meter → Phase 8;
- Hourly Intelligence Retainer → Phase 8;
- Hermes Framework / Agent Co-Pilot → Phase 10;
- OpenCut / creative automation → incubate for Phase 8;
- AEO Monitor → superseded by current verified AEO/GEO/Search products;
- Synthetic Agent → retired under current truth rules.

Legacy names, SQLite subscriptions, Solana/USDC settlement and historical prices
are not current commercial truth.
