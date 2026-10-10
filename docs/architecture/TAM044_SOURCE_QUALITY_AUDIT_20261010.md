# TAM 044 source-quality audit — six-market evidence gates

Date: 10 October 2026. Status: prepared, tests pass on disposable PostgreSQL. Production counts not yet observed.

The canonical TAM044 result contains eight US roofing records; the other five approved market cells returned zero sampled observations, not proof of zero businesses.

The installed scoped TAM SQL requires six evidence gates: exact canonical sector label (roofing, solar or insurance); nonempty canonical business name; active entity/prospect link; a matching acquisition record; explicit GB/US locale.country_code; and a nonempty original acquisition source URL.

scripts/tam044_source_quality_audit_readonly.sql is a bounded, aggregate-only diagnostic. It starts a REPEATABLE READ READ ONLY database transaction, validates the canonical EmpireDB primary and migration 044, sets a 25-second statement timeout, emits six anonymized cell aggregates, then ROLLBACK. It does not return company names, UUIDs, emails, contacts or source URLs. No DB or runtime writes.

IMPORTANT: The inspected cohort is the first up to 20,000 canonical entities by ID whose existing niche contains roof, solar or insur. This is not an exhaustive census. A company with an unrelated/blank niche may be invisible. Possible aliases remain unverified and are not automatically converted into the allowed three sectors. Industry-wide counts repeated for GB and US are NOT country-located counts. Gate counts can overlap and must not be added together.

An authorized DBA can run this ONE read-only command directly over SSH:

    cd /srv/empire_os && sudo -n -u postgres psql -X -w -At -v ON_ERROR_STOP=1 -d empiredb -f scripts/tam044_source_quality_audit_readonly.sql

Success returns an aggregate JSON document with schema_version=empire.tam-source-quality-audit.v1 and scope_count=6, then ROLLBACK. Failure/timeout is not evidence of zero businesses. Remote Commander does not permit the privileged DBA action.

Interpretation: exact niche with inactive links -> review identity graph and qualified link promotion; active links with no acquisitions -> recover real acquisition evidence; missing locale -> recover explicitly supported country without guessing; missing source URL -> retrieve real provenance; possible niche aliases -> manual label verification, no heuristic promotion. If no matching canonical candidate exists, use existing Solar Opportunity Map, lead-intelligence/Overpass, roofing and insurance discovery lanes for independent source enrichment with separate authorization for any production write.

No automatic CRM mutation, tenant authority, outbound, payment, scheduler, market total or buyer-intent claim has been authorized.
