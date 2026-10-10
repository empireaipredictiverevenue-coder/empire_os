# Solar existing-entity acquisition — identity-readiness recovery

Date: 10 October 2026. Production READ ONLY audit not executed.

## What live source matching actually proved

Previous authorised RECC source-acquisition preview: 120 observations (three distinct RECC pages), 93 with an extracted business website, 119 with a business phone, and no name/website/phone corroborated overlap with the 83 canonical solar companies. The canonical target query yielded 869 active prospect links across those 83 companies; 71 companies had website evidence but none had a canonical company phone field.

Zero overlap is NOT evidence of zero solar companies or false source data. RECC covers only some UK installers, and the 83 canonical entities are NOT proven to be UK. The entity-link fanout (869/83) must be examined before any immutable acquisition ledger insert.

## Fix to the existing source connector

Read-only canonical target SQL now fetches linked prospect.phone as well as business_entities.canonical_phone, prospect.website and canonical business website. Source corroboration uses the supported GB/US phone normaliser on both fields, but multiple prospects or conflicting identities remain manual/ambiguous. A linked phone can reveal a name-variant review; it NEVER grants automatic acquisition attachment, outbound, or country provenance. Aggregate stdout separately reports canonical-phone evidence and linked-prospect-phone evidence. No database write or external source request was performed as part of this code change.

## Read-only identity graph audit

scripts/tam_solar_identity_graph_audit_readonly.sql is a separate data quality diagnostic on the first at most 250 exact solar canonical entities that have active links and no acquisition ledger history on any active link. It uses a 20 second timeout, repeatable read, transaction READ ONLY, and ROLLBACK. Its scalar JSON response is aggregate-only; no names, UUIDs, URLs, phone numbers or contacts leave the database.

Fields include: true distinct entities vs prospect links; link-count distributions (1, 2-5, 6-20, over 20), maximum links per entity; multiple linked prospect website hosts; no website evidence; linked prospect phones; linked prospect name/niche disagreement; per-entity website host contradictions; diagnostics for identity confidence and stored resolution state; explicit country=GB in existing entity provenance.

Interpretation: Multiple unrelated hosts or inconsistent prospect identities need **link-quality review**, not more blind matching or auto-merging. The absence of GB provenance means a UK source observation is not sufficient to declare a specific entity UK. Stored 'resolved' identity state is not independent proof.

## One authorised audit command

    cd /srv/empire_os && sudo -n -u postgres psql -X -w -At -v ON_ERROR_STOP=1 -d empiredb -f scripts/tam_solar_identity_graph_audit_readonly.sql

Remote Commander cannot issue privileged DBA commands. Running it directly from an authorised terminal is safe as a bounded read-only transaction. Only the resulting aggregate JSON is needed.

## Revenue relevance and next decision

If most identities are unique and have verified website hosts, plug into EmpireOS's existing first-party website Search Fabric site_probe for targeted source verification (one bounded observation per unambiguous company). If many identities have multiple unrelated domains or inconsistent prospects, repair evidence associations first under a separately approved identity workflow. Do not make 869 acquisition records out of 83 companies. An acquisition ledger append still requires verified real source URL, exact existing prospect binding, country evidence, deduplication/idempotency and separately approved authority.

Current retained TAM result: 8 US roofing observations; UK solar still zero verified TAM acquisition observations. No additional records inserted, no sends, no payments or timers.