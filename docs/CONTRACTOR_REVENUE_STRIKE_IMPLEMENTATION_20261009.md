# EmpireOS Revenue Strike: DFW contractor-commercial review

Implementation date: 9 October 2026. **Existing EmpireOS**, not a new platform or independent CRM.

## Objective and verified facts

Use the existing September DFW contractor discovery cohort as a bounded pipeline for **fixed-fee B2B marketing/opportunity-intelligence pilot research**, not a list of companies already willing to buy Empire's services. The original eight company domains are historic. The source snapshots were manually reviewed on 2026-10-09; they are NOT real-time capacity, procurement intent, verified insurer roles, regulated insurance licence status or company registration evidence.

- The seven current-site research candidates (not qualified customers) are PowerEdge, Max Exteriors, 180 Roofing, LABA, RISE, SPC, Top Notch Roofing & Restoration.
- Mastercraft historical domain redirects to a differently named Cedar Crest Roofing website: fail closed under identity-change hold. No auto-merger or cross-company contact.
- PowerEdge has an independently viewed *public company webpage* advertising sales roles; this is a growth-fit research signal, NOT confirmed buying interest. Its claimed crew/roof capacity receives zero score weight unless independently verified.
- Public business directory entries corroborate the general existence of some company names in DFW, but these do not independently prove company registration, ownership, domain control or licensing.
- Website statements around insurance claims should be reviewed under the relevant Texas rules; do not treat their marketing claims as lawful adjusting authority.

Evidence references:
- https://poweredgetx.com/careers
- https://poweredgetx.com/
- https://www.maxexteriors.com/areas/roofing-contractor-fort-worth-tx
- https://180roofing.com/service-areas/fort-worth/
- https://www.spcroofs.com/contact
- https://labaroof.com/contact
- https://www.topnotchroofingrr.com/

## Integration points — existing platform only

- `empire_os/claims_exchange/`: the previously-tested V2 candidate normalization, public site dossier, safe economics and claims/offers gates are now *copied into the original EmpireOS application*, not a separate runtime.
- `empire_os/storm_contractor_review.py`: aggregates historical DFW cohort + dated first-party website observations + bounded same-domain public market signals; deduplicates and weights only research relevance. Capacity claims receive zero points, and model scores never confer outbound authority.
- `scripts/refresh_contractor_revenue_review.py`: a **one-shot command**, NOT a timer, writes an owner-readable (mode 0600) JSON snapshot only when explicitly invoked with `--write`. Without the flag it only prints non-sensitive summaries.
- `runtime/revenue_strike/contractor_founder_review_latest.json`: one evidence snapshot under the existing Revenue Strike runtime location. No contact information, contract PDFs, SMTP credentials, personal data or provider signing links.
- `empire_os/founder_dashboard.py`: adds a safe aggregate `contractor_revenue_strike` block to the *existing* founder overview. It exposes counts/status only, never prospect-level contacts or internals. The API's standard auth posture is unchanged.
- All binding agreements route through `/v1/deal-room` and the existing Documenso integration, not another signing service. They are currently marked `NOT_CREATED`.

## Work remaining before first legal outreach or paid pilot

1. **Independent identity**: corroborate companies and actual domain control; retain changed-identity quarantine. Distinguish Texas state-wide roofing licensure from local permit/registration requirements; separate from regulated public adjusting.
2. **Real B2B need**: obtain current evidence that a contractor wants/needs growth or territory intelligence, including decision-maker and service capacity. Hiring and claimed capacity are *research relevance only*.
3. **Product terms**: confirm an actual EmpireOS priced product and fulfilment capacity. The proposed $1,500/14-day entry pilot is a *hypothesis*, not a binding quote, discount approval or verified return.
4. **Consent and suppression**: inspect canonical EmpireDB prior contact/suppression and require a verified owned professional mailbox and founder authorisation for every outbound act. No silent send through Gmail, Resend or AWS.
5. **Contracting**: legal/founder-reviewed immutable PDF, Documenso signatures and independent signed-PDF/audit verification. Binding terms are NOT created by a review score.
6. **Payment and delivery**: verified USDT BSC payment and fulfilled deliverables; recognized revenue remains zero unless genuine payment/fulfilment evidence proves otherwise.

## Read-only repeat / snapshot reproduction

```sh
cd /srv/empire_os
PYTHONPATH=. ./.venv/bin/python scripts/refresh_contractor_revenue_review.py --as-of 2026-10-09
# To update the existing OBSERVE snapshot only:
PYTHONPATH=. ./.venv/bin/python scripts/refresh_contractor_revenue_review.py --as-of 2026-10-09 --write
```

No agents sent outbound, accessed private claims, signed documents, started services, changed DB rows, incurred paid traffic or issued a fee in this implementation.


## Third-party identity and canonical contact-history upgrade — 2026-10-09

The same existing Revenue Strike review now ingests the manually reviewed
`docs/DFW_CONTRACTOR_INDEPENDENT_EVIDENCE_20261009.json` with
`empire_os/storm_contractor_independent_evidence.py` as a pure corroboration
overlay. Direct BBB profile website links validate **directory website/name
matching**, not state incorporation, corporate-control, buyer intent or
consent to outreach:

- Max Exteriors: https://www.bbb.org/us/tx/desoto/profile/roofing-contractors/max-exteriors-llc-0875-91051523
- 180 Roofing: https://www.bbb.org/us/tx/mesquite/profile/roofing-contractors/180-roofing-contracting-llc-0875-90938685
- SPC Construction & Roofing: https://www.bbb.org/us/tx/euless/profile/roofing-contractors/spc-construction-roofing-inc-0825-155405122

**Holds:** RISE similar-name BBB profile links a different domain,
https://www.bbb.org/us/tx/southlake/profile/roof-structure/rise-roofing-construction-0825-1000215721 ;
Top Notch same-name BBB profile shows business age/rating inconsistent with
the reviewed prospect website, and does not establish the same domain,
https://www.bbb.org/us/tx/wylie/profile/residential-roofing/top-notch-roofing-restoration-0875-91348579 .
Mastercraft historical domain already has a different-company redirect hold.
Do not infer that any conflicting company is the same legal entity.

**Existing canonical prior contact reader reused** from
`scripts/materialize_company_routed_buyer_review.py` via optional
`--check-contact-history` in the existing
`scripts/refresh_contractor_revenue_review.py`. This is an opt-in, bounded
**read-only** EmpireDB check and requires the existing operational
`EMPIREDB_DSN`. Failed checks do not overwrite the prior review snapshot.
A negative company-domain match NEVER clears individual recipient suppression
or confers authority to email anyone. No separate database, service, timer
or CRM has been created.

Run with the existing authorised read-only EmpireDB service environment:

```sh
PYTHONPATH=. ./.venv/bin/python scripts/refresh_contractor_revenue_review.py --as-of 2026-10-09 --check-contact-history
```

A separate explicit `--write` is required to persist the OBSERVE-only
review snapshot. If the DB role/env is unavailable, this fails closed
instead of claiming that suppression has passed.

**Ranking is for research time allocation only.** $1,500 pilot fee and 14
days remain hypothetical. Active commercial need, confirmed person-bound
contact route, exact recipient suppression, founder send approval,
Documenso contract issuance, valid USDT BSC payment and fulfilled outcomes
all remain unverified.

## Existing relationship registry reconciliation (10 October 2026)

To avoid starting another CRM or forgetting conversations, the existing
`scripts/refresh_contractor_revenue_review.py` now directly consumes
`runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json`
through `empire_os/storm_contractor_relationships.py`. The join is exact
company domain, read-only and aggregate. Matched or ambiguous domain = HOLD
for review; *no match* = **not sufficient to assert zero prior contact** and
never a release for outreach. The join does not return email addresses,
thread IDs or the unrelated buyer CRM's private correspondence in contractor
snapshots. Gmail evidence is treated as untrusted historical context only.

10 Oct 2026 check: the source registry contained 185 relationships (4 two-way
relationships) and matched **zero of the eight contractor domains exactly**;
this is not a canonical suppression check, company registration, or interest
confirmation. The full source registry remains in its existing directory; no
second relationship registry or campaign list was created. The founder
overview shows only summary counts and read-only state.

Official public state identity-verification sources, where actual entity
results are not yet obtained:
- Free Texas Comptroller taxable-entity-status search by official name:
  https://comptroller.texas.gov/taxes/franchise/account-status/search.php
- Texas Secretary of State **SOSPortal** now handles official business filings
  and searches (modernisation launched 29 September 2026):
  https://www.sos.texas.gov/corp/business-law.shtml
- SOSPortal currently states a $1 search fee; **no fee or filing was executed**.
  https://www.sos.state.tx.us/corp/sosda/index.shtml
- A BBB listing, a sales-hiring listing, and self-published capacity claims
  are context for qualification, not official legal entity or ownership proof.

Regulated insurance claims/settlement percentage terms remain prohibited in
the default fixed-fee contractor-growth offer without counsel-approved scope
and appropriate licensing. In particular, no claims adjusting or percentage
of settlement services are implied.

**Revenue checkpoint:** Top candidates Max Exteriors, 180 Roofing and SPC
have directory-to-site name/domain corroboration and require official
registration and authorised buyer-contact evidence. PowerEdge remains a
research lead based on first-party hiring/context. No verified decision-maker
conversation, no approved send, no Documenso envelope, no paid order, and
no realised revenue from this cohort.
