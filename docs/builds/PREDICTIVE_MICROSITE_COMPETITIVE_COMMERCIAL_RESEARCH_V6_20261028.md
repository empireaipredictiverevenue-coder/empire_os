# Predictive Microsite Factory — Competitive Opportunity & Commercial Underwriting

**Original lane:** `agent/predictive-microsite-slopmonster-20261026`
**Date:** 28 October 2026
**Scope:** Executive research screening, competitive alternatives, commercial evidence gaps. **No website, SEO release, outreach, payment, new AI agent, database or scheduler.**

## Why this upgrade matters

An editorially sound research draft can still be a weak commercial opportunity. The prior V4 queue did not structurally distinguish **reader usefulness** from **differentiation versus alternatives**. A three-source Manchester heat-pump research draft correctly reached `MEASURE_FIRST_PARTY_INTENT`, but independently accessible established resources already cover much of the same advice.

The new research overlay makes incumbent solutions explicit **before** investing in additional acquisition research or proposing a public marketing product. It does not mistake self-reported observations for proven market saturation, an unmet gap, buyer demand or attributable revenue.

## Minimal integration — existing implementation only

- `empire_os/microsite_ranked_production_queue_v4.py` accepts an **optional** bounded `competitive` evidence dossier with exact candidate/market/keyword binding and author-reported UTC observation date (within 30 days).
- The schema `empire.microsite.competitive_desk.v1` is read-only and explicitly `RESEARCHER_DESK_OBSERVATIONS_UNVERIFIED`. Each source must have a unique direct public HTTPS URL, publisher, source type and narrowly enumerated **observed reader job**. Malformed, stale, fake-scope, spoofed, local and unsafe sources are rejected; no URLs are fetched by this module.
- Each queue row retains the original `research_priority_points` and existing V4 schema. Added `competitive_screen` and `commercial_underwriting` are explanations, **not a parallel ranker**.
- When a research-desk-qualified page has 2+ observed alternatives, next action becomes `VALIDATE_DIFFERENTIATED_READER_JOB`, owned by Marketing Research, **before** more ranking/acquisition work. **No claim of a verified competitive gap, willing buyer or unique value is made.**
- `commercial_underwriting` itemises missing exact buyer contract, billable acceptance definitions, consented identity joins, payout, fulfilment and acquisition costs. Until independently evidenced, contribution, CAC, breakeven and profit are **null**, not estimates disguised as facts.
- The existing `scripts/review_ranked_microsite_outcomes_v4_20261027.py` accepts one optional `--competitive-source` private dossier. The original release/outcomes, five existing website campaigns and all other queues/owners remain unchanged.

## Genuine current external comparison — 28 October 2026

Original private Manchester heat-pump research candidate `microsite_facd8e65d37634b91a6d` was compared against four live public information resources:

| Independent public resource | Observed topics covered in public page |
| --- | --- |
| [GOV.UK heat-pump suitability checker](https://www.gov.uk/check-heat-pump) | House suitability and indicative cost comparison |
| [MoneySavingExpert grants guide](https://www.moneysavingexpert.com/utilities/heat-pumps-grant/) | Boiler Upgrade Scheme conditions, grant amounts and installer-selection process |
| [MoneySavingExpert heat pumps explained](https://www.moneysavingexpert.com/utilities/heat-pumps/) | Cost comparison, suitability and homeowner decision guidance |
| [Manchester City Council energy support](https://www.manchester.gov.uk/homes-and-property/energy-efficiency/get-support-for-your-energy-improvements) | Local funding and support channels |

These were reviewed from public pages, but stored in the factory as **researcher observations**, not independent cryptographic content-provenance facts. The City Council information references a prior scheme window; the desk researcher must independently recheck current scheme terms before relying on it as current eligibility or funding advice. **No page is shown to lack a feature merely because its researcher didn't list it.**

Private original source dossier:
`/home/ubuntu/empire_releases/predictive_microsite_uk_source_research_20261028/competitive_public_alternatives_desk_20261028.json`

### Observed change to the same original V4 CLI

| Field | Before competition observations | With documented alternatives |
| --- | --- | --- |
| Legacy priority points | 15 | 15 (unchanged compatibility) |
| Desk decision | `MEASURE_FIRST_PARTY_INTENT` | **`VALIDATE_DIFFERENTIATED_READER_JOB`** |
| Public alternatives recorded | Unknown | 4 desk-research URLs |
| Verified competitive gap | Unknown | **False / not verified** |
| Distinct verified reader benefit | Unknown | **False / not verified** |
| Unit payout / CAC / contribution | Unknown | **Null / no verified terms** |
| Publishable pages | 0 | **0** |

The original read-only V4 queue command succeeded using the actual existing Manchester source + original commercial review + private competitive dossier, yielding `PRIVATE_RANKED_RESEARCH_QUEUE`, `production_changed=false`, original published five campaigns intact, zero new services, and an actual private queue:
`/home/ubuntu/empire_releases/predictive_microsite_uk_source_research_20261028/original_v4_competitive_final_20261028/ranked_research_queue.json`
SHA-256: `393668c26b9e076a4e2126ac821b98efe0c633ae81c0e7985d1d0918a1bf7613`.

## Executive research protocol for the next owner action

1. **Define the distinct customer job first:** one observable, useful outcome beyond general grants/suitability/cost summaries. E.g. a property-specific decision sequence joining official source lookup and a reusable checklist. This is only a hypothesis to validate against existing alternative services.
2. **Test the supposed gap against each alternative:** record page URL, observed date, exact task and what the existing service actually covers; a missing note is **not** evidence of absent functionality.
3. **Verify a feasible, consented buyer/product path:** request contract acceptance, lead definition, source restrictions, live fulfilment, refund and chargeback conditions from the original commercial owner; do not derive a buyer from a keyword.
4. **Only after those facts exist**, let the original SEO/GSC owner supply exact first-party search interest; original site owner may then consider one distinct useful experiment under existing controls.
5. **Finance evidence must be explicit:** payout minus genuine acquisition, servicing, compliance and return costs, matched to independently verified accepted/settled events. No generic lead benchmark or model forecast substitutes for this.

## Verified engineering acceptance

- **210 tests passed** across original factory/competitive/SlopMonster/source policy/commercial/forecast/ranking/measurement and keyword tests (one existing AnyIO deprecation warning).
- New competitor tests cover accurate scoped source mapping; missing competitor info not treated as a market gap; copied/fake evidence rejected; HTTPS, local URL, stale UTC timestamp, spoofing, duplicate and cross-scope failure; existing V4 CLI private end-to-end output; null economics.
- **Read-only, no public site or owner release, zero observed revenue.** This is original marketing/source work only.

## Next original workstream milestone

Build verified differentiated *reader-job* briefs and economically feasible product hypotheses **before** producing another batch of sites. Feed those briefs into existing ranking, then use real first-party data and only original owners for any subsequent campaign or publication.
