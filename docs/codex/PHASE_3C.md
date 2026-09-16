# Codex Task Packet — Finish Phase 3C

## Goal

Finish Phase 3C canonical prospect acquisition safely. Do not expand scope into Phase 3D.

## Current checkpoint

Base branch when this task packet was created:

`feature/revenue-intelligence-v2`

Known pushed checkpoints before this setup branch:

- `af3d33a feat: add atomic canonical prospect acquisition`
- `8df336c chore: remove synthetic production data paths`
- `c82f02f feat: wire crawler to canonical prospect acquisition`

There may be newer local/unpushed work on the operator host. Before making changes, inspect the current branch/worktree and do not overwrite unrelated user changes.

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

### `empire_os/prospect_ingest.py`

- `prepare_candidate`
- conservative identity lookup
- `materialize_prospect`
- deterministic identity claims

### `empire_os/autonomous_execution_bus.py`

- canonical Supabase REST reader
- `_write_canonical_prospect`
- RPC target: `/rest/v1/rpc/ingest_prospect_atomic`

### `migrations/003_prospect_acquisition_ledger.sql`

Intended to provide:

- `prospect_identity_claims`
- `prospect_acquisitions`
- atomic `ingest_prospect_atomic(...)`
- idempotency and race-safe identity ownership
- service-role execution only

Migration has not been intentionally applied live as part of this task packet. Treat live application as human-gated.

### `empire_os/crawler_runner.py`

Crawler is intended to use canonical acquisition and fail closed rather than fall back to `/v1/leads/direct` or `lane_leads`.

### NO-SIM cleanup

Synthetic production fallbacks were removed or disabled from scanner/satellite/customer-analysis/marketplace-related active paths. Do not reintroduce them.

## Immediate work to review/finish

1. Inspect the current worktree first. Preserve any intentional uncommitted Phase 3C changes.
2. Verify `migrations/003_prospect_acquisition_ledger.sql` SQL correctness, especially explicit aliasing for `unnest(p_identity_keys)`.
3. Review `/v1/leads/direct` in `empire_os/hub.py`.
   - It must remain compatible with active AEO/form/data-acquisition callers that expect `{"ok": true, ...}` on successful intake.
   - It must not generate timestamp-based canonical `prospect_*` identities.
   - It must not directly insert a new prospect identity into `lane_leads`.
   - It should route to canonical acquisition and fail closed if the canonical store/RPC is unavailable.
4. Review `empire_os/agents/data_acq_agent.py`.
   - Real source results are `LeadCandidate` objects, not necessarily dictionaries.
   - Preserve evidence/source metadata when forwarding intake.
5. Enumerate every decision returned by `ingest_prospect_atomic` and ensure compatibility route handling is correct for each one.
6. Add focused regression tests for:
   - new canonical acquisition;
   - matched read-only acquisition;
   - fail-closed behavior when RPC is unavailable;
   - direct endpoint payload compatibility;
   - ambiguous/conflicting identity behavior where applicable.
7. Run focused tests, compile changed Python, and run `git diff --check`.
8. Search for remaining active production code that can fabricate canonical prospect identity. Report findings, but do not broaden into unrelated legacy cleanup.

## Do not do

Without explicit human approval, do not:

- apply migration `003` to live Supabase;
- restart production services;
- run a live source smoke that creates real records;
- switch autonomous execution to live mode;
- send outreach;
- deliver leads to buyers;
- modify `recovery/` or `toop`;
- expose secrets.

## Validation commands

Use focused tests first. Current relevant suites include:

```bash
.venv/bin/python -m pytest -q \
  tests/test_crawler_runner.py \
  tests/test_prospect_ingest.py \
  tests/test_qualification_materializer.py
```

For changed Python modules:

```bash
.venv/bin/python -m py_compile <changed modules>
git diff --check
git status --short
git diff --stat
```

Known historical full-suite collection failures exist in unrelated legacy tests. Report them if encountered; do not mask them or expand scope automatically.

## Completion report

When done, report exactly:

1. architectural summary;
2. files changed;
3. tests/commands run and exact results;
4. remaining Phase 3C blocker(s);
5. whether migration `003` remains unapplied live;
6. proposed commit message;
7. concise diff/risk review.

Do not state that Phase 3C is production-complete until the human-gated migration, queue gate, and controlled live smoke have actually been completed.