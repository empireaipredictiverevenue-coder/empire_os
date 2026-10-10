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