# Canonical Lead Intelligence

## Purpose

Provide one read-only, evidence-preserving Lead Intelligence view over the
canonical EmpireOS prospect and Intelligence Fabric graph without introducing
another lead database or silently widening commercial authority.

## Canonical read graph

```text
prospects
  -> prospect_acquisitions
  -> prospect_entity_links
  -> business_entities
  -> prospect_qualifications
  -> intelligence_facts
  -> intelligence_signals
  -> intelligence_scores
  -> intelligence_contact_points
  -> intelligence_employment
```

Missing optional layers remain explicit unknowns. Absent facts, signals, scores,
identity links, contacts or qualification are never coerced into zero or false
values. Conflicting temporal facts remain separate evidence rows.

## Compatibility convergence

Legacy lead intake URLs remain available for compatibility, but both
`/v1/leads/intake` and `/v1/leads/direct` converge on the canonical
Supabase prospect ingestor.

Compatibility evidence such as external lead ID, source, intent, consent,
campaign metadata, ZIP, IP address and user agent is preserved in canonical
acquisition evidence rather than written to a second CRM intake database.

The existing legacy `/v1/leads` read/status surface remains compatibility-only
for now. Its broken return/status contracts were repaired, but it is not yet the
canonical Lead Intelligence read surface. Consumers will migrate incrementally
after parity is proven.

## Runtime trust boundary

Production Lead Intelligence reads use a dedicated PostgreSQL DSN:

`EMPIRE_LEAD_INTELLIGENCE_DSN`

The runtime login is NOINHERIT and passwordless until provisioned out of band.
Every transaction executes:

```sql
SET LOCAL ROLE empire_lead_intelligence_reader;
```

The capability role has SELECT-only access to the exact canonical tables above,
cannot write those tables, cannot read unrelated commercial tables, and cannot
bypass RLS. The Python transport exposes a fixed query map rather than arbitrary
SQL and has no fallback to `service_role`.

## Current status

Local/tested:
- canonical evidence-preserving read projection;
- GET-equivalent fixed query contract over direct PostgreSQL;
- dedicated read-only database role migration;
- canonical convergence of both lead intake compatibility URLs;
- repaired legacy lead list/status endpoint contracts;
- conflict-safe identity handling;
- bounded limits and strict UUID/filter validation;
- isolated RLS/permission tests;
- read-only canonical-vs-legacy parity engine;
- bounded parity CLI using the dedicated Lead Intelligence DSN and SQLite
  mode=ro; exact UUID, acquisition external-ID and unique identity fallback
  matches are reported with explicit confidence and ambiguity handling.

Production status:
- the SELECT-only reader-role migration is applied in canonical Supabase;
- the dedicated login remains passwordless/unprovisioned.

Still gated:
- provisioning the dedicated login password/DSN;
- exposing any internal Lead Intelligence API;
- runtime parity through the dedicated reader identity once provisioned;
- any legacy-consumer retirement that changes live behavior.

Production inspection found 29,807 canonical prospects, 12,184 active identity
links, 1,177 v1 qualifications and 466 prospects with both identity and
qualification. Legacy SQLite crm_leads and lane_leads are empty, so there is
no meaningful SQLite lead inventory to migrate. The acquisition ledger currently
contains only one row and must not be treated as historical provenance coverage.

No runtime credential activation or lead mutation occurs as part of the current
reader foundation.
