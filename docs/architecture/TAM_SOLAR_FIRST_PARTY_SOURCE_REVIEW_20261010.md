# EmpireOS: bounded first-party solar source review

Date: 10 October 2026. STATUS: Engineering prepared; no production five-site observation yet.

## Live evidence driving this change

The exact-sector solar audit returned 83 canonical entities and 869 linked prospects. All 83 entities lacked a verified resolution state and explicit GB provenance. No company-level canonical website was set. Seventy-one entities had website evidence on linked prospects, and 18 had linked-prospect phone evidence. A 120-entry UK RECC member sample produced zero matches. Zero matched RECC sources does not mean zero real UK solar businesses.

## Integrated first-party mode

Files: empire_os/tam_source_acquisition_connector.py, scripts/run_tam_source_acquisition_connector.py and tests/test_tam_first_party_source_review.py. Reuses existing Search Fabric site_probe; no new service or timer.

Root-authorised caller queries canonical EmpireDB READ ONLY (max 250 solar entities with active links and no source acquisition). It groups linked prospects by entity and rejects contradictory entity/prospect names, multiple website hosts within an entity, a host shared across entities, non-business social hosts, local/private IPs, and malformed source URLs. It picks at most FIVE distinct business hosts for review. A single site is not permission to attach evidence to any one of many prospects.

Each chosen public website is inspected using existing site_probe with public_only=True, max_pages=2, request_timeout=4 seconds and total time_budget_seconds=10. A successful result must show HTTPS at the exact expected host and an actual same-host page receipt. Public business name/address claims are preserved privately for founder evidence review; contacts/emails and customer data are not sent to stdout. Name agreement is NOT proof of country, independent entity authority, payment or buyer intent.

Only a private 0600 review file stores entity/source details. The public receipt emits aggregate attempted/success/name-aligned counts, and explicitly says country_verified=false, database_write=false, acquisitions_appended=0, outbound_sent=false, execution_authority=none.

## Bounded operator example (not yet executed)

cd /srv/empire_os && sudo -n bash scripts/run_tam_source_acquisition_connector.sh --observe --source first_party_site --sector solar --country GB --max-targets 250 --max-source 5

GB is research focus, not proof of domicile. This mode refuses RECC pagination, location override, non-GB solar or >5 sites. It does not write to prospect_acquisitions or alter entity resolution states. A subsequent separately approved ledger attachment must bind original source evidence to exactly one verified canonical entity and prospect with independent country verification and idempotency.

Current TAM research remains eight US roofing observations, zero verified UK solar acquisitions; market GPS and TAM research scheduling remain unchanged.
## 10 October 2026 — live first-party selection failure and correction

Founder-run live first-party mode considered 83 entities and rejected all 83 **before any public website request**. This is not a negative company identity result; it is an eligibility-selection result. Its private receipt remains at /var/lib/empire/source-acquisition-review/20261010T193847Z-353c78d7b9c8.json. No individual company data need be disclosed.

The selection criteria previously required stored candidate URLs to point to the domain root, excluding valid business website evidence stored as a /contact or /about path. This has been relaxed to evaluate the *host* as an unverified candidate, while the actual site probe still starts only from the HTTPS root and requires same-host public retrieval. Existing checks for unsafe hosts, shared cross-entity domain identity, conflicting entity/prospect names, and no database writes remain in force.

The connector now reports aggregate eligibility_diagnostic statistics:
- rejection_reasons by number of entities, including NO_UNAMBIGUOUS_BUSINESS_WEBSITE, CONFLICTING_BUSINESS_WEBSITE_HOSTS, CONFLICTING_CANONICAL_OR_PROSPECT_NAMES and BUSINESS_HOST_SHARED_ACROSS_ENTITIES
- entity candidates prior to cross-entity shared-domain filtering and the count affected by shared hosts
- candidate website values checked, valid/unusable values and deep-path values

A new --diagnose-only mode uses only the same bounded READ ONLY canonical database query, **makes no website network requests**, produces no acquisition records, and prints only aggregate rejection counts. It does not weaken the identity-resolution or country verification gates.

**One deterministic aggregate-only diagnostic command** (root via an authorised shell; do not repeatedly run RECC or first-party probes in advance):

    cd /srv/empire_os && sudo -n bash scripts/run_tam_source_acquisition_connector.sh --observe --source first_party_site --sector solar --country GB --max-targets 250 --max-source 5 --diagnose-only

Use the resulting rejection distribution to decide whether the true blocker is global host reuse, unusable original website values, or conflicting identity names. Source/domain evidence may still be shared across metros and must not be attributed to one of 869 prospects without independent entity verification. All UK/TAM acquisition ledger writes remain held.
