# Empire AI — Data Brokerage Sales & First Recurring-Revenue Handoff

**18 October 2026 | Internal founder/Sales proposal drafts | Never sent, sold, invoiced or promised.**

## The commercial choice

The existing Data Handler has **4 product families**, **14 draft monetisation options**
and **6 distribution routes**. Those numbers are internal product work,
not 14 deliverable live subscriptions. Reuse the existing sources,
Marketing, Sales/CRM, Strategic Partnerships, Predictive Intelligence and
Workspace mail. Do not create a second prospect database or marketplace.

Prioritise **one real customer problem** in each of three price tiers:

| Track | Existing code | Price hypothesis | Buyer | Proposed next action |
|---|---|---:|---|---|
| Entry proof | `roofing_competitor_report` | $199 once | Local roofing contractor | Convert existing SPC email into an accepted one-service one-city scope if the recipient replies |
| Recurring channel | `agency_white_label_search` | $1,250/month | SEO / web agency | Confirm a real agency decision-maker needs independently sourced client briefs |
| Enterprise contract | `portfolio_geography_intelligence` | $4,000/month | Multi-location operator | Verify named territory expansion decision and budget owner |

The prices and volumes below are **negotiation drafts only**. No
real customer, willingness-to-pay, reporting capacity, contractual
rights or independent cash settlement is established by this document.
No free unlimited pilot or guaranteed rankings/ROI is promised.

## A. Proposed agency white-label pilot — $1,250 USD/month

**Best-fit agency:** a professional service provider working with real
roofing, solar, HVAC or dental clients in the UK/USA. Enterprise agency
does not need to move its clients' personal data to Empire AI.

**Problem statement:** agencies need independently researched local
competitor/market evidence without hiring another analyst for every
service-area study.

**Proposed first-month package, conditional on capacity confirmation:**

- Two tightly bounded original local-market briefs, each **one service
  + one metro**, with dated sources, measured search-engine locale
  and results *only when actually captured*.
- Evidence-linked 3–5 comparator service pages for each scoped brief.
- One original monthly change/opportunity synthesis and one documented
  correction/revision round.
- Agency-branded presentation of the *original analysis* under a
  separately agreed white-label licence. No resale of protected
  third-party source rows or claim of exclusive ownership of public
  data.
- Private delivery via an existing, authorised route after clear
  terms/recipient verification; no automatic distribution or
  customer-facing API enabled by this scope.

**Acceptance criteria to negotiate:** actual client/territory list,
permitted agency recipients, per-brief source freshness, page evidence
and correction policy, human report QA, monthly capacity and payment
period, cancellation date, portfolio attribution, confidentiality and
usage restrictions. Do not bind two briefs/month until workload proof
exists.

**Founder-review conversation starter — DRAFT, NOT APPROVED OR SENT**

> Empire AI is testing a white-label market-intelligence service for
> established agencies. Rather than another SEO execution package,
> we would supply independently sourced, dated competitor briefs for
> one service and territory at a time. We're testing a $1,250/month
> limited pilot, subject to confirming scope and reporting capacity.
> Is original, evidence-linked market research something your team
> already commissions or needs for existing clients?

No generic “your rankings are bad” claims and no duplicate first-touch
message to agencies already approached by other EmpireOS agents.

## B. Proposed multi-territory enterprise pilot — $4,000 USD/month

**Best-fit buyer:** an authorised expansion, corporate development,
operations, or commercial leader at a business operating multiple
territories in roofing, HVAC, solar or dental.

**Problem statement:** choose where to expand or intervene commercially
using reproducible market evidence, rather than unverified “AI lead
scores.”

**Proposed reporting pack (not committed capacity):**

- Three precisely identified city/sector territories chosen with the
  buyer, and a transparent source freshness/missingness table.
- Original market-size *hypotheses* distinguished from confirmed facts;
  buyer/competitor entities and local intent supported by citations.
- A priority dashboard covering verified search/service visibility,
  market coverage limitations and suggested next measurement, with
  **no fabricated demand forecast, revenue probability or ranking**.
- A concise decision memo: possible market focus, evidence confidence,
  underlying assumptions and what could invalidate the recommendation.
- An agreed cadence and correction process, validated with existing
  Predictive Intelligence and Research departments before promising
  an SLA.

**Founder-review conversation starter — DRAFT, NOT APPROVED OR SENT**

> We're building original, source-verified territory-intelligence
> briefs for multi-location operators. A pilot would compare a small
> number of buyer-selected markets, show what the evidence actually
> proves and flag what still needs verification before expansion
> decisions. Is there one territory decision your team is making now
> where this kind of independent research would be useful?

**Contract dependency:** named authorised buyer, precise territories
and deliverables, verified evidence coverage, rights for derived
analysis, internal quality acceptance, price/payment/cancellation,
and actual delivery capacity. **$4,000 is a test price, not a buyer
commitment or realised MRR.**

## C. Existing $199 SPC entry offer

The original roofing report source and 0600 provenance are verified.
The existing live Workspace message to SPC Construction & Roofing
about Euless commercial TPO repairs already exists.

- Reuse that **same thread**, not another cold blast.
- If a genuine appropriate reply arrives, offer the specific private
  scope from `docs/commercial/EMPIRE_BROKERAGE_SPC_EULESS_ONE_PAGE_SCOPE_20261018.md`.
- Current 2026 Common Crawl graph counts are historical associations
  only; dated live SERP measurements still need actual capture.
- Existing checkout `/buy` returning 200 does not establish a
  usable permitted payment route, a sale or settlement.

## Existing CRM / handoff contract (no new table)

Use **canonical EmpireOS CRM** and existing Strategic Partnerships.
Record only source-backed facts:

1. **Opportunity identity:** real company and authorised person/role,
   existing tenant/prospect identity, historical contact/suppression
   decision, no invented duplicate buyer.
2. **Problem and scope:** actual buyer expression, one named service
   and geographic territory, buyer-provided use case, intended
   deliverable and buyer-approved evidence claims.
3. **Offer:** existing code and exact negotiated price/currency/period;
   keep a price hypothesis separate until actually accepted.
4. **Rights and source QA:** source date, raw versus derivative
   licensing, commercial reuse, attribution, privacy, permission to
   deliver exact customer artefacts.
5. **Accepted terms:** signed/recorded acceptance, revision/cancellation,
   allowed distribution, contract or order reference.
6. **Settlement/fulfilment:** independent payment receipt and finality,
   actual delivery proof and recipient acceptance; reconcile those to
   the existing revenue-event and Economic Memory systems.

The new operator **does not** create or update CRM opportunities. It
generates an internal review pack and never infers buyer contact
permission from a business website, email or public dataset.

## Read-only integration and reproducible checks

`empire_os/data_brokerage_sales_activation.py` derives three precise
proposed packages from the existing 14-option portfolio, after
`scripts.review_data_brokerage_first_sale_closeout_20261018` has
validated the original sample SHA, private custody and commercial
holds. Each package carries named blocking evidence requirements and
an explicit owner lane. A stringent read-side validator rejects
modified amounts, missing rights, fabricated buyer acceptance or
changed contract/payment/revenue fields.

`scripts.review_data_brokerage_sales_activation_20261018` reads the
existing private `0600` catalogue, builds the same trusted
portfolio and source-attested packages, then returns a concise
status. `--show-packages` emits all proposed scopes and proof gates.

After source promotion, run:

```bash
cd /srv/empire_os
./.venv/bin/python -B -m scripts.review_data_brokerage_sales_activation_20261018 --read-only
./.venv/bin/python -B -m scripts.review_data_brokerage_sales_activation_20261018 --read-only --show-packages
```

**Expected:** `THREE_BROKERAGE_DRAFT_PACKAGES_READY_REVENUE_HELD`.
This is an accurate build milestone—not commercial activation.

### Outcomes and remaining real-world gates

**Closed in source:** reusable scope templates, exact price/source
mapping, source-catalogue and report integrity, read-only handoff,
proof obligations, owner-lane separation and non-escalating test guards.

**Still externally unverified:** agency or enterprise buyer need,
contact permission, scope agreement, capacity, current market data,
signed terms, rights, live payment, delivery and realised revenue.
Until then, there are **zero independently proven brokerage
subscriptions, paid reports or enterprise licence contracts** in
these reviewed sources.

Do not activate mail automation, route third-party raw data to a
marketplace or rewrite the main website while ASTRA owns the flagship.
