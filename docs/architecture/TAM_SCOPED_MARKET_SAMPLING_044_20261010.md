# TAM 044 — market-aware country/sector sampling (PREPARED, HELD)

Date: 10 October 2026

## Problem proved by live run

Stage 2 was successfully activated using isolated EmpireDB TAM role and function 043. Canonical receipt: 21 globally sampled source rows, 13 excluded after sampling, 8 retained US roofing records, 1 observed market scope. No verified TAM denominator, buyer intent or external execution.

The 043 function selects a globally sorted set and applies `LIMIT` **before** its caller applies the founder-approved UK/US × roofing/solar/insurance scope. Thus a dominant US roofing cohort can starve the other five requested markets, even if other eligible source records exist later in the database.

## Upgrade prepared, NOT deployed

- **New function:** `migrations/empiredb/044_tam_scoped_market_sampling.sql` creates **separately named** `public.get_tam_market_observations_scoped(text[],text[],integer)`. It leaves existing function 043 and Market GPS unchanged. The new function uses the existing `empiredb_migrator` owner and `SECURITY DEFINER STABLE SET search_path=''`, with EXECUTE **only** for `empire_tam_market_reader`; no customer login or source-table SELECT grant.
- **Exact pilot allowlist:** `GB,US`, `roofing,solar,insurance`. Reject duplicate, unknown, noncanonical or null countries/sectors. Requested sample bound is `1..1000`, and must be large enough to allocate at least one slot per market.
- **Market-aware SQL:** applies the country/industry constraints **inside** the database query, keeps newest provenance per canonical entity within each market, and allocates per-market quotas deterministically from the global limit. Under a six-market 1,000-row request, four market cells get 167 slots and two get 166; actual selected counts can be lower. Total returned rows never exceeds 1,000.
- **Result truth:** `empire.tam-scoped-reader.v1` returns `rows` plus six `scope_coverage` entries (including those with `selected_count=0`), per-scope quotas, `population_complete=false`, `buyer_intent_inferred=false`, `tam_inferred_from_roster=false`, `execution_authority=none`. **Zero sampled observations is not zero businesses, and a quota is not a market denominator.**
- **Runtime gating:** `empire_os/tam_market_runtime.py` retains the original 043 reader by default. Only explicit `EMPIRE_TAM_READER_MODE=scoped_v1` opts into 044. Before any scoped market data read, the restricted TAM login performs a separate **read-only live catalog verification** of both the existing 043 authority and new 044 owner, security definer, empty search path, permissions and return type. Missing/unsafe 044 **blocks** the run; there is no fallback.
- **Strict ingestion:** rejects rows outside approved industry/country pairs, duplicate entities, source authority escalation, fabricated or contradictory quota counts, missing/duplicate coverage cells, wrong total and inferred market population. Snapshot must be private 0600 as before.
- **Founder and Radar:** the validated snapshot preserves existing market-scope observations and passes through the existing Opportunity Radar. The founder supervisor separately exposes requested scope count and zero-observation count. Research-only, no new TAM sales, prospect send or revenue promises.
- **Read-only production preflight:** `scripts/preflight_empiredb_tam044.sql`, independently tested in disposable PostgreSQL, checks the live 043 function and roles, table privilege safety, no 044 collision, unchanged Market GPS permissions. It does not deploy or query companies.
- **No new timer/agent.** The already installed `empire-tam-market-read.service` remains a static on-demand unit. Its root-owned scope env currently **does not** opt into the new mode.

## Activation gates (not covered by the earlier stage-2 consent)

1. **Separate founder authorization for migration 044.** An authorised DBA runs the read-only 044 catalog preflight against canonical EmpireDB, makes/verifies the usual fresh database and globals backup/rollback inventory, then installs 044 in a guarded transaction. Read back the new function's exact owner/ACL/search_path and verify original 043, old Market GPS, and source-table isolation remain unchanged.
2. **Separate authorization for a second bounded market-data read and the scope-mode config change.** Using the existing **protected** on-demand service, add only `EMPIRE_TAM_READER_MODE=scoped_v1` to the approved root-owned non-secret `/etc/empire/tam-market-scope.env`, then run one bounded 1,000-row read through 044. No new credential/password/LOGIN change is needed, and do not restart unrelated services.
3. Verify all six coverage cells and actual source rows; update the existing Radar and founder views; ensure no invented denominator, demand, buyer, or revenue. Preserve prior snapshot backup for audit; do not treat zero observed cells as evidence of zero addressable businesses.
4. If 044 fails, leave the installed 043 reader and current private snapshot intact. A separately approved rollback can remove only function 044 and revert the isolated TAM mode flag; it **must not** remove existing 043 or legacy materializer permissions.

**Current state:** scoped 044 SQL, reader code, preflight and disposable test contracts are engineering changes only, not proof of production activation.


## Guarded release pack and independent verification

The entire release pack is **held** pending a separate founder authorization for production migration 044:

- `scripts/deploy_empiredb_tam044.sh` accepts `--preflight` for root/DBA read-only catalog assessment; its *DDL* path requires **`--apply --approved-044`**, and deliberately refuses accidental/malformed invocations.
- Before DDL it verifies exact SHA-256 hashes of migration, preflight and postverify, checks the canonical PostgreSQL 18 primary and exclusive lock, reruns the read-only preflight, checks backup headroom, takes **fresh** private `pg_dump -Fc empiredb` plus `pg_dumpall --globals-only`, verifies archive format, canonical source table inventory and checksums, then applies 044 **once** in a transaction.
- `scripts/verify_empiredb_tam044.sql` is a read-only, final-ROLLBACK catalog proof for owner, function security, empty PostgreSQL 18 search path, correct EXECUTE grants (no PUBLIC/legacy), zero direct TAM role table/column rights and unchanged 043/Market GPS.
- `deploy/empiredb/tam044_scoped_rollback_held.sql` is a separately gated rollback that removes **only** function 044, not existing TAM 043, the current TAM login/secret or Market GPS. Disposable PostgreSQL proves this isolation.
- `tests/test_tam044_guarded_deployer.py` proves no-approval/non-root refusal and the absence of service restart, credential mutation, new market-data reads or payments from the 044 release.
- To activate the **new sampling method**, the separately approved non-secret environment change `EMPIRE_TAM_READER_MODE=scoped_v1` must be added to the existing protected TAM scope environment and the on-demand static unit run once within its approved bounded scope. The deployment script deliberately does **not** make this change or issue that read. The existing 043 path remains the default.
- Do not treat selected quotas or empty market cells as a census. Distinguish `requested_market_scope_count`, `market_scope_count`, and `market_scope_zero_observation_count` in founder reporting.
- Do not run 044 deployment with remote system permissions that have blocked DBA commands. Use the authorised DBA path only after the founder explicitly approves 044; *current work prepares and tests, it does not grant migration authority*.

**Production truth:** Existing Stage-2 043 has a valid 0600 TAM snapshot of 8 US roofing records; existing Market GPS is healthy; new scoped 044 is not installed and no second market read has occurred.
