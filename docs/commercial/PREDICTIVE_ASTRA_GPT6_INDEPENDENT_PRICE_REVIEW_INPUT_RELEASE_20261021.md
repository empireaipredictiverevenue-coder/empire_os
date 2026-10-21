# ASTRA GPT-6 review input: Predictive Cloud, Intelligence and all 86 products

Date: 21 October 2026. Owner: existing Predictive branch and guarded immutable private runner. **Not** an independent model review or a product pricing approval.

## Critical evidence confirmed from original root-owned catalogue
Original catalogue has 86 SKUs, each `actual_revenue=false` in this snapshot. Catalogue state `VERIFIED` and version `VERIFIED` for 26 SKUs, 60 unverified. 35 SKUs are marked active, of which **nine are active with unverified catalogue/version**: four Commercial Exchange seats and five Predictive Revenue enterprise products. This is a genuine launch-readiness contradiction to challenge (not proof any product has active paying customers). 51 legacy Recovered MRR SKUs are inactive.

Price-source custody: 35 founder-approved price records (only 26 have complete comparable internal cost ceilings), 26 unapproved legacy consensus amounts, 20 unpriced single-source candidates and five historical conflicts without sellable price:
- Meetily Pro: metadata candidate $299/month 2026-06-20; pricing candidate $249/month 2026-06-23. Difference $50/month.
- Meetily Enterprise: $999 versus $499/month. Difference $500/month.
- Elite Scraper Starter: $149 versus $49/month. Difference $100/month.
- Elite Scraper Pro: $499 versus $149/month. Difference $350/month.
- Elite Scraper Enterprise: $1,999 versus $399/month. Difference $1,600/month.

These are **unapproved, conflicting historical amounts**. Neither newer timestamp nor higher number gives commercial authority. Verified original use case, per-plan feature entitlements, provider rights, true delivery cost, support/SLA, a contract and buyer willingness to pay are missing. Do not choose any figure, charge or publish.

## Pinned review input implementation
`empire_os/predictive_astra_product_review_packet.py` reads only the existing root-owned catalogue as passed by `predictive_catalog_readiness_bridge` and the source-aligned private competitor report. It checks exact 86 product identities, price units and amounts, original reported readiness and revenue status, immutable historical candidate chronology, per-SKU evidence denials and source-reported counts. It constructs a deterministic SHA-256 of its review body tied to the original snapshot SHA (integrity detection only; neither is a trusted signature or EmpireDB issuer proof).

`scripts/review_predictive_comparison_20261021.py` gains:
- `--astra-review`: summary/counts + reviewer task contract + original snapshot SHA and packet SHA, no 86-SKU dump.
- `--astra-review-all`: all 86 SKU risk dossiers and historical price conflict values with a SHA-pinned source digest.

The guarded `empire-predictive-observe` executable gains `comparison-astra` and `comparison-astra-all`; the user's private `empire-predictive-comparison --astra` and `--astra-all` can be pinned to the same private release after testing. This is *review input prepared*, not a model execution.

## Required independent ASTRA GPT-6 challenge
A **separately executed GPT-6 reviewer**, with an auditable model invocation and exact release/input identity, must independently:
1. Rerun original-version checks and tenant/auth attack tests; scrutinise whether active unverified entries can reach customer actions.
2. Compare original product entitlements and actual implementation status with commercial promises; challenge source licence and use rights.
3. Verify the five historical price conflicts using source-owner/founder evidence, not an arbitrary timestamp/mean.
4. Reconcile all per-SKU actual expenses, settlement terms, refunds, compute budgets, conversion rates and quantified buyer benefits before concluding the price is justified.
5. Verify competitor public prices and contract-unit equivalence, including onboarding, licences, cap volume, support and privacy boundaries.
6. Require authenticated prospective original conversion forecast readback matched to independently verified customer outcome before claiming forecast accuracy, realised profit or scientific performance.
7. Evaluate Cloud control, evidence, compute and serving planes, isolation, per-tenant quotas, job retries, SLO and rollback.
8. Produce a per-SKU severity-ranked outcome and provenance-backed recommendations with exact code/commit and original source receipts. Neither ASTRA nor a reviewer report may modify founder-approved prices or customer/payment authority without separately authorised gates.

## Independent execution availability
The existing `empire-astra-dispatcher.service` is a bounded workflow dispatcher; it **does not itself provide an independent GPT-6 product reviewer**. Its last observed one-shot service exited successfully but did not issue a review receipt. Do not claim otherwise or silently route a premium AI call through it. The private packet's `independent_astra_gpt6_invocation_executed` remains false until an independent real invocation and attributable review is recorded and verified.

## Release boundaries
This release adds only pure review computation and a private checksum-pinned operator command. No production Cloud service reinstallation, tenant/database role, public product quote, forecast issue, model retraining, money movement or outbound send is authorised. Existing original price basis and root-owned catalogue remain untouched. Review source freshness and pinned release manifest are checked on each operator run.
