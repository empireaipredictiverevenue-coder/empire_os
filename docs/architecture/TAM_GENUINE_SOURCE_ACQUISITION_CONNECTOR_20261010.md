# EmpireOS TAM — genuine-source acquisition connector v1

Date: 10 October 2026. Code release prepared, real RECC source connection demonstrated, canonical entity matching still subject to authorised one-shot live observation.

## Production problem established from canonical read-only audit
- UK/US TAM scoped v044 sample: eight US-roofing eligible records; five other market cells have no sampled observations.
- Bounded canonical candidate audit: 83 *exact-sector solar entities* with active identity links and zero matching acquisition ledger rows. This is the immediate highest-impact recovery lane.
- 184 exact roofing entities, 39 with acquisitions; country evidence is incomplete. Insurance: 108 *possible niche aliases*, zero exact-sector entities; aliases are NOT verified insurance businesses.
- A prior healthy canonical match does not imply a new acquisition. The existing crawler's materialize_prospect intentionally skips existing matches; forcing that new-prospect path would risk duplicate identities.

## Implemented non-mutating existing-entity evidence bridge
- Pure matching: empire_os/tam_source_acquisition_connector.py
- Operator CLI: scripts/run_tam_source_acquisition_connector.py
- Minimal root-gated shell entry: scripts/run_tam_source_acquisition_connector.sh
- Tests: tests/test_tam_source_acquisition_connector.py

The bridge can sample from two existing owned software source adapters:
1. RECC Solar PV member directory, source recc_solar, **GB solar only**. This is the highest-priority source for the 83 linked solar targets. The public directory provides source membership page evidence. Source code limits are 40 records; never reproduce, resell or publish raw directory content.
2. Public OpenStreetMap/Overpass observations, source overpass_osm, roofing or solar, GB/US but only for an explicit existing, country-verified market metro. OSM evidence needs identity corroboration. No paid third-party acquisition services.

An unprivileged real-source probe successfully fetched TWO actual RECC GB solar entries and verified both original member-page URLs. This demonstrates the public source can work **without** accessing EmpireDB; it does **not** establish matching results against the 83 canonical entities.

## Identity and provenance safeguards
- Canonical DB query is a single bounded, READ ONLY transaction on the local empiredb. It selects only exact-sector entities with active prospect link(s), excluding entities already backed by an acquisition on any active link. There is NO source/write cross-tenant assumption, login promotion or automatic account authority.
- Names require exact normalized identity; member directory URL must be authentic recc.org.uk scheme-member HTTPS URL (not lookalike domains). OSM must use authentic OpenStreetMap object HTTPS URL.
- A name match plus independent website host or phone agreement, without contradictory website evidence, creates **STRONG_EVIDENCE_REVIEW**, not an authorised automatic match. Name-only, conflicting website, duplicate canonical entity/prospect, or multiple source candidates go to manual review.
- The result is a private root-owned 0600 review JSON under /var/lib/empire/source-acquisition-review/. The stdout only shows aggregate counts and report location, not companies, phones, URLs, emails or DSNs.
- Each review finding contains canonical entity/prospect IDs, source URL, exact evidence basis, source locale and a deterministic SHA-256 review ID for later human gating. It explicitly declares no acquisition appended and no external execution authority. It does not invoke ingest_prospect_atomic for existing prospects and never fabricates acquisitions.
- IMPORTANT: matching a member directory observation to a canonical entity does not by itself authorize an INSERT to prospect_acquisitions, tenant authority, outreach, payments or buyer intent.

## One bounded live preview command

An authorised root operator runs:

    cd /srv/empire_os && sudo -n bash scripts/run_tam_source_acquisition_connector.sh --observe --source recc_solar --sector solar --country GB --max-targets 250 --max-source 40

The stdout gives aggregates: source observations, potential existing-entity matches, strong-evidence-review candidates, manual-review counts and the root-private report path. An observed zero **does not** establish no matching company: the RECC source is capped to forty and target queries are capped to 250.

For a UK/US roofing or solar metro with existing geo_registry support, the same command accepts --source overpass_osm --metro '<explicit market name>' --country GB|US --sector roofing|solar. Source country must match that market. No broad location guess.

**Current production state:** This release is an evidence-finding and identity-review tool, not an acquisition-ledger writer. A separately approved append-only acquisition attachment release must enforce exact entity/prospect binding, reviewed genuine source proof, country evidence, fingerprint uniqueness and idempotent transaction semantics before any real DB mutation. It must preserve original source acquisition history; never silently update or backfill from guesses.

## Next commercial tasks, in dependency order
1. Run this GB-solar preview and review the actual matching evidence packet privately. **Do not paste private company/contact data into public chat** unless appropriate; aggregate output is sufficient to plan.
2. If truly corroborated, implement and separately authorize a bounded append-only existing-prospect acquisition attachment, with suppression/duplicate/tenant checks and rollback rehearsal.
3. Run TAM scoped read once to verify country-specific canonical source admission. Do not call an inferred market size or buyer demand.
4. Extend to UK/US roofing original-source recovery. For insurance, first independently verify entity classification; do not auto-promote 108 substring-based aliases.
