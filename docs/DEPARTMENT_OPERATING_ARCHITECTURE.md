# Empire AI — Department Operating Architecture

Date: 2026-09-22
Status: CANONICAL ORGANIZATIONAL ARCHITECTURE

## Company hierarchy

**Founder**
→ **Astra Executive**
→ **Department**
→ **Specialist agent / model / deterministic service / tool**
→ **Control Fabric**
→ **Governed action**
→ **Observed outcome**
→ **Predictive Cloud / Economic Memory**

Agents are replaceable workers.

Departments are durable operating systems.

Models are replaceable intelligence providers.

Control Fabric owns authority.

Quant owns mathematical verification.

Predictive Cloud owns business/world state and learning.

Astra Executive owns cross-company goals, prioritization, delegation and review.

## Canonical departments

### 1. Strategy & Executive

Mission:
Coordinate company goals, priorities, attention, resources and cross-department work.

Core systems:
- Astra Executive
- Astra
- Control Fabric

Primary outputs:
- company goals
- department objectives
- resource priorities
- founder gates
- executive review

### 2. Marketing & Growth

Mission:
Create, capture, convert and expand profitable demand.

Functions:
- category / positioning
- demand generation
- search / SEO / AEO / GEO
- content / editorial
- brand / creative
- lifecycle marketing
- community / PR
- partner / affiliate marketing
- campaign analytics
- conversion optimization

Core systems:
- Marketing
- Search Intelligence
- Demand Genesis
- Conversion Intelligence

Canonical blueprint:
`docs/MARKETING_DEPARTMENT_BLUEPRINT.md`

### 3. Sales & Revenue

Mission:
Convert genuine buyer evidence into conversations, commercial terms, verified
payment and expansion.

Functions:
- qualification
- buyer review
- AI closer
- Conversation OS
- CRM sales motion
- terms progression
- payment progression
- expansion

Core systems:
- Conversation OS
- Buyer Review
- Commercial Terms
- Revenue Pulse

### 4. Research & Development

Mission:
Convert scientific, technical and commercial uncertainty into validated
capabilities, defensible IP and product advantages.

Functions:
- applied AI / ML research
- agentic/general intelligence
- Quant methods
- causal / experimentation
- multimodal intelligence
- new sources / crawlers
- new products / data products
- prototypes
- benchmarking
- engineering transfer

Core systems:
- Opportunity Loop
- Empire Coder
- Quant Brain
- Experiment Intelligence

Canonical blueprint:
`docs/RD_DEPARTMENT_BLUEPRINT.md`

### 5. Product

Mission:
Turn validated customer problems, market opportunities and R&D capability into
coherent products, offers, packaging and roadmaps.

Core systems:
- Commercial Product Catalog
- Opportunity Factory
- Digital Twin

Primary outputs:
- product requirements
- product definitions
- offers / packaging
- roadmap
- launch candidates

### 6. Engineering & Platform

Mission:
Build, test, operate and improve secure, reliable EmpireOS capabilities.

Core systems:
- Empire Coder
- Ops Sentinel
- Control Fabric

Functions:
- software engineering
- architecture
- testing
- deployment
- runtime reliability
- performance
- infrastructure
- internal developer tooling

### 7. Data, Quant & Predictive Intelligence

Mission:
Measure reality, quantify uncertainty, forecast outcomes and verify economic
decision quality.

Core systems:
- Quant Brain
- Predictive Intelligence
- Predictive Cloud Status
- Intelligence Fabric

Functions:
- descriptive analysis
- diagnostic analysis
- predictive analysis
- causal analysis
- Bayesian inference
- Monte Carlo
- calibration
- forecasting
- risk
- portfolio analysis
- value of information
- decision packets

### 8. Market & Opportunity Intelligence

Mission:
Continuously discover and validate markets, signals, triggers, territories,
buyers, gaps and emerging commercial opportunities.

Core systems:
- Predictive Cloud Opportunity Loop
- Market Opportunity Agent
- Intelligence Fabric

Functions:
- Opportunity Radar
- Market Sweeps
- Revenue GPS
- TAM / ICP
- competitor intelligence
- event intelligence
- geographic intelligence
- opportunity lifecycle
- evidence routing

### 9. Customer & Revenue Operations

Mission:
Drive onboarding, adoption, retention, expansion and accurate customer state.

Core systems:
- Revenue CRM
- Conversation OS

Functions:
- onboarding
- customer success
- lifecycle
- retention
- expansion
- churn prevention
- customer outcome capture

### 10. Operations & Fulfilment

Mission:
Turn sold outcomes into reliable delivery and verified fulfilment evidence.

Core systems:
- Fulfilment Readiness
- Ops Sentinel

Functions:
- capacity
- delivery
- service levels
- runbooks
- cost control
- quality
- fulfilment evidence

### 11. Finance & Capital

Mission:
Protect cash, measure economics and allocate capital toward evidence-backed,
risk-adjusted returns.

Core systems:
- Capital Allocator
- Quant Brain
- Revenue Pulse

Functions:
- unit economics
- budget recommendations
- capital allocation
- portfolio concentration
- cash exposure
- payback
- realized GP

### 12. Risk, Legal & Compliance

Mission:
Constrain company action to approved legal, security, privacy, compliance and
authority boundaries.

Core systems:
- Control Fabric
- Outbound Governor

Functions:
- policy
- authority
- suppression
- privacy
- security
- compliance
- audit
- founder gates

### 13. Partnerships & Distribution

Mission:
Build scalable buyer, agency, affiliate, reseller, white-label and strategic
distribution channels.

Core systems:
- Buyer Capacity Readiness
- Strategic Partnerships

Functions:
- partner research
- buyer capacity
- distribution routes
- affiliates
- reseller / agency
- co-marketing
- channel economics

## Department execution contract

Every department receives from Astra:

- objective
- priority
- evidence refs
- allowed authority
- memory scope
- success condition
- review horizon

Every department returns:

- work performed
- evidence acquired
- artifacts produced
- observed result
- uncertainty
- blockers
- recommended next action
- authority needed for next step

## Cross-department operating loop

Market Intelligence discovers an opportunity.
↓
Data/Quant measures evidence and uncertainty.
↓
Strategy/Astra determines priority.
↓
R&D investigates unknown technical/commercial questions.
↓
Product defines the offer.
↓
Engineering builds or adapts capability.
↓
Marketing creates/captures demand.
↓
Sales converts genuine buyer state.
↓
Operations fulfils.
↓
Finance verifies economics.
↓
Customer Success drives retention/expansion.
↓
Risk/Compliance governs boundaries throughout.
↓
Partnerships expands distribution.
↓
Observed outcomes return to Predictive Cloud / Economic Memory.
↓
Astra updates company priorities.

## Intelligence rule

A department does not become a separate brain.

Astra remains the executive coordinator.

Predictive Cloud remains the shared world/business state.

Quant remains the deterministic mathematical verifier.

Specialist LLMs/agents may change over time without changing department
contracts.

Future stronger models, AGI-class systems or ASI-class systems plug into
department and intelligence-provider contracts. Greater intelligence does not
automatically grant greater authority.

## Current implementation

Canonical registry:
`empire_os/departments.py`

Authority/routing registry:
`empire_os/control_fabric.py`

Executive delegation:
`empire_os/astra_executive.py`

Department health/coverage:
`empire_os/predictive_cloud_status.py`

The implementation must fail tests if a canonical department references a
component that is no longer registered in Control Fabric.
