# Empire AI Analytics → canonical CRM → Finance: original-owner integration
27 October 2026 | Scope: Empire AI first-party acquisition, not any separate operating company.

## Completed, built and unit-tested
This extends EXISTING `empire_os/analytics` and EmpireDB Analytics054/055. No duplicate tracking platform, payment database or runtime agent.

1. **Acquisition source v2 candidate:** `empire_os/analytics/acquisition_source_v2_candidate.py` validates eleven fixed categories: six existing v1 sources plus `paid_search`, `paid_social`, `affiliate_partner`, `publisher_referral`, `organic_video`. New paid channels require server-authenticated **signed campaign binding**; affiliate/publisher referrals require a **signed partner binding**; organic video is server-verified referral. Raw UTM/query/click IDs, browser consent or guessed source names are not sufficient. The code is explicitly REVIEW_ONLY.
2. **Staged EmpireDB migration:** `migrations/empiredb/075_first_party_analytics_source_taxonomy_v2_held.sql`. Requires canonical isolated EmpireDB/fixture database, original safe migrator, forced RLS, existing legacy constraints and installed 055 erasure function/table. Atomic transaction adds/validates replacement CHECK constraints before removing the old constraints. No runtime writer, tag, login, collector, RLS grant, schedule or service is installed. **NOT RUN ON PRODUCTION**. The exact original PostgreSQL-generated cross-column constraint is `empire_analytics_sessions_check`, not the initially assumed column-derived name; isolated PostgreSQL 18 QA caught and corrected that safely.
3. **CRM/Finance owner evidence join contract:** `empire_os/analytics/canonical_commercial_lineage.py` accepts ONLY a bounded original-source cohort described consistently by three distinct typed readers: Analytics consented sessions and CTA stage presence; canonical CRM accepted/source-linked order counts; and original Finance settled-order and independently reconciled actual cash/cost proof. Exact tenant UUID, `empire-ai.co.uk` property, acquisition channel, cohort ID and date window must match. Contradictory stages, cross-property/tenant/source records, unsupported currency, credentials, raw personally identifying fields and wrong provenance labels reject the review. It does not query customer tables, edit records, or issue payments.
4. **Independent verification remains separate:** even all three syntactically valid reports, with `authenticated_original_owner_assertion=true`, are **claims from provided inputs**, not cryptographically authenticated records. This reviewer correctly returns `ALL_ORIGINAL_OWNER_ASSERTIONS_PRESENT_NOT_INDEPENDENTLY_AUTHENTICATED` and always reports actual revenue, margin and Predictive Revenue training eligibility as UNKNOWN/false. Only separately authenticated original readers may promote evidence in their owning systems; no simulated channel cohort is fed into economic memory.

## Genuine collection/readiness status — confirmed in this session
- Original Analytics054 and Analytics055 are HELD by design; the read-only live catalog probe requires the dedicated local OS `postgres` peer and from the unprivileged session returned `HELD_EXACT_LOCAL_POSTGRES_PEER_REQUIRED`. **Production objects' current presence remains UNKNOWN**, not absent.
- The original Tag Intelligence read confirms the static homepage is observed, while lawful analytics consent, firing/delivery, real website sessions, collector activation, CRM attribution and realised revenue are **NOT verified**.
- The original `OfflineSessionAuthority` and `first_party_event_contract` are protected simulations. The `dormant_event_ingress` is local-test-only and MUST NOT be mounted publicly.
- Real customer collection/CRM/Finance matching has **NOT been activated or proved**. No unapproved production change is implied by a successful PostgreSQL fixture test.
- Existing canonical CRM `empire_os/conversion_data_repository.py` has accepted orders and payment-evidence readers, but it does **not** provide independent source-bound visitor cohort proof. Original Predictive Revenue V4.15/BSC candidate and V4.17 order cohort readers are intentionally HELD on financial finality; do not replace them with a browser event or a Finance true/false flag.

## Exact remaining original-owner integration sequence
1. **Privacy/Website:** approve the collection purpose, consent or lawful alternative where applicable, retention and deletion schedule, processor details, and how UTM / publisher source metadata is authenticated. Preserve first-party control and do not install new analytics cookies/scripts or public endpoints before release.
2. **EmpireDB/Analytics:** original DBA runs the restricted 054/055 live catalog inspection under its existing OS peer, verifies table owner, RLS, erasure roles and current state, and authorises any necessary 054/055 deployment. Only after that, review 075 separately for paid/affiliate categories; stage fixture tests are NOT production approval. A dedicated authenticated tenant-bound ingest role, admission capability, replay/rate limits, privacy checks and revocation/erasure tests require their own controlled migration and approval.
3. **Website gateway:** deploy an owner-reviewed server-issued pseudonymous session/consent path with hard-denied pre-consent events, signed source binding, allowlisted event categories, published privacy notices, short TTL, strict event replay rules, and no raw contact, IP, query string, user-agent or cookie in the research feed. The existing unmounted HTTP test router cannot simply be flipped live.
4. **CRM:** the original signed first-party CRM membership and conversion owner must bind accepted order/opportunity references to independently consented source cohort receipts, without exposing visitor/session identifiers to commercial research and without interpreting CTA attempts as accepted leads.
5. **Finance/CRU:** the canonical payments/settlements owner must reconcile verified settlement, refunds/chargebacks and real acquisition costs in the **same tenant, source and window**, in one currency, via dedicated source-controlled readers. An on-chain candidate, vendor bid, order marked paid or unverified owner assertion is insufficient.
6. **Predictive Revenue:** only independently authenticated, privacy-authorised source–order–settlement cohorts can enter the existing calibration and economic memory programme. Simulated stage presence is never training data.

## Test evidence
- `tests/analytics/test_source_taxonomy_and_canonical_lineage_20261027.py` exercises eleven classified sources, owner provenance contracts, rejection of PII, cross-tenant/source/window collisions, mismatched conversion counts, currency and financial truth. All examples and amounts are synthetic.
- `tests/analytics/test_analytics_source_v2_pg18_20261027.py` uses the **existing isolated disposable PostgreSQL 18 fixture** with Analytics054/055, and tests migration application, legacy preservation, mismatched partner source rejection, RLS/role integrity and fail-closed second application. Production EmpireDB is never connected.
- Existing first-party offline consent/session, revocation and channel-stage regressions remain green.

**Execution status:** source-contract and staged SQL **built/tested only**; production collector/schema deployment, real source-to-CRM join and final settled revenue **NOT VERIFIED OR ACTIVATED**. This is a bounded owner handoff, not another framework or a second database.


## Production EmpireDB ground truth — founder-run read-only catalog, 27 Oct 2026
The founder executed the EXISTING `scripts.review_analytics_live_catalog_20261019 --read-only` as the local `postgres` OS peer against canonical EmpireDB. The report established:
- `database_catalog_observed=true`, `canonical_empiredb=true`, `table_count_catalog=0`;
- `status=ANALYTICS054_055_NOT_DEPLOYED_IN_OBSERVED_CATALOG`;
- `analytics054_production_deployed_verified=false`, `analytics055_production_deployed_verified=false`;
- `maintenance_role_not_activated_verified=true`, `no_public_erasure_execute_verified=true`;
- `customer_records_read=false`, `database_writes=false`, `website_analytics_consent_verified=false`, `live_visitor_sessions_verified=false`.

The ORIGINAL source-only preflights were independently rerun (nonprivileged, no DB connection) and verified the existing pinned Analytics054/055 SHA256 hashes. The original tag monitor observes static homepage markup, but not live consent, tag firing, sessions or revenue. Analytics075 remains HELD and tested only in isolated PostgreSQL 18. This creates an accurate **zero-table production baseline**; prior UNKNOWN inventory in this document is superseded by the founder-run result.

### Exact approved-owner deployment decision still outstanding
1. The original DBA must independently attest `empiredb_migrator` NOLOGIN/non-superuser/no-BYPASSRLS against **current** `pg_catalog`, plus safety of schema ownership, backups/recovery, operational lock window and original SQL pin. The general zero-table catalog report does NOT itself positively attest the migrator role.
2. The founder and original Privacy/Retention owners must expressly approve a **schema-only** installation scope for Analytics054 and Analytics055, with no public analytics collection, browser scripts/cookies, maintenance LOGIN, writer role, app grants or live visitor storage. Retention/erasure authority and legal review for eventual actual collection are separate hard requirements. Neither this handoff nor the founder's read-only check authorises schema writes.
3. Original DBA, after approval, alone installs the EXACT checked-in 054 and 055 migrations in order through the existing controlled database release, with verified safe owner, collision preflight, backup and restoration procedure. Re-run the existing peer-only `review_analytics_live_catalog_20261019 --read-only` after each migration and verify the expected schema state and forced-RLS/owner protections. STOP on any deviation; do not apply 075 automatically.
4. Only AFTER 054/055 and separate owner review may the original DBA consider Analytics075 paid/affiliate taxonomy. The isolated fixture passing does not authorise production. Subsequent dedicated consent-authority/writer, publisher-signed source bindings, lawful retention, public website activation, canonical CRM order join, independently reconciled Finance cash and Predictive Revenue calibration each remain individually withheld pending real evidence.

**Current installation decision: `SCHEMA_NOT_INSTALLED_FOUNDER_DBA_APPROVAL_REQUIRED`.**
**Current ingestion decision: `REAL_COLLECTION_OFF_AND_CONSENT_UNVERIFIED`.**
**Live cash attribution: `NOT_VERIFIED`.**

An attempted follow-up privileged role-only catalog query from the remote execution tool was blocked by that tool's command restriction. No privileged query or migration was executed by the assistant, and that restriction was not bypassed. Original founder-run catalog status above remains authoritative.

## Founder approval and guarded schema-only release command — 27 Oct 2026

The founder explicitly approved installing ONLY empty locked-down Analytics054 and Analytics055 tables and erasure definitions, with ZERO visitor collection, runtime grants, new services, website changes, Analytics075 application or commercial activation.

**Release driver prepared:** `scripts/deploy_empiredb_analytics054055_schema_only_20261027.sh`. This uses exactly the pinned and committed 054/055 source hashes, verifies current EmpireDB is the original PG18 primary, no Analytics collisions, the NOLOGIN migrator safety state, a recent existing encrypted pgBackRest backup with fixed AES-256 config, exclusive lock and purpose-restricted preflight. It copies approved SQL privately for executing as the local PostgreSQL peer. It then requires exact read-back of THREE force-RLS tables after 054, and FOUR force-RLS/owner-protected, EMPTY tables after 055. It does not create a writer or call any service/website API.

**Privileged remote execution constraint:** The Remote Desktop Commander command channel declined the operator's root `--preflight` invocation (`Command not allowed`). No alternate shell/privilege workaround was attempted, and **no production migration has yet been run**. Founder can execute the reviewed root command below directly in the authorised Ubuntu terminal:

```bash
cd /srv/empire_os && \
sudo bash scripts/deploy_empiredb_analytics054055_schema_only_20261027.sh --preflight && \
sudo bash scripts/deploy_empiredb_analytics054055_schema_only_20261027.sh --apply --schema-only-founder-approved-20261027
```

The preflight is a separate no-write pass and exits nonzero on any mismatch; `&&` prevents installation if it fails. The application checks preflight again and stops on mismatch. **Do not retry** a partial migration failure automatically: 054 commits before 055, and a 055 failure leaves 054 installed for exact DBA review. Files containing private DDL execution stdout/stderr are root-only under `/var/backups/empiredb/analytics054055-schema-release-20261027`; the existing encrypted pgBackRest repository is not replaced.

On successful application the final output must include `ANALYTICS054055_STATUS=SCHEMA_ONLY_INSTALLATION_VERIFIED` and internal catalog read-back. The independent original peer-only verifier may then be re-run:

```bash
cd /srv/empire_os
sudo -u postgres env PYTHONPATH=/srv/empire_os /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_analytics_live_catalog_20261019 --read-only
```

Expected `status=ANALYTICS054_055_CATALOG_OBJECTS_OBSERVED_RELEASE_HELD`, `table_count_catalog=4`, two deployment booleans true, no public erasure execute, no maintenance login and **no real visitor/consent evidence**. That represents infrastructure presence, NOT legal/privacy/marketing authority.

The shell runner and preflight tests passed locally; original migration fixture tests passed. Current truth remains `SCHEMA_NOT_INSTALLED_IN_LATEST_AUTHORITATIVE_CATALOG` until the user's operator result proves otherwise.

## AUTHORITATIVE PRODUCTION RELEASE COMPLETION — 27 Oct 2026, 19:17 UTC
**This update supersedes all earlier "054/055 not installed" or "current catalog UNKNOWN" statements above.**

The founder executed, in the authorised EmpireOS terminal:
`sudo bash scripts/deploy_empiredb_analytics054055_schema_only_20261027.sh --preflight && sudo bash scripts/deploy_empiredb_analytics054055_schema_only_20261027.sh --apply --schema-only-founder-approved-20261027`.

The user-provided actual production terminal result reported:
- `ANALYTICS054055_PREFLIGHT=PASS_PINNED_SQL_ROLE_PRIMARY_ZERO_TABLES_BACKUP` on both dry-run and apply;
- `ANALYTICS054_POSTCOMMIT=THREE_LOCKED_TABLES_VERIFIED`;
- `ANALYTICS054055_POSTCOMMIT=FOUR_EMPTY_FORCED_RLS_TABLES_VERIFIED`;
- `ANALYTICS054055_WRITER=NOT_PROVISIONED`;
- `ANALYTICS054055_COLLECTION=OFF`;
- `ANALYTICS075=NOT_APPLIED`;
- `ANALYTICS054055_STATUS=SCHEMA_ONLY_INSTALLATION_VERIFIED`.

The original root-owned release receipt is at `/var/backups/empiredb/analytics054055-schema-release-20261027/20261027T191704Z`. It was not accessed or altered by this workstream. The verified state is **PRODUCTION_ANALYTICS054055_SCHEMA_ONLY_INSTALLED**, four empty protected tables, no consent ledger records or visitor data. No application login was provisioned, no website tag or collector was enabled, and no paid/affiliate taxonomy migration was applied.

**What remains held:** Independently approved retention/legal basis and policy version; original website/CMP consent decision authority; dedicated tenant-scoped server writer with signed source classification and erasure execution role; separate reviewed Analytics075 release; canonical CRM linkage to accepted opportunities/orders; Finance-authenticated final settlement and costs; downstream Predictive Revenue calibration. Neither a successful schema deployment nor locally passing tests authorises live collection, materialised conversions, recognised revenue or automatic spend.

The existing peer-only catalog script is available for an *independent* post-release readback but the guarded installer has already checked the original catalog after each migration. Do not rerun this once-only, fail-on-collision installer. No change to other company lanes.
