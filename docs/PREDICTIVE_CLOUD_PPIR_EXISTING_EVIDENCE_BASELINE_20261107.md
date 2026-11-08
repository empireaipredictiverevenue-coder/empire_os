# Predictive Cloud — PPIR evidence baseline (7 November 2026)

**Scope:** read-only evaluation of the **existing** EmpireOS Search Fabric/Decodo discovery and monthly provider attempt records; no new crawler, API, database, provider calls, pricing, outreach, activation or production write. This is complementary to, and does not replace, the founder-approved release handoff in GitHub issue #156.

## Verified current production evidence (20:27 UTC)
- Source: protected mode-0600 `runtime/search/decodo_service_business_discovery.json`, schema `empire.decodo.service_business_discovery.v1`. Exactly **4** distinct candidate domains: **4** recent search result observations, **0** first-party verified customers **in this artifact**, **0** outreach-authorized. Individual domains and search terms intentionally omitted from output.
- Source: protected mode-0600 `runtime/search/decodo_request_ledger.json`, schema `empire.search_fabric.decodo_request_ledger.v1`. **16 provider request attempts** logged in 2026-11 (6 on Nov 6 and 10 on Nov 7), `provider_hold=false`. Attempted requests do **not** prove 16 successes, and there is no request-ID join to the 4 candidates. A 4/16 "conversion rate" would be fabricated.
- Founder Data Products live GET `http://127.0.0.1:8766/v1/founder-data-products`: **HTTP 200**, **8** data-product definitions, `mode=OBSERVE`, **0** priced, **0** claim release-ready, `execution_authority=none`. Catalogue readiness is not customer product fulfilment.
- Customer Data Intelligence GET `http://127.0.0.1:8771/v1/data/usage`: **HTTP 404**, search health GET 200. Port 8771 hosts Search Intelligence and is **not** assumed to be the intended customer gateway.
- Current founder auth/route/meter integration worktree commit `882824d6b` before PPIR update, 82 feature/CRM/SQL tests passed. No canonical production metering migration or authenticated transaction evidenced.
- A fixed source cohort has **not** been independently ground-truth labelled. Metrics below are therefore not competitive benchmark results.

## PPIR metrics: defendable meanings

| Pillar | Observed now | Unknown, cannot claim |
|---|---|---|
| **Precision** | 4 distinct, recent search candidates; 0 promoted first-party identities in this artifact | Identity precision, precision@20, recall, record-level factual accuracy |
| **Power** | 16 Decodo request attempts logged for current billing window | Successful throughput, p95 latency, actual provider spend, cost per verified entity, scaling |
| **Intelligence** | Existing evidence-driven product definitions and predictive modules | Independent predictive uplift, calibration, better buyer decisions versus matched baseline |
| **Revenue** | 8 unpriced product definitions; no customer release authorisation | Any PPIR-attributable sale, unit economics, realized gross profit, paying customer count |

**Non-negotiable:** Unknown is `null`, not zero or an optimistic placeholder. Search result discovery is not qualified customer supply. The benchmark script redacts individual URLs, source titles, contact data, secrets and costs; no external calls and no write operations.

## Bounded verification delivered
- Script: `scripts/review_predictive_cloud_ppir_existing_evidence_20261107.py --read-only`.
- Tests: `tests/test_predictive_cloud_ppir_existing_evidence_20261107.py`, **20/20 PASS** including forged qualification, unsafe/duplicate domain, naive/future timestamp, stale data, inconsistent provider ledger and file/symlink checks.
- Uses the **existing committed** `empire_os.scrapling_source_evidence._public_url` syntax guard. The newer live `empire_os.search_fabric.decodo_service_customer_admission` is untracked and owned by another source owner; it is **not imported/copied/overwritten**.
- This only establishes defensible data provenance **within the selected two artifacts**. It does not verify first-party DNS, source rights, accuracy, buyer intent, spend or ROI.

## Smallest evidence-producing next sequence, after recovery
1. Finish issue **#156** via original DB/recovery and gateway owners: fresh backup + independently verified isolated restore; verify security, signed founder token and canonical metering; one genuine cost-capped founder-only API request. Do not release paid provider traffic or arbitrary site audits.
2. In the original Search Fabric owner's lane, choose one **fixed** small discovery cohort across two sectors and verify original company domains directly from lawful first-party sources. Record reviewer, snapshot timestamp, accepted labels and explicit non-matches/uncertainty; preserve all false positives for precision. These labels are not currently in the Decodo discovery artifact.
3. Add per-request correlation IDs and validated provider receipts in the **existing** source pipeline; record success/failure, exact provider charge or `UNKNOWN`, p50/p95 latency and idempotent quota reservations. Don't infer costs from mock reservations.
4. Score independently reviewed `precision@20`, entity accuracy, quality-adjusted throughput and unit cost versus a matched no-intelligence baseline. Initial proposed targets (not achievements): **>=95%** first-party identity evidence coverage and **>=80%** verified precision@20 with clear sample sizes/confidence, then graduated volume within the independently authorised budget.
5. Only when source rights, qualified customer willingness to pay, accepted terms and attributable fulfilment are verified should the Revenue pillar count realized gross profit. Reuse Smart CRM, commercial usage metering and original Data Product catalogue, not a parallel SaaS or billing system.

**Release state:** `BENCHMARK_FOUNDATION_VERIFIED; PERFORMANCE_AND_REVENUE_UNPROVEN; CUSTOMER_API_RELEASE_HELD`.

## 8 November 2026 — source admission reconciliation: four RAW ≠ four admitted

**Live read-only replay, no paid provider call:** the private `runtime/search/decodo_service_business_discovery.json` contains 4 recently observed search-result domain rows. The original Search Fabric owner module `empire_os/search_fabric/decodo_service_customer_admission.py` was executed **read-only** against exactly those 4 rows, using its existing `domain`, `service_query` and `NON_COMPANY_RESULT_TITLE` policy; it returned **2** `PASS_RESEARCH_ONLY` and **2** rejected:
- `kahnmechanical.com`: research admission policy pass (not independently verified legal entity, buyer, prospect, contact, customer or licensed output).
- `ich-services.co.uk`: research admission policy pass with the same restrictions.
- `cedur.com`: rejected as `non_company_result_title` on the specific search-result row; this does **not** assert that the website itself is not a business.
- `ziprecruiter.com`: rejected as `untrusted_or_excluded_source_domain` and `non_company_result_title` (job-board result).

Two current publicly retrieved company-website pages independently showed relevant **first-party service claims** at `https://www.kahnmechanical.com/` (commercial HVAC, Dallas–Fort Worth) and `https://ich-services.co.uk/` (UK facilities-management and M&E services). These are site claims and **do not prove legal entity identity, intent to buy, service quality, advertising consent, source redistribution rights or predictive model uplift**. The current provider source licence/re-use right is **still unverified**. Do not create contacts, CRM identities, outreach permissions or customer-facing predictions on this observation alone.

**Narrow original PPIR script correction:** `scripts/review_predictive_cloud_ppir_existing_evidence_20261107.py` retains the four **raw** results for historical accuracy but explicitly adds `raw_candidate_count_is_not_source_policy_admission=true`, `source_policy_eligible_research_rows=null`, `source_policy_rejected_research_rows=null` and `source_policy_review_status=NOT_ASSESSED_BY_PPIR_AUDIT`. The script does **not copy or reimplement** another owner's source-admission rules; the above 2/2 result is a separate *actual original-policy* read-only check. A test includes a synthetic job-board result and proves the auditor cannot infer source eligibility, verified customer, revenue, licensing or output permission. Independent source admission remains a required evidence step.

This is a PPIR **accuracy repair**, not new customer data ingestion or a production API release. Confirmed status: customer usage API authenticated, source search/audit routes held, Predictive Cloud V4 shadow readiness reports `real_source_rights_verified=false`, `production_tenant_source_admitted=false`, `live_consumer_activated=false`; original product remains OBSERVE. No original live Search Fabric files, Predictive Fabric bridge, services, PostgreSQL objects, credentials or provider calls were modified.

## 8 November 2026 — official UK source into original Predictive Cloud V4.11 HELD reviewer

Founder authorised continuing existing Data Cloud -> Predictive Cloud source admission research, not a database migration, new data product, Redis activation or paid provider call.

**Real source retrieval:** Direct HTTPS GET of https://find-and-update.company-information.service.gov.uk/company/02745893 returned 200. Observed company: ICH SERVICES LTD, 02745893, Active, incorporated 9 September 1992, registered address Union Bridge Works/Roker Lane/Pudsey, SIC 43210/43220/81100. Government HTML source response SHA256 19272fb537c8fddfd389fd9d760b3e52f2164258401693f1aa05f700e5ca2053. Bounded public, non-personal company-field SHA256 31787934624aac98439d48603641951d910e6df96880de9dafe4e35cb2614b5d. The same original cohort JSON now contains the source URL, response hash and size, observation timestamp, exact company facts and review-only gates. Raw HTML and any personal details were not stored.

**Source-rights distinction:** Companies House official published reuse guidance https://www.gov.uk/government/publications/companies-house-accreditation-to-information-fair-traders-scheme/public-task-copyright-and-crown-copyright permits public-register reuse subject to copyright, privacy and other applicable law. The only currently proposed purpose is PRIVATE_PREDICTIVE_RESEARCH_ONLY. Owner-attested rights custody, original signed CRM tenant binding, restricted EmpireDB source-rights reader, live predictive consumer and customer delivery remain FALSE. Texas TDLR dataset https://data.texas.gov/dataset/TDLR-All-Licenses/7358-krk7 explicitly lists its dataset licence as UNSPECIFIED and has no approved customer redistribution. Decodo's competing-product restrictions continue to apply to its system.

**Existing V4.11 source reviewer actually exercised:** The exact UK source-evidence digest was supplied to original empire_os.predictive_revenue_v411_source_gate.review_revenue_source_candidate_held with a SYNTHETIC fixture CRM login and fixture HELD rights-reader row. Original gate returned CANDIDATE_REVIEW_HELD and revenue_opportunity_admitted=FALSE; the separate source receipt also has production_source_admitted=FALSE. A deliberately mismatched synthetic tenant returned SOURCE_RIGHTS_READER_UNAVAILABLE_HELD. Neither can generate commercial predictions, publish Redis source events, or grant customer permissions. Synthetic proof is not real production admission.

**Acceptance tests:** 74 existing Data Cloud and updated source-record tests PASS; 35 tests for untouched original V4.11, Data Fabric and Predictive Fabric PASS. No production services, PostgreSQL objects, actual CRM tokens, provider requests, payments, source-rights grants, customer API routes or migrations changed.

**Remaining existing owner gate:** Independently attest actual source licence obligations and revocation policy, bind the public-register evidence to the real signed CRM tenant via the original rights-reader owner, review any migration 066 activation as a separately authorised bounded release, and verify one real permitted source-to-internal-decision canary. Until then mark production tenant admission, source publishing, customer forecasts and external delivery HELD. No duplicate module or independent source database should be created.
