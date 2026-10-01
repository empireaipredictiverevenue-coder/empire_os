# Production Dirty Worktree Recovery Plan — 2026-10-01

Status: READ-ONLY CLASSIFICATION / NO RESET / NO CLEAN

## Production truth

- Total dirty paths (expanded): 10778
- Tracked modified/deleted paths: 112
- Untracked paths: 10666
- Aider environment/cache noise: 10578
- Non-Aider untracked candidate paths: 88

## Rule

Do not use git reset, git clean, rebase, or broad staging. Candidate work is preserved and promoted by scoped path/branch verification only. Tool/cache noise is ignored, not deleted by this closure drop.

## Non-Aider untracked candidate buckets

- backend: 21
- deploy: 1
- docs: 20
- frontend: 1
- migrations: 5
- other: 7
- scripts: 10
- tests: 23

## Protected / held migrations

- M: migrations/empiredb/017_cutover_compatibility_rpc_parity.sql
- ??: migrations/empiredb/017_cutover_compatibility_rpc_parity.sql.pre-semicolon-fix
- ??: migrations/empiredb/022_commercial_catalog_restricted_reader.sql
- ??: migrations/empiredb/023_revenue_pulse_restricted_reader.sql
- ??: migrations/empiredb/024_outbound_provider_event_ingest.sql
- ??: migrations/empiredb/025_owned_campaign_intake.sql

## Closure action

- Add Aider virtualenv/history/cache paths to .gitignore.
- Preserve all code/data candidates until their owning candidate branch is verified.
- Keep migration 018 checksum-protected.
- Keep migration 025 HELD_FOR_FOUNDER_DB_APPROVAL and unapplied.
- Promote the closure-drop branch as one reviewed candidate; do not merge production piecemeal.
