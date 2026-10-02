# TAM Country Evidence Reader — Architecture Delta V1

## Purpose

Supply the TAM / Market Intelligence runtime with company-level country evidence
without inferring geography from metro text and without granting the
intelligence materializer direct access to canonical acquisition ledgers.

## Canonical placement

EmpireDB remains canonical. The reader joins:
- prospect_acquisitions: acquisition evidence and observed timestamp;
- prospect_entity_links: active prospect to canonical entity identity;
- business_entities: canonical company name and canonical niche.

Country comes only from the locale.country_code field inside canonical
prospect acquisition evidence.

## Interface

A bounded read-only function named get_tam_market_observations(integer) returns
JSON. Each returned row contains entity_id, company_name, industry,
country_code, source_ref, and observed_at.

Rows require an active identity link, non-empty canonical niche/name, a
two-letter country code, and non-empty source provenance. The latest evidence
for an entity/industry/country scope wins deterministically.

## Authority

The function is STABLE, SECURITY DEFINER, owned by non-login
empiredb_migrator, and has empty search_path. EXECUTE is revoked from PUBLIC,
empiredb_app, and the materializer login role and granted only to
empire_intelligence_materializer.

The capability role receives no direct SELECT/INSERT/UPDATE/DELETE authority on
prospect_acquisitions, prospect_entity_links, or business_entities.

It cannot create prospects, modify identities, send outreach, accept terms,
move funds, trigger fulfilment, recognize revenue, or expand authority.

## Runtime

tam_market_runtime.py will consume this RPC through the existing restricted
materializer connection, map rows to MarketEntityObservation, build the
evidence-backed TAM snapshot, and write only:
runtime/tam_market_intelligence/latest.json.

Active industries/countries are explicit runtime configuration. Absence of
configuration fails closed rather than classifying every observed market as
new.

Opportunity Radar may consume the snapshot, but TAM expansion candidates remain
research-only and factory-blocked until independent buyer-intent, demand,
economics, distribution and fulfilment evidence exists.

## Promotion

Migration 028 is HELD until explicit database activation. Required before DONE:
1. executable DB security/semantics tests;
2. Python runtime/radar tests;
3. explicit migration activation;
4. live restricted-reader smoke;
5. live TAM snapshot with canonical evidence;
6. Opportunity Radar sees the TAM source without authority expansion.
