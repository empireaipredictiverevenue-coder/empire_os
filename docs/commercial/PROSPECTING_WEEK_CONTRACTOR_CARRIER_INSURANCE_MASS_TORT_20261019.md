# Empire AI — Revenue prospecting week, 19–23 October 2026

Founder direction 17 October: **sales first**, reuse existing B2B scraper/buyer scouts, finish contractor, insurance-carrier/TPA, claims and law/mass tort work. Email first. UK + USA. £0 additional paid acquisition. No artificial CRM prospect, fake transaction or mass mail.

## What actually exists (17 October, observed)

- The original `empire_os/agents/b2b_scraper_agent.py` is **legacy/not scheduled** (old `/root/empire_os`, feedback and retired `/v1/b2b/direct` hub path). `empire_os/agents/contractor_scraper_agent.py` uses placeholder Texas/California/Florida endpoints; `carrier_rosters.py` has HTML/JavaScript placeholders and the retired SQLite path. `biz_scraper.py` and `host_b2b_hunter.py` likewise include legacy output or hub semantics. **Do not execute, treat their rows as verified businesses, or restore old agents.**
- Real research owner is **existing** `empire-buyer-acquisition-scout.timer`, `empire-buyer-acquisition-team.timer` and `empire-buyer-deferred-enrichment.timer`. All were active with recent successful runs. Exact scout 17 October: **12 queries**, 30 domain cap, 12 site-probe cap, **10 research-only candidates**, **zero verified budgets/buyer purchases**, no outbound or DB writes. Previous query mix crowded out law/mass tort.
- Narrow fair-query correction on existing `empire_os/buyer_acquisition_scout.py` now allocates one bounded existing ICP query each to `legal_mass_tort_plaintiff_firm`, `legal_plaintiff_growth_firm` and `insurance_distribution_growth` alongside existing contractor/product streams, preserving the **12-query ceiling**. **This is insurance distribution research, not proof of insurer procurement.** Tests: 49 passed across scout, legal, carrier and claims, no live sends.
- Historical planned B2B Data Fabric code and tests persist in `/home/ubuntu/empire_worktrees/getlead_blitz_phase3_ingestion` and related existing Getlead/Blitz worktrees; **29 offline planning tests passed**. Canonical branch did not yet integrate that optional provider-neutral planner, and **it is not a functioning live scraper**. Reuse only after evidence of a missing capability; do not bring up another service.
- Buyer Network research queue: 214 candidate domains; 209 currently labelled home-services; 25 founder shortlist records, **not paying buyers**. Existing DFW founder packet: **8 contractors**, zero independently verified purchase intent and incomplete recipient suppression checks.
- **Claims Exchange research refreshed privately on 17 October:** 214 existing buyer-network research rows + 8 DFW contractor rows + 2 managed-repair official programmes = **224 candidate records**, **0 verified commercial matches, 0 revenue, 0 claims, 0 payouts or authorised outbound**. Existing private `runtime/claims_exchange/research_latest.json` mode 0600, OBSERVE. Settlement compensation/claims handling stays separate from normal B2B analytics.
- Mass-tort intelligence `runtime/legal_mass_tort/latest.json`: 5/5 components present, **live market evidence not bound**, no legitimate contracted legal buyer. Historical 547 candidate legal rows / 522 unique firm names / 122 mass-tort category are research archive only. Old sensitive-consumer Mass Tort agent is retired; never profile individual claimants or medical histories.

## Monday — focus on the easiest payable service, not enterprise theatre

Offers already in the **live founder-led catalogue**, with delivery scope confirmed but checkout OFF: **Competitor Search Gap $199**, **Search Opportunity Map $249**, **Technical Search Audit $299** (one-off USD, reviewed scope before manual contracting); consultancy assessment £2,500 can follow real business needs. Do not invent a cheaper price, charge an insurer a referral/settlement fee, or imply these services automatically collect payments.

### Contractor sale pipeline — existing eight DFW firms, not new leads

**First research and outreach-priority cohort:** PowerEdge Roofing & Home Repair (`poweredgetx.com`), 180 Roofing & Contracting (`180roofing.com`), Max Exteriors (`maxexteriors.com`), SPC Construction & Roofing (`spcroofs.com`).

**Second cohort, only if first qualifies:** LABA Roofing (`labaroof.com`), Mastercraft Roofing (`mastercraftroof.com`), RISE Roofing & Construction (`riseroofingconstruction.com`), Top Notch Roofing & Restoration (`topnotchroofingrr.com`).

Actual existing source: `runtime/revenue_strike/contractor_founder_review_latest.json`. All eight are **research-only**, not verified decision-makers or purchase commitments. Pick two businesses with direct first-party sites and verifiable current acquisition/SEO gap. Check exact-recipient contact history/suppression before individual, relevant founder-reviewed first touches. **Ask whether they would buy a specifically scoped $199/$249 report. Do not assert a guarantee, make storm-insurance claim promises or send eight near-identical emails.**

### Carrier/TPA and insurance — distinguish roles

- **Sedgwick Repair Solutions / Sedgwick vendor network:** official managed-repair and vendor registration exist (e.g. https://www.sedgwick.com/repair-solutions/managed-repair-network/ and https://www.sedgwick.com/en-gb/vendor-network/). These are NOT insurance carrier procurement invitations, approval of Empire AI, or evidence of guaranteed repair assignments. Find a named/official enterprise analytics procurement route and a specific data-buying problem first.
- **Crawford / Contractor Connection:** insurer-facing managed repair solution https://www.contractorconnection.com/for-insurers and separate contractor enrollment https://www.contractorconnection.com/for-contractors/. Insurance carrier customers and contractors are separate audiences. We are **not** submitting carrier/vendor enrollment applications on behalf of unlicensed/unverified companies.
- **Insurance distribution/agency analytics:** existing Scout lane `insurance_distribution_growth` is a *different* B2B buyer class from carriers/TPAs. Research relevant companies and real analytics procurement roles, with provenance. No claim settlements or lead commissions before verified commercial and applicable legal conditions.
- **Claims compensation/settlement track:** research only. No insurer claim handling, policyholder data exchange, claims negotiation or settlement percentage arrangements. A B2B source-verified analytics service is a different product and can be sold on its own merits.

### Law and mass tort — new B2B firm prospect research only

- **Seeger Weiss LLP**: verified official firm and mass-tort/product-liability practice https://www.seegerweiss.com/product-liability/ . Research authorised firm growth/operations/innovation decision-maker; do not use claimant intake as a cold business sales destination. No specific paying interest observed.
- **Milberg PLLC**: verified national plaintiff-firm mass tort and class action practice https://milberg.com/about-us/ . Same: target only firm-level market/search/court-source intelligence and an evidence-backed fixed deliverable, not individual claimants, leads or settlement percentages.
- Previously contacted law firms include Batrice, Shamieh, The Barnes Firm, Pond Lehocky and National Legal Research Group: **do not duplicate outgoing messages or imply positive buying responses**.
- **Permanent do-not-contact:** Gastley Law (explicit opt-out). **Dave Rainbow/Results Agency** already received an unanswered latest message; do not follow up or send the staged £2,500 proposal draft.

## 5-day execution: actual business activities, no new infrastructure

| Day (UK) | Commercial activity and evidence of progress |
| --- | --- |
| Monday 19 Oct | Check buyer/partner replies, freshest Scout batch and exact suppression. Choose **two** viable DFW contractor companies. Prepare evidence-backed report scope and 2 founder-review first-touch drafts. Separately identify true insurer/TPA procurement route. |
| Tuesday 20 Oct | After recipient clearance and explicit founder send decision, approach the two strongest *new* contractor decision-makers by email; offer the actual $199 or $249 scoped product. Record genuine answer, question or rejection; no volume boast. |
| Wednesday 21 Oct | Research 2 carrier/TPA enterprise analytics buyer contacts and 2 insurance distribution organisations. Distinguish procurement from vendor enrollment. Prepare direct B2B proposals only for a named current need. |
| Thursday 22 Oct | Verify Seeger Weiss and Milberg *firm-side* business decision routes, their actual case-market/search or growth problem, outreach history/suppression; prepare (not auto-send) two individualized B2B proposals. No plaintiff/case-level solicitation. |
| Friday 23 Oct | Review actual sent/answered/offered/accepted/paid events with separate counts. Pick the first real paying product, narrow or retire unproductive sectors, and report real revenue without inflated lead counts. |

**Weekly target:** 8–12 carefully reviewed company opportunities across lanes, at most a small batch of genuinely new, verified decision-makers for founder-approved personalized emails; **one concrete request for a fixed-price report and ideally one accepted payable offer**. Targets are goals, not promises.

**Complete condition:** meaningful decision-maker response or signed scoped first transaction, proven service delivery, and real payment. A loaded scraper, 522 historical law firms, or 224 insurance research records is not a completed sale.

**Owner boundaries:** existing Buyer Scout/CRM/EmpireDB; existing ASTRA website owner unchanged. No mass outreach, new agents, DBs, deployments, financial activation, carrier enrollment, consumer profiling or paid traffic. All claims of permission/revenue must come from primary proof.
