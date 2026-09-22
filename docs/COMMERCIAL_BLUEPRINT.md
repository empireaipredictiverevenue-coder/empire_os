# Empire AI Commercial Blueprint

## Purpose
This document is the canonical commercial model for the buyer side of Empire AI. It unifies seats, corridors, territories, recurring MRR products, opportunity supply, routing, fulfilment, free traffic, campaigns and Revenue OS economics.

The commercial system is demand-led:
buyer demand + verified capacity + commercial terms -> supply generation -> qualification -> allocation -> delivery -> payment -> outcome -> learning.

## Canonical vocabulary

### Buyer Account
The commercial customer or partner. A buyer may hold one or more seats, subscribe to MRR products, receive opportunities, consume intelligence, or use Empire software/services.

### Territory
A geographic right or operating scope: country, region, county, metro, postcode/ZIP cluster, radius, or another explicitly defined geography.

A territory does not itself guarantee volume. It defines where a buyer is eligible to receive supply.

### Corridor
A commercial market corridor is:
product/niche x territory x demand type x delivery mode.

Examples:
- roofing x Manchester x qualified homeowner opportunity x exclusive
- dental x Birmingham x booked appointment x shared
- legal x UK national x qualified case lead x exclusive
- SaaS x London x buyer-intelligence feed x subscription

The corridor is the economic unit Astra and Revenue OS can measure.

### Seat
A seat is a buyer's governed commercial right to consume capacity inside one or more corridors.

A seat has:
- buyer
- corridor
- status
- start/end dates
- exclusivity mode
- daily/weekly/monthly capacity
- delivery destination
- pricing/commercial terms
- evidence requirements
- territory rights
- renewal terms
- performance/outcome history

A seat is not merely a software login. It is a commercial allocation entitlement.

### Capacity
How much verified supply a buyer is willing and able to accept. Capacity gates allocation/delivery, not acquisition.

When seat capacity is full or unavailable, Empire keeps the opportunity as owned inventory/overflow for another buyer, corridor, marketplace path, self-serve route, or later allocation.

### Owned Inventory
Qualified or potentially valuable opportunities that Empire owns/control before allocation. Inventory is never fabricated and keeps provenance/evidence.

### Market Lane
A broader grouping of related corridors, normally a niche/product family. Lanes are useful for dashboards and portfolio management; corridors remain the precise allocation/economic unit.

## Buyer product ladder

### 1. Opportunity Products
Usage/transactional products:
- qualified lead
- exclusive lead
- shared lead
- qualified call
- booked appointment
- verified commercial opportunity
- high-ticket opportunity pack
- pay-per-call
- outcome-priced opportunity where legally/commercially appropriate

### 2. Seat / Territory MRR
Recurring access products:
- single corridor seat
- metro/city seat
- postcode/ZIP cluster seat
- county/region seat
- multi-territory seat
- category/niche seat
- exclusive territory seat
- priority routing seat
- reserve/overflow seat
- enterprise multi-seat portfolio

MRR buys governed access/capacity rights; actual delivered inventory and overage can be priced separately.

### 3. Intelligence MRR
- Search Intelligence / SEO / AEO / GEO
- Organic + AI Recommendation Intelligence
- AI Visibility monitoring
- Competitor Revenue Radar
- Territory Opportunity Radar
- Buyer Intelligence
- Predictive Revenue forecasting
- Revenue CRM
- AI Closer/Concierge
- Signal feeds
- Market/Storm/Event alerts
- Benchmark reports and API/data feeds

#### Organic + AI Recommendation Intelligence packaging

Sellable outcome:
measure and improve discoverability across organic search and captured AI-answer
surfaces without promising a specific ranking or recommendation.

Deliverables may include:
- organic visibility baseline;
- AI answer/citation/recommendation observation report;
- monitored-query share of observed recommendations;
- competitor recommendation-gap report;
- citation/source opportunity map;
- recurring change alerts;
- search/AI-touch to recognized-revenue attribution where evidence exists.

Commercial models:
- subscription monitoring;
- managed service;
- agency/reseller wholesale;
- white-label licence;
- enterprise reporting/API.

Pricing remains evidence-driven until real willingness-to-pay, delivery cost,
retention and outcome data are observed.

### 4. Growth / Managed MRR
- managed SEO/AEO/GEO
- programmatic landing/page factory
- content/campaign engine
- conversion optimisation
- call handling / appointment qualification
- done-for-you growth
- managed lead supply
- managed territory expansion

### 5. Platform / SaaS MRR
- Starter
- Growth
- Pro / Agency
- White Label
- Enterprise

Existing commercial ladder remains:
Starter GBP 299-499/mo
Growth GBP 999-2,500/mo
Pro/Agency GBP 3,000-7,500/mo
White Label GBP 10k-30k setup + GBP 2k-10k/mo
Enterprise GBP 25k-100k implementation + GBP 5k-25k/mo
Managed revenue GBP 3k-15k/mo + performance
Custom GBP 25k-250k+

## Seat economics
A seat can combine:
base MRR + included capacity + overage + exclusivity premium + territory premium + performance component.

A seat must never imply guaranteed lead volume unless the contract explicitly supports it.

Suggested commercial states:
prospect -> qualified_buyer -> terms_review -> seat_pending -> activated -> capacity_open -> capacity_full -> paused -> renewal_due -> cancelled.

## Territory model
Territories are composable rather than hard-coded.

Hierarchy:
country -> region/state -> county -> metro -> postcode/ZIP cluster -> radius/geofence.

Territory claims require:
- explicit buyer agreement
- corridor definition
- exclusivity mode
- start/end dates
- capacity
- commercial price
- renewal rights
- conflict/overlap rules
- outcome performance

Empire should be able to show:
- open territories
- occupied territories
- waitlisted territories
- under-capacity territories
- high-demand/low-supply territories
- overflow inventory by territory

## Corridor economics
Every corridor should expose:
- owned inventory
- qualified inventory
- active buyer seats
- verified buyer capacity
- delivered units
- accepted/rejected units
- realized revenue
- realized cost
- gross profit
- gross margin
- buyer conversion/outcomes
- repeat-purchase rate
- traffic/source contribution
- demand/supply imbalance

This is the core unit for Predictive Revenue.

## Buyer acquisition system
Empire GTM owns:
lead generation -> buyer acquisition -> qualification -> matching -> commercial terms -> seat activation -> fulfilment -> payment -> outcome -> feedback.

Buyer sourcing channels:
- TAM/account intelligence
- organic search
- AI search/AEO/GEO
- free tools/scanners
- partner/referral network
- content/social/community
- marketplace/inbound
- governed direct outreach
- agency/white-label partners

## Free traffic system behind buyer acquisition
Free tool/scanner -> organic/AI visibility -> buyer enters niche/territory -> territory/corridor opportunity report -> buyer qualification -> seat proposal -> activation -> opportunity supply.

High-value free tools:
- Territory Opportunity Scanner
- AI Visibility Checker
- Revenue Leak Scanner
- Lead Value Calculator
- Competitor Revenue Radar
- Buyer Capacity Calculator
- Territory Availability Checker
- Corridor Profitability Calculator

Each tool should create first-party intent evidence and map the prospect to likely products/corridors without automatically activating commercial authority.

## Campaign model
Campaigns are no longer a legacy SQLite object.

A campaign is a governed plan attached to:
- objective
- audience
- corridor(s)
- territory
- offer/product
- channel(s)
- content/assets
- evidence
- attribution model
- success metric
- cost/spend policy
- approval state
- outcome history

Free/owned campaigns may produce drafts, pages, content plans, internal-link plans, community/social packs and partner packs automatically when execution is reversible and policy-safe.

Outbound sending, paid spend, account mutation and consequential commercial actions remain separately governed.

## Product flywheel
Market signal
-> corridor opportunity
-> free tool / content / page
-> inbound buyer
-> buyer qualification
-> territory/seat proposal
-> recurring MRR
-> supply generated against demand
-> opportunity delivered
-> verified payment/outcome
-> corridor economics improve
-> Astra identifies next territory/product to scale.

## Buyer-facing product
The buyer portal should eventually expose:
- My Seats
- My Territories
- My Corridors
- Capacity
- Delivered Opportunities
- Calls/Appointments
- Outcomes
- Spend / invoices / USDT-BSC settlement evidence
- ROI / gross value
- Territory expansion opportunities
- Add/upgrade seat
- Intelligence products
- Search/AI visibility
- Campaigns
- Support/AI Concierge

## Internal operator views
Operator Cockpit:
- corridor heatmap
- territory occupancy
- buyer seat capacity
- open inventory
- overflow inventory
- revenue/margin by corridor
- MRR by product
- churn/renewal risk
- first-revenue pipeline
- free-traffic attribution
- campaign performance
- blocked approvals

## Core commercial rule
Do not generate supply blindly.

Empire generates and acquires supply against:
1. observed demand,
2. verified buyer capacity,
3. corridor economics,
4. expected margin,
5. fulfilment ability,
6. evidence quality.

Acquisition may continue above current delivery capacity only when inventory remains owned, provenance-safe and economically justified; allocation stops at verified capacity.

## Architecture principle
Supabase is canonical truth.
Legacy SQLite commercial paths are retired.
Revenue CRM is the commercial spine.
Astra coordinates priorities.
Predictive Cloud scores expected economics.
Revenue OS measures real outcomes.
Demand Genesis proposes demand creation.
Search/Growth OS creates inbound demand.
Revenue Exchange later handles dynamic inventory/pricing/allocation under governance.
