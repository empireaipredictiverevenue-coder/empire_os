# EmpireOS Jev — bounded supply QA mechanics canary

**22 October 2026 · isolated worktree · no real company/person records, network requests, delivery or commercial execution**

## Business question

Could a small, low-cost business-website review workflow identify whether a
candidate merits further source verification **without** confusing
historical EmpireDB entries, missing listing fields, or public information
with qualified and permitted sales leads?

The earlier pre-offer gate read the current Lead Supply aggregate:
**180** selected research records, **84** held for evidence, **96**
awaiting verified buyer capacity and **zero** immediately sellable records.
The first-person buyer identities behind the Tennessee roofing and the US
web-agency public posts remain independently unverified. No company name,
contact permission, signed offer, accepted batch or paid receipt was inferred.

## Implemented internal QA canary

`jev_internal_b2b_sample_qa.py` uses **11 fictional companies and reserved
.example domains** with individually specified source-review and two-reviewer
outcomes. The logic is deterministic and never requests external inference.

| Synthetic review outcome | Cases |
|---|---:|
| Two-reviewer website-issue pattern with all mock checks passed | 2 |
| Duplicate domain | 1 |
| Listing omitted website field (not proof of no website) | 1 |
| Source-rights hold | 1 |
| Original-source review missing | 1 |
| Fictional company-identity hold | 1 |
| Reviewer disagreement | 1 |
| Reviewed valid site, no problem asserted | 1 |
| Website status inconclusive | 1 |
| Missing primary website examination | 1 |
| **Total** | **11** |

The two mock QA passes are **not two real leads**. No site was fetched or
independently inspected, and no real company matched. A claimed
`REVIEWED_SITE_PROBLEM` requires actual original-site evidence and dated
independent review before it could count toward even a *real internal*
sample. Source licensing, country/purpose compliance, duplicate suppression,
website status and buyer-acceptance terms remain separate.

## Payment and commercial reality

The web-agency author's public offer advertises **$150 per fully accepted
50-record batch**, equivalent to **$3 gross per accepted record if all 50
are accepted**. Partial-batch payment, rejection, payment proof and
commission terms are unverified. Synthetic passes have zero commercial
value. Actual source collection, verification labour and error/rejection
cost have not been measured, so no profitability or capacity claim is made.

The Tennessee roofing request is a different supply product:
**qualified appointments**, with a reported 10%-of-closed-jobs commission.
A business website-status QA fixture cannot prove a single opt-in
Knoxville roofing appointment, route connection, close event or accepted
commission. Keep those offers entirely distinct.

## Next bounded real-world execution gate

1. Existing Research/Data Quality owner identifies a **lawfully reusable,
   business-only source**, confirms source licence/purpose and provenance
   first, without exporting individuals or raw CRM identities.
2. Select a small, separately approved sample of **up to five businesses**
   from a relevant UK/US niche and territory; maintain source custody.
3. Independently verify canonical business identity, original source date,
   website status and reviewer agreement. Do not treat blank directory
   fields as proof that a website is absent.
4. Log internal time/QA error and duplicate counts; *do not* deliver the
   sample or reuse phone/email fields until legal rights, purpose and
   buyer acceptance rules are documented.
5. Get direct buyer identity and current purchasing needs from voluntary
   business evidence; apply the CRM tenant and suppression checks before
   any reviewed, founder-approved contact decision.

The new immutable output
`JEV_WEB_AGENCY_SYNTHETIC_QA_CANARY_20261022.json` fingerprints its
fictional sample and the earlier Jev pre-offer evidence. It records
**0 real records evaluated, 0 real accepted, 0 original network calls,
0 contacts extracted, 0 CRM/database writes, 0 outbound and 0 revenue**.

## Rollout

- Only a development branch and isolated worktree were changed.
- Original production EmpireDB, Buyer Scout, Jev, CRM and mail services
  remain unchanged.
- No extra provider, GPU, packages, credentials or network traffic used.
- This is **proof of QA rejection controls**, not proof of real-world
  lead supply or payment readiness.
