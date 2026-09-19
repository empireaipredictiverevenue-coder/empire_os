# Phase 3F Intelligence Materializer

Status: local/tested. Production writer activation is gated.

## Purpose

Project already-observed canonical prospect and qualification evidence into the
Empire Intelligence Fabric without inventing enrichment, confidence, or
commercial outcomes.

## Inputs

A prospect is eligible only when it has exactly one active canonical entity
link and a compatible empire_os.lead_scoring qualification. v2 is preferred;
legacy v1 is accepted only as an explicit compatibility fallback.

## Evidence rules

- Prospect facts preserve observed values exactly, including false and zero.
- Missing values are skipped rather than replaced with synthetic defaults.
- Fact confidence is the active identity link match_score, describing the
  confidence of associating the prospect observation with the canonical entity.
- Qualification v2 score confidence is the persisted evidence_confidence,
  preserving v2 evidence sufficiency separately from commercial quality.
- Legacy v1 score confidence remains data_completeness_score / 100 and is
  explicitly labelled as a compatibility proxy, not outcome-calibrated
  predictive confidence.
- v2 observed_dimensions and unknown_dimensions are preserved in score lineage.
- Fact evidence hashes are deterministic and unique.
- Score identity is unique on entity, score type, model and scored_at.
- Cross-prospect identity or qualification mismatches fail closed.

## Runtime authority

The staged empire_intelligence_materializer role has:
- SELECT on canonical prospect, identity, qualification and required
  Intelligence Fabric lookup tables;
- INSERT only on intelligence_facts and intelligence_scores;
- no UPDATE or DELETE;
- no access to unrelated commercial tables;
- RLS insert policies limited to canonical company facts and explicitly
  supported empire_os.lead_scoring:v1/v2 qualification scores.

The runtime login is NOINHERIT, passwordless in the staged migration, and must
be provisioned separately before production activation.

## Current production evidence

As of 2026-09-19, canonical Supabase contains 29,807 prospects, 12,184 prospects
with active identity links, 1,177 prospects with qualification records, and 466
prospects with both active identity and qualification. The acquisition ledger
contains only one row, so historical acquisition provenance is not yet
backfilled and must not be treated as complete history.

No bulk historical Intelligence Fabric write has been activated. The staged operator entrypoint is scripts/intelligence_materialize.py and accepts exactly one canonical prospect UUID per invocation.
