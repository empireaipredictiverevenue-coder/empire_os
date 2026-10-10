# TAM solar - shared directory URL contamination and genuine website discovery

10 October 2026 | engineering release prepared; NO production first-party discovery run yet.

## Proven live evidence and root cause

Bounded canonical 83 solar entities, with 869 active linked prospects and zero source acquisitions. Original RECC public source sample of 120 returned zero identity matches. Independent read-only website eligibility diagnostics reported 845 nonempty website values across 71 different entities, all from exactly ONE shared host; 12 entities had no candidate URL. The common host is NOT an independent business website for 71 companies. No website was probed; no acquisition was appended. Do not classify those values as qualified first-party websites, infer GB from metro or a domain suffix, or blindly select one linked prospect.

## Existing upstream guard and legacy remediation boundary

Current canonical prospect_ingest.prepare_candidate explicitly does NOT copy LeadCandidate.url into prospect.website, and preserves it as source_url evidence. The shared-host contamination seems legacy or alternate and its exact source path remains unverified. The live production rows are NOT modified. Existing business_entities have resolution_state=resolved_candidate from identity_resolver promotion but not verified identity, and zero explicit GB provenance in this audit.

## Integrated bounded recovery via owned Search Fabric

Updated same source acquisition connector, not another parallel database:
- empire_os/tam_source_acquisition_connector.py
- scripts/run_tam_source_acquisition_connector.py
- tests/test_tam_first_party_discovery_review.py

The new source=first_party_search mode uses one READ ONLY local EmpireDB query to obtain at most 250 entities and selects at most THREE by default (HARD LIMIT FIVE) with coherent name/metro linked records. It searches business name plus recorded metro through the existing Empire Search Fabric using at most five SERP results per selected entity. Metro is ONLY a search disambiguator, NOT verified country. It refuses known third-party directories, RECC/OSM source domains, the shared original host(s), search hosts already claimed by a different original entity, unsafe/nonpublic literal IPs, usernames, invalid ports, domain collisions between candidate entities, and ambiguous multiple plausible hosts.

A single unambiguous candidate host is then probed using existing Search Fabric site_probe(public_only=True), max_pages=2 and <=10s site budget. Verification requires HTTPS, same host, a real same-host page receipt, positive existing Search Fabric identity_guard verdict, and EXACT normalized canonical company name on that site's own business-name evidence. All review findings are kept in a private 0600 JSON; only counts and the private file location appear in stdout. Even a successful identity-review candidate does NOT verify individual prospect binding among 869 links, GB country, buyer intent, or source acquisition authorization. No writes, no timers, no outbound.

The originally polluted website field is used only as a HOST COLLISION / EXCLUSION SIGNAL, not as trusted input for source discovery. All candidate domains come independently from owned Search Fabric.

## One guarded, bounded research run AFTER this commit

cd /srv/empire_os && sudo -n bash scripts/run_tam_source_acquisition_connector.sh --observe --source first_party_search --sector solar --country GB --max-targets 250 --max-source 3

One canonical read-only query; at most three search requests and three public site probes. No database writes. If search infrastructure is degraded, returned zero is SOURCE_UNAVAILABLE / UNOBSERVED, not zero valid companies. Do not rerun automatically. Inspect only the aggregate stdout unless a founder explicitly approves private detail review.

Next required separately approved workflow: check exact original corporate identity, verify jurisdiction from first-party or official registry documents, select the correct existing prospect relation, implement idempotent append-only source ledger attachment with transactional duplicate and tenant/suppression guards, then reread TAM on founder approval. Nothing may be automatically written merely because a website was observed.