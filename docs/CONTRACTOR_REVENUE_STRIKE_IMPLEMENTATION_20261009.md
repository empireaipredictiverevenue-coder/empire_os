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
