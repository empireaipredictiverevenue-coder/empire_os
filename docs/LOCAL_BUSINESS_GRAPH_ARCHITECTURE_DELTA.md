# Local Business Graph — Architecture Delta

Date: 2026-10-01
Status: IMPLEMENTATION-READY / OBSERVE-FIRST

## Diagram

```text
OSM/Overpass + Public Registries + First-Party Sites + Search Fabric
        + Public/Authorized Social Evidence + Licensed Providers
        -> Candidate Quality Gate
        -> Canonical Prospect Ingest
        -> Business Entity Resolution
        -> Local Business Graph Projection
        -> Intelligence Facts / Contact Points / Signals
        -> Contact Resolution V2
        -> B2B Data Fabric
        -> Predictive Revenue / Buyer Demand / Opportunity Value
        -> Verified Outcome Learning
```

## Purpose

Turn EmpireDB's existing canonical business identity and intelligence tables into
a coherent Local Business Graph without creating a duplicate lead database.

The graph represents real local businesses, their locations, public/verified
contact points, categories, licences, people relationships, social/profile
evidence, commercial signals, freshness and provenance.

## Canonical placement

Canonical identity remains:
- public.prospects for owned source prospect inventory;
- public.business_entities for resolved business identity;
- public.prospect_entity_links for lineage;
- public.business_entity_conflicts for unresolved identity/data conflicts.

Canonical intelligence remains:
- public.intelligence_sources;
- public.intelligence_people;
- public.intelligence_facts;
- public.intelligence_contact_points;
- public.intelligence_signals;
- public.intelligence_scores;
- public.intelligence_outcomes.

No new database or migration is introduced in V1.
Migration 018 remains untouched and HELD.

## Local business projection contract

A graph projection may expose:
- entity_id and canonical business name;
- niche/category and geography;
- verified/observed website, domain, phone and email evidence;
- public address/location evidence;
- licence/registry identifiers as facts;
- person relationships only where identity evidence exists;
- public social/profile URLs and observed social signals;
- source provenance, first/last seen timestamps and confidence;
- contradictions/conflicts;
- current commercial signals and freshness.

Unknown remains unknown. A social profile or directory record alone is not
canonical identity proof.

## Social evidence lanes

Instagram:
- public or explicitly authorized business/profile evidence only;
- handles, profile URL, bio/category, public outbound links and public activity
  may be recorded as OBSERVED evidence when collection is permitted;
- no login/session bypass, credential automation or access-control evasion.

LinkedIn:
- do not build anti-bot scraping or bypass access controls;
- use authorized API access, licensed providers, first-party/company links and
  publicly indexed evidence where permitted;
- LinkedIn-derived facts remain source-attributed observations until
  corroborated by stronger identity evidence.

Social evidence may improve discovery/intent confidence but cannot independently
upgrade a person/contact to VERIFIED.

## V1 implementation

Create a pure deterministic projection library:
- empire_os/local_business_graph.py
- tests/test_local_business_graph.py

Inputs are existing canonical entity/fact/contact/signal rows supplied by callers.
The V1 core performs no network calls and no database writes.

Responsibilities:
- normalize a local-business graph packet;
- preserve evidence refs and timestamps;
- separate OBSERVED / VERIFIED / UNKNOWN;
- surface social evidence without treating it as truth;
- expose conflicts explicitly;
- compute freshness status without inventing values;
- grant no external execution authority.

## Authority

Allowed: OBSERVE and deterministic internal computation.

Forbidden:
- canonical identity mutation;
- fabrication of a business, person or contact;
- live social scraping that bypasses platform controls;
- live outreach;
- buyer approval;
- allocation/fulfilment;
- payments/settlement/revenue recognition;
- migration or authority expansion.

## Worker assignment

Hermes owns only:
- empire_os/local_business_graph.py
- tests/test_local_business_graph.py

Empire Coder owns B2B Data Fabric files separately.
Codex is read-only audit.
Swarm V6 is independent verification.

## Verification

Required:
- missing/ambiguous identity fails closed;
- stale facts and contact points are marked stale;
- verified and observed evidence remain distinct;
- social evidence cannot self-verify identity/contact;
- conflicting values are surfaced;
- no execution authority;
- existing identity/prospect/Overpass tests remain green.

## Live verification

Read-only only: exercise the projection against existing EmpireDB rows after
independent verification. No migration, restart, send, or database mutation.
