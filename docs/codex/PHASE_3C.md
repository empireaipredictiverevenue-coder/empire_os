# Codex Task Packet — Finish Phase 3C

## Goal

Finish Phase 3C canonical prospect acquisition safely. Do not expand scope into Phase 3D.

## Current checkpoint

Base branch:

`feature/revenue-intelligence-v2`

Known pushed checkpoints:

- `af3d33a feat: add atomic canonical prospect acquisition`
- `8df336c chore: remove synthetic production data paths`
- `c82f02f feat: wire crawler to canonical prospect acquisition`
- `bbea742 feat: bridge direct lead intake to canonical prospects`

At `bbea742`, the Phase 3C code path is largely implemented and focused tests passed. Treat this task as a final code-readiness review plus preparation for the human-gated live migration and smoke.

## Architecture to preserve

- Supabase/Postgres `prospects` is canonical owned prospect inventory.
- `prospect_qualifications` is scoring/intelligence.
- `fulfilment_orders` is commercial allocation/delivery state.
- `commercial_events` is the immutable ledger.
- `lane_leads` is legacy compatibility/operational state and must not establish canonical prospect identity.
- Buyer capacity gates delivery/allocation, not acquisition.

Canonical acquisition path:

`LeadCandidate -> prepare_candidate -> lookup_existing_prospect -> materialize_prospect -> ingest_prospect_atomic`

## Already implemented

### Canonical acquisition

`empire_os/prospect_ingest.py` provides candidate preparation, conservative identity lookup, materialization, deterministic identity claims, and fail-closed ambiguity behavior.

`empire_os/autonomous_execution_bus.py` provides the canonical Supabase REST reader and `_write_canonical_prospect`, targeting `/rest/v1/rpc/ingest_prospect_atomic`.

### Atomic acquisition migration

`migrations/003_prospect_acquisition_ledger.sql` provides the intended identity-claim/acquisition ledger and `ingest_prospect_atomic(...)` RPC. The `unnest(p_identity_keys)` aliasing has been hardened to an explicit column alias.

Expected RPC decisions currently include:

- `created`
- `existing_ingest`
- `existing_identity`
- `ambiguous`

Migration `003` has not been intentionally applied live. Live application is human-gated.

### Real crawler path

`empire_os/crawler_runner.py` routes real `LeadCandidate` records through canonical acquisition and does not fall back to `/v1/leads/direct` or `lane_leads` for canonical identity.

### Compatibility intake

`/v1/leads/direct` remains available for AEO/forms and acquisition callers, but at checkpoint `bbea742` it is intended to route into canonical acquisition, preserve the `{"ok": true, ...}` success contract, stop generating timestamp-based `prospect_*` identities, and stop directly inserting new canonical identities into `lane_leads`.

`empire_os/agents/data_acq_agent.py` has also been updated to handle `LeadCandidate` objects while preserving source evidence.

### NO-SIM cleanup

Synthetic production fallbacks were removed or disabled from active scanner, satellite, customer-analysis, marketplace, and related paths. Do not reintroduce them.

## Codex task

1. Inspect the current branch and diff from `bbea742` before editing.
2. Review the Phase 3C implementation end-to-end for correctness and architectural consistency.
3. Verify every possible `ingest_prospect_atomic` decision is handled correctly by `/v1/leads/direct` and crawler acquisition.
4. Verify no active production path in the Phase 3C acquisition flow can fabricate canonical prospect identity or silently fall back to SQLite.
5. Verify `migrations/003_prospect_acquisition_ledger.sql` is syntactically and logically ready for live application, including race/idempotency behavior. Do not apply it live.
6. Add only narrowly necessary regression tests if a real gap is found.
7. Run the focused Phase 3C tests and compile changed Python modules.
8. Run `git diff --check` and report the exact status.
9. Search narrowly for remaining active production callers that can bypass canonical acquisition. Report findings without broad legacy cleanup.
10. Produce a completion report and stop before any human-gated live action.

## Human-gated actions — do not perform

Without explicit human approval, do not:

- apply migration `003` to live Supabase;
- restart production services;
- run a live source smoke that creates real records;
- switch autonomous execution to live mode;
- execute queued jobs;
- send outreach;
- deliver leads to buyers;
- create invoices or settlements;
- modify `recovery/` or `toop`;
- print or expose secrets.

## Validation commands

Use focused tests first:

```bash
.venv/bin/python -m pytest -q \
  tests/test_crawler_runner.py \
  tests/test_prospect_ingest.py \
  tests/test_qualification_materializer.py
```

Compile changed Python modules as applicable, then:

```bash
git diff --check
git status --short
git diff --stat
```

Known unrelated legacy full-suite collection failures may exist. Report them if encountered; do not broaden scope automatically.

## Completion report

Report exactly:

1. architectural summary;
2. files changed, if any;
3. tests/commands run and exact results;
4. remaining Phase 3C blockers;
5. whether migration `003` remains unapplied live;
6. proposed commit message if changes were made;
7. concise diff/risk review;
8. recommendation for the human-gated migration + queue-gate + controlled real-source smoke sequence.

Do not state that Phase 3C is production-complete until the live migration, fresh queue gate, and controlled live smoke have actually been completed by or with explicit human approval.
