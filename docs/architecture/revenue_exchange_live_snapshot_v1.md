# Revenue Exchange Live Snapshot v1 — Architecture Contract

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Revenue Exchange / Sales Revenue

## Purpose
Materialize a deterministic read-only Revenue Exchange snapshot from canonical
EmpireDB `public.revenue_exchange_observations` so Marketplace/Auction and Founder
surfaces have one persisted live read model.

This does not create a second exchange, pricing engine, allocation engine or truth store.
EmpireDB remains canonical business truth.

## System diagram

EmpireDB `revenue_exchange_observations`
  -> dedicated `empire_revenue_exchange_reader` role
  -> `PostgresRevenueExchangeReader`
  -> normalize + latest-per-(niche,metro)
  -> `runtime/revenue_exchange/latest.json`
  -> Marketplace/Auction readiness / Founder surfaces

## Canonical inputs
Read only:
- observation_key
- niche
- metro
- qualified_inventory_count
- active_buyer_capacity
- verified_price_per_lead_cents
- observed_at
- source
- evidence
- created_at

The transport must use the existing least-privilege reader role. No writer or RPC
is required by this materializer.

## Snapshot rules
- Rows are normalized through `normalise_exchange_snapshot(...)`.
- Keep only the newest row per casefolded `(niche, metro)` market key.
- Preserve `observation_key`, `source`, structured `evidence`, `created_at` and
  normalized snapshot fields.
- Output ordering is deterministic by niche/metro.
- Empty database result is valid and yields `market_count=0` plus an explicit blocker.
- Invalid rows are reported as blocked rows; they are never coerced into valid data.
- File write is atomic.

## Reconciliation truth rule
The observation itself is canonical market evidence but it must not certify its own
independent reconciliation.

The materializer may expose reconciliation evidence only when the observation's
structured `evidence` object explicitly contains independent values:
- `inventory_count`
- `buyer_capacity`
- `verified_prices_cents`
- non-empty `evidence_refs`

If those are absent, Marketplace reconciliation remains blocked with missing-evidence
reasons. Never mirror the observation values into reconciliation fields merely to make
`review_ready=true`.

## Output
`runtime/revenue_exchange/latest.json`

Required top-level fields:
- schema_version
- generated_at
- source=`canonical_empiredb_revenue_exchange_observations`
- mode=`OBSERVE`
- market_count
- invalid_row_count
- blocker_count
- markets
- blockers
- read_only=true
- execution_authority=none
- allocation_authority=none
- pricing_authority=none
- settlement_authority=none
- payment_action=false
- revenue_recognition=false

Each market row includes:
- market_key
- observation_key
- snapshot
- source
- evidence
- created_at
- reconciliation_evidence (or null)

## Runtime identity and activation

The snapshot runtime MUST NOT use the broad canonical `EMPIREDB_DSN` login to
borrow the reader capability. It uses one dedicated NOINHERIT LOGIN identity:

- login: `empire_revenue_exchange_reader_login`
- capability role: `empire_revenue_exchange_reader`
- env key: `EMPIRE_REVENUE_EXCHANGE_READER_DSN`
- protected env file: `/etc/empire_revenue_exchange.env`

The login is granted exactly the Revenue Exchange reader capability role. The
transport continues to execute `SET LOCAL ROLE empire_revenue_exchange_reader`
inside each transaction. The login receives no writer, allocation, pricing,
payment, settlement or revenue-recognition capability.

Provisioning this LOGIN/password/role membership is an authority activation and
remains founder-gated even though it is read-only. The code/provisioner may be
staged and tested before that approval, but must not apply the role or credential.

A oneshot service/timer may refresh this read model on a bounded cadence using:
- User=ubuntu
- `/etc/empire_revenue_exchange.env`
- no outbound secret file required
- no network destination other than local EmpireDB

## Authority
Always read-only. No ingest, allocation, pricing mutation, terms, payment, settlement,
fulfilment or revenue recognition.

## Files
- `empire_os/revenue_exchange_transport.py` (reader fields only)
- `empire_os/revenue_exchange_snapshot.py`
- `scripts/refresh_revenue_exchange_snapshot.py`
- `scripts/provision_revenue_exchange_reader.py`
- `tests/test_revenue_exchange_reader.py`
- `tests/test_revenue_exchange_snapshot.py`
- `deploy/systemd/empire-revenue-exchange-snapshot.service`
- `deploy/systemd/empire-revenue-exchange-snapshot.timer`

## Verification
- dedicated-role reader test
- latest-per-market deterministic materialization
- evidence-lineage preservation
- no self-reconciliation
- invalid-row fail-closed behavior
- atomic write
- no authority expansion
- live read from EmpireDB
- systemd read-only service/timer verification if deployed

## Completion
This slice is complete only when the live artifact is generated from EmpireDB and
Marketplace can consume a real `ExchangeSnapshot`. Marketplace allocation readiness
may still be blocked by missing independent reconciliation evidence; that is acceptable
and truthful.
