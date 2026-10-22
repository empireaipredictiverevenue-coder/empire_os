# EmpireOS: first two public B2B requests — pre-offer evidence review

**22 October 2026. Development-only, OBSERVE. No customer outreach or revenue recognised.**

## What was tested

The existing Jev public-source owner packet identifies two public supplier-search
requests. Neither public post establishes the legal company behind the
account, business authority, a still-active purchase or marketing consent.

The original Jev / Buyer Scout case review remains authoritative for
identity, geography and commercial status. This incremental read-only
pre-offer check additionally consumes the **existing** private Lead Supply
aggregate, without opening any individual prospect records.

At review the canonical Lead Supply summary was fresh:

| Aggregate fact | Count |
|---|---:|
| Selected source inventory for research | 180 |
| Evidence holds | 84 |
| Awaiting verified buyer capacity | 96 |
| Independently sellable records | **0** |
| Qualified buyers and live accepted buy-boxes | **0** |

The selected 180 records are neither a licensed, current 50-row batch nor
confirmed Tennessee roofing appointments. Their two hold categories account
for the entire selected cohort. No territory match or contacted buyer is
inferred. The historical **32,899 prospect** reservoir also remains
unapproved for resale or automatic marketing use.

## First option: Knoxville roofing

Publicly stated terms: **10% of closed roofing jobs** originating from
qualified appointments, no fee paid upfront. Unknowns remain:

- Direct, voluntary legal business identity and the representative's
  authority to agree on behalf of the business.
- The need remains open, exact territory, genuine appointment definition,
  site visit/booking acceptance, exclusions and consumer consent.
- Organic appointment generation and traceable handoff capabilities with
  no paid traffic; Chicago campaign routing is not Knoxville proof.
- Auditable closed-job linkage, payout timing, rejected/cancelled jobs,
  reporting access, dispute and settlement rules.

There is **no guaranteed commission revenue**. A small synthetic,
non-contact appointment acceptance test can precede negotiations, but
cannot be presented as fulfilled leads or booked appointments.

## Second option: US web agency

Public June post says **$150 after review and acceptance of a 50-record
batch**, with a possible 10% commission on fully paid customer deals.

- $150 is a **conditional maximum base payment for one fully accepted
  batch**, not realised revenue, a guaranteed price for partial acceptance
  or evidence of a paying client.
- This would demand source-proven, business-only company records, a
  clear website-status test, de-duplication, jurisdiction/territory,
  permitted field use, and a reproducible human QA review.
- Actual validation labour, source expenses, errors, rejections, disputed
  acceptance and payment collection are unmeasured. A historical export
  does **not** provide ready-to-sell 50 records.
- Do not assume legal permission to distribute public personal contact
  details merely because they are visible in a listing.

Only after explicit business identification, request reconfirmation,
source-rights approval and written acceptance/payment terms should
an internal, limited private **zero-delivery** QA exercise be considered.

## System improvement delivered

The new `empire_os/jev_preoffer_evidence_review.py` is a small
non-executing reader that combines the existing **Jev counterparty evidence
packet** with the canonical **Lead Supply research aggregate**.

The `review_jev_public_preoffer_20261022.py` one-shot runner pins the
original public-source receipt and writes
`JEV_PUBLIC_TWO_CASE_PREOFFER_REVIEW_20261022.json` using a new
non-overwriting path. The output contains no individual records, business
emails, postal addresses or prospect IDs.

The gate fails closed if either public counterparty suddenly claims an
unreviewed buyer, supplier fulfilment, contact clearance or payment. It
also refuses to treat more advanced Lead Supply summary authority as
permission to market to a particular public poster without the separate
legal business, rights, contract and CRM identity reviews. If a snapshot
is stale, its inventory totals are withheld.

The research owners can now prioritise:
1. Reconfirm original requests and request business identity voluntarily,
   without inferring identity from an online alias.
2. Verify one small organic supply workflow and company data provenance,
   **without promising or exporting** a customer batch.
3. Get real, written payout, attribution and acceptance definitions before
   any exact commercial proposal is drafted.
4. Run the existing CRM tenant-contact-history and opt-out checks before
   seeking an explicitly approved outreach action.

No production changes, outbound, CRM writes, contact scraping, payment
activation, automated Jev decisions or newly registered agents were made.
