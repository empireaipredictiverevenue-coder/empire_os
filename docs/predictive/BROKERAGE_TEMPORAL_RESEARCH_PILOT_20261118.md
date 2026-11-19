# Empire AI — Predictive Cloud DESNZ temporal research pilot
Date: 18 November 2026 | Original EmpireOS Data Brokerage owner and Predictive Fabric | INTERNAL RESEARCH ONLY

## Verified source history and correction

Four distinct official publisher editions, checked against original archived bytes, schema, row counts, publisher publication dates, revision date boundaries, and SHA-256:

| DESNZ period | Published | Publisher records | SHA-256 | Archive capture |
| --- | --- | ---: | --- | --- |
| January 2026 / Q4 2025 | 2026-02-09 | 13,995 | fdb6aec50647a4de88f63d33679b93cb2147417eddc43f3f31cbf12792a38aae | UK National Archives 2026-04-10 |
| April 2026 / Q1 2026 | 2026-05-06 | 14,316 | 3aa6752bfdc6b5275f8be0585ad8bd00a8646bd522d686cfb57d95cc9d8688a3 | UK National Archives 2026-06-04 |
| July 2026 / Q2 2026 | 2026-08-03 | 14,657 | 84c1b5f958a934d8b4b86ec88f50bdcf43830ded7ff2efc27bffca0c98695035 | UK National Archives 2026-10-08 |
| October 2026 / Q3 2026 | 2026-11-13 | 14,967 | ec3b08d7986faff59b2a29adca75521583094198faa4f72244d16e09e936f440 | Original Data Brokerage verified Cloud intake |

The current GOV.UK URL for the old July CSV redirected to the October CSV, and the current April URL also redirects to October. Both old links MUST NOT be used to infer historical states. The earlier mislabeled July file is quarantined. Original April data was obtained from a National Archives asset captured on 4 June 2026, not from the later redirect. All archived rows were checked for duplicates, schema and impossible future record-updated timestamps. Publisher record-last-updated is not an independently verified stage-transition time. The July edition has 175 missing/invalid record-last-updated metadata values, but no valid updated dates after the edition date.

## Publication-to-publication outcomes: real publisher labels, not customers

| Publisher window | Days | Matched project references | Stage changes | Share |
| --- | ---: | ---: | ---: | ---: |
| Feb 9 → May 6, 2026 | 86 | 13,982 | 417 | 2.9824% |
| May 6 → Aug 3, 2026 | 89 | 14,310 | 476 | 3.3263% |
| Aug 3 → Nov 13, 2026 | 102 | 14,648 | 373 | 2.5464% |

Across three windows there are 42,940 labelled project-edition observations with 1,266 observed publisher stage changes. Projects missing from a subsequent edition are excluded rather than labelled as unchanged, and previously unseen project IDs never receive an as-of feature retroactively. Training labels available only at the following publisher release cannot leak into prior as-of features.

The stage+technology scorer is a fixed smoothed frequency baseline (stage prior weight 50, stage-technology prior weight 100) evaluated entirely in research memory. It uses the first window to score the second, then both earlier windows to score the last. Model fitting excludes later-window labels, with no customer data, live weights, tenant records or production inference. **However, the analyst examined aggregate stage-change counts before designing this scorer: the retrospective evaluation is time-ordered but was NOT blind or prospectively pre-registered.** Model selection bias therefore remains possible; all accuracy and lift metrics are exploratory, not independently validated forecasts.

### Chronological historical evaluation (not prospective forecasts)

| Research fold | Train labels | Held-out labels | Held-out stage changes | ROC AUC | Brier score, scorer | Training-only prevalence Brier | Top 500 changes identified |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Train Feb–May → evaluate May–Aug | 13,982 | 14,310 | 476 | 0.925335 | 0.026257 | 0.032168 | 150 |
| Train Feb–Aug → evaluate Aug–Nov | 28,292 | 14,648 | 373 | 0.908750 | 0.021313 | 0.024853 | 123 |

Latest historical holdout: top-500 precision 24.60%, recall 32.98%, approximately 9.66× the holdout's 2.55% unranked prevalence. Brier skill against the training-prevalence constant is 14.25% in the latest holdout. These values measure **changes in the government's published planning-stage classification only**, not demand, actual construction, revenue, completed deals or prospective customer forecasts. A no-change classifier would appear 97.45% accurate but detect ZERO of the 373 observed stage changes; its balanced accuracy is 0.50. Accuracy without event recall is misleading.

**Scientific limits:** one final heldout quarter, two earlier retrospective windows of unequal length (86/89 vs 102 days), potential publisher corrections, missing labels for removed IDs, current input provenance and source licensing review, grouping by prior stage with strong class-imbalance effects. This does not independently replicate or establish a calibrated model. Research scores must remain internal; model qualification remains HOLD_INSUFFICIENT_INDEPENDENT_ROLLING_EVALUATIONS_FOR_PRODUCTION. More historical holdout quarters, frozen prospective scores and genuinely independently verified outcomes are required for a product-level predictive claim.

## Private evidence and original ownership

Existing original chain, preserved: Data Brokerage source/mining owner → verified Predictive Cloud intake → existing Predictive Fabric internal research adapter → temporal research pilot and pure in-memory chronological evaluator. No competing scheduler, new system, model deployment, database migration, extra GPU, paid network source or public endpoint.

Private paths:
- Current research report: runtime/predictive_cloud/brokerage_research_private/forecast_pilot/research_pilot_latest.json
- Immutable hashed-project-ID label ledger: location and SHA recorded in private_temporal_label_ledger in that report
- Three pinned historic editions: runtime/predictive_cloud/brokerage_research_private/forecast_pilot/source_archives/
- Source recovery evidence and rollback: runtime/data_brokerage/enterprise_feed_release_20261118/temporal_q1_upgrade_20261118/
- Temporal pipeline: empire_os/predictive_cloud_temporal_research_pilot.py
- Research scoring and anti-leakage checks: empire_os/predictive_cloud_temporal_science_eval.py
- Continuous refresh owner: scripts/run_data_brokerage_source_mining.py (existing lock and timer, no restart)

Label rows contain a SHA-256-hashed public REPD project reference, prior published stage, prior technology, prior edition date, later published stage and next edition date. No operator names, street addresses, personal identifiers, buyer identities, customer or claimant records, procurement values, pricing or transactions are included. Protected directories 0700; private file objects 0600. Changing history creates content-addressed new versions; identical history creates no duplicate object.

FEMA storm activity remains strictly descriptive: latest 1,000 selected declaration/county rows, not complete historical sample; 140 distinct declaration IDs, sample median incident-to-declaration lag 2.5 days, sample p90 111 days. No valid future storm-count backtest, claims inference or insurance purchase-propensity estimate.

## Prospective internal research cohort — frozen 18 November 2026, 18:59:43 UTC

The November DESNZ Q3 2026 publisher edition (published 13 November) now has a genuine **pre-next-edition research scoring freeze** created at 18:59:43 UTC on 18 November, not retroactively dated to publication. The original Data Brokerage/Predictive Fabric research owner used 42,940 prior project-window labels (1,266 publisher stage changes) to freeze research scores for all 14,967 current publisher projects and an explicitly predeclared top-500 ranking.

Private commit receipt: runtime/predictive_cloud/brokerage_research_private/forecast_pilot/prospective_freezes/repd_2026-11-13_freeze.json. Receipt SHA256 at creation: 460624fd3c161b65592133bb5fe2f794cd3bc9a6ea9b46f3cf37b410f9b323f6.

Immutable-by-application create-once scoring object SHA256: 44d30ca2aae298294f6f6b04c8d0a9b1cac20507be545716a5557ed79e6f864c (8,359,251 bytes). Frozen model-parameter object SHA256: 69f7cbfe1878ceb893e753e058e76bcdd8745d3be1a6ada5e884b9a4d388101a (26,303 bytes). Private mode 0600 files, 0700 directory. These are pseudonymised public project reference hashes, not guaranteed anonymised identifiers. The score vector contains only publisher-stage change research scores, known as-of stage/technology and explicit no-outcome/no-training flags, not actual sales, revenue or buyer intention.

The original scheduled Brokerage owner verifies the frozen byte hashes; it NEVER re-scores or overwrites the committed cohort. The genuine systemd owner invocation at 19:06:38 UTC independently recorded a verified 14,967-project freeze, score SHA256 44d30ca2aae298294f6f6b04c8d0a9b1cac20507be545716a5557ed79e6f864c, original frozen-at timestamp and zero customer forecast permissions. This is not third-party cryptographic timestamping or storage-level write-once media. Preserve the creation timestamp and score digest for independent future review.

Next validation: when DESNZ genuinely publishes the next quarterly edition, preserve its original publication binary and source/version proof, join on hashed public project IDs, exclude vanished IDs as unknown, and compute the already fixed top-500 event recall, precision, AUROC, precision-recall and calibration checks. Do not change the historical cohort, sorting or scoring parameters before observing that outcome. The next publisher edition date is not yet verified, and no model/customer/revenue forecasting approval is implied.
## Continuous next-edition outcome evaluation — guarded

The original Data Brokerage seven-day DESNZ feed refresh now owns the prospective evaluation trigger, under the existing department heartbeat and lock. Module: `empire_os/predictive_cloud_prospective_outcome_eval.py`. No new timer or parallel publisher watcher exists. The current official data remains the November 2026 Q3 edition, so the live evaluator explicitly returns `AWAITING_NEW_OFFICIAL_REPD_RELEASE` with zero evidence writes and zero scored future outcomes.

An evaluation is eligible only when the original publisher source receipt and private Cloud intake both verify a *different* normalised source SHA, an official `assets.publishing.service.gov.uk` CSV link with exact Q4 2026 filename, an authenticated existing source-owner freshness/status receipt checked in 2027 or later, no future-dated row updates, 10,000–20,000 distinct source records, and >=97% matched frozen projects including >=98% coverage of the original fixed top 500. Q3 revisions or changed URLs do not count as future labels. The Q4 file's publisher publication day is not claimed without separate metadata; the receipt's SHA applies to EmpireOS's **normalised CSV**, not an independently archived raw publisher binary.

The original frozen ranking, 14,967-project cohort, top-500 selection and model parameters remain immutable-by-application. Missing next-edition IDs remain **unknown**, and the system never substitutes ranks 501 onward for missing top-500 projects. A successful later outcome check produces separate SHA-addressed private evaluation evidence and an original-owner commit marker, with no production prediction admission. The score comparison will report fixed-top-500 precision and recall, event prevalence, tie-aware ROC AUC and average precision, Brier score against the **frozen training-only prevalence** constant, log loss, missing-label coverage and score-band reliability. All results will remain research-only pending source/licence verification, an independent model-science review and Founder approval for any product use.
## Raw DESNZ provenance and encoding repair — 18 November 2026

The original Q3 2026 DESNZ publisher CSV is preserved privately, with raw-byte SHA256 `48e76c49f33a1090e78108d1ea9bfe689b35963ea3be1bb4f6516d038a5ff862` and 5,219,160 original bytes. It contains **14,968 physical records but 14,967 unique Ref IDs**, because the two records for public reference 7679 are identical. Original source bytes, normalised dataset SHA and exact duplicate counts are separately recorded in `runtime/predictive_cloud/brokerage_research_private/forecast_pilot/source_archives/2026-11-13_REPD_Q3_2026_raw_provenance_receipt.json`.

The earlier Q3 normalised source SHA256 `ec3b08d7986faff59b2a29adca75521583094198faa4f72244d16e09e936f440` was produced by UTF-8 replacement decoding of a Windows-1252 publisher file, altering 88 text-field values (49 site names, 39 planning reference strings). The original Research Fabric frozen cohort remains pinned to that verified as-of snapshot, not rewritten or quietly re-scored. The existing enterprise feed parser has now been corrected to strict UTF-8 or fallback CP1252, retains exact duplicate rows only when identical, rejects conflicting project-ID duplicates and redirected or unexpected government asset URLs, and archives publisher raw bytes with content-addressed SHA metadata for subsequent official refreshes. The immediate manual reader QA verified 14,967 distinct projects, correct original apostrophes, one identical duplicate, secure 0600 raw archive and no source-owner state mutation.

On the next scheduled Q3 refresh, a resulting corrected **normalised** SHA is a known text-decoding repair, **not** a newer Q4 edition. The gated prospective evaluator explicitly remains waiting for a genuine new official Q4 publisher file. Before any future evaluation is admitted, the original raw Q4 CSV is hash-checked and fully rebuilt into the same normalised fields and digest as the existing Cloud source; publisher filename alone is insufficient. A failing raw archive, conflicting duplicate or mismatched checksum holds the evaluation without retroactively changing the November freeze.

## Official REPD rights evidence — 18 November 2026

The government's public data catalogue lists the Renewable Energy Planning Database (REPD) under the **UK Open Government Licence (OGL)**: https://www.data.gov.uk/dataset/a5b0ed13-c960-49ce-b1f6-3a6bbe0db1b7/repd (viewed 18 November 2026). The official DESNZ publication identifies Barbour ABI as its data manager and identifies the 13 November 2026 October dataset as the current official edition: https://www.gov.uk/government/publications/renewable-energy-planning-database-quarterly-extract. OGL v3.0 generally permits commercial reuse with acknowledgement: https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/.

**Rights are not blanket-cleared for every column or product.** OGL excludes personal data and any third-party intellectual-property rights the publisher is not authorised to license. The archive guidance explicitly says sources must be attributed and third-party/personal-data rights separately reviewed: https://www.nationalarchives.gov.uk/information-management/re-using-public-sector-information/uk-government-licensing-framework/open-government-licence/exceptions-to-ogl/. The source contains company/operator and location fields, so a commercial data-pack export still requires field-level rights/privacy review, the documented source attribution, customer access/tenancy checks and Founder release approval. The internal stage-and-technology research scores do not include operator/contact or customer identifiers. The repository's existing `customer_delivery_authorized=false` and `licence_release_approved=false` remain correct.

Suggested attribution for an independently reviewed permitted public-sector-information product, not yet authorised for deployment: “Contains public sector information from the Department for Energy Security and Net Zero (Renewable Energy Planning Database, October 2026) licensed under the Open Government Licence v3.0. Source: GOV.UK. Adapted and analysed by Empire AI; the source does not endorse Empire AI.” Verify the exact attribution and any excluded fields before customer sale.

## Admission and product gates

Zero production training samples admitted, zero production customer revenue forecasts, no outbound, no paid source calls, no tenant exposure, no automatic public delivery or sale. Existing pinned Forecast materializer remains unchanged and in observation mode. The founder's licence, tenant isolation, security, accuracy and publication gates remain in effect. Public products must NOT expose private JSONL, Cloud object paths, internal model scores or misleading confidence numbers.

Next independent evidence: retrieve further correctly dated historical releases (not redirects); then at least two additional independent rolling holdout quarters or a prospective frozen scoring run, followed by proper event-recall, PR/ROC, calibration and drift reporting. Actual commercial prediction requires independently verified enquiries, signed work and revenue outcomes; publisher stage alone cannot supply them.

Official primary sources:
- https://www.gov.uk/government/publications/renewable-energy-planning-database-quarterly-extract
- https://webarchive.nationalarchives.gov.uk/ukgwa/20260410041509id_/https://assets.publishing.service.gov.uk/media/6985c316d3f57710b50a9b1f/REPD_Publication_Q4_2025.csv
- https://webarchive.nationalarchives.gov.uk/ukgwa/20260604190919id_/https://assets.publishing.service.gov.uk/media/69fc56908cc72d2f863ea58d/REPD_publication_Q1_2026.csv
- https://webarchive.nationalarchives.gov.uk/ukgwa/20261008070634id_/https://assets.publishing.service.gov.uk/media/6a6cbdc00c36759b5ccaa305/REPD_Publication_Q2_2026.csv
- https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries
