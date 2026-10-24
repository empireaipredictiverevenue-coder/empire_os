# EmpireOS / PRIME — first-write authenticity and replay-control OWNER PROPOSAL

**24 October 2026 — Research worktree only. Original EmpireDB/Production untouched. NO EXECUTION APPROVAL.**

## Completed scoped engineering

- `empire_os/prime_first_write_attestation_preflight.py` (new) reuses pinned-key Ed25519 design from original EmpireOS. It checks **exact** original forecast digest, prediction reference, tenant-scope digest, immutable feature/model/policy lineage, signed claimed first-write clock, issuer owner `predictive_cloud`, intended audience, source-row fingerprint, issued-near-recording time (max 60 seconds), scope, key ID and digital signature.
- Requires original owner-provided `active_journal_authority(tenant,scope,now)` and `read_canonical_first_write(tenant,prediction_ref,now)` callbacks. The canonical first-write readback must match *exact* prediction hash, first-write time, first-write record fingerprint and an explicit append-only uniqueness attestation.
- Signing in the present cannot turn a historical backdated prediction into a first-write proof: signed `issued_at` must be within the original 60-second claim window. Archival review permits a past issuance window; real historic key legitimacy/rotation still needs the original security registry.
- The original `predictive_revenue_brain_bridge.py` now optionally accepts `signed_forward_first_write_attestations` and `original_first_write_verifier` while retaining the original forward journal, signed owner evidence, CRM, Quant and Economic Memory. **Signed proof never changes calibration truth, prediction accuracy, money, outbound or model promotion.** Output only reports `prime_first_write_attestation_preflight_status` and false authority flags, not private evidence.
- Adversarial offline tests use temporary test-only keys, synthetic original prediction fixtures, tampered signatures/models/timestamps/source rows, original tenant/source scope readers and deliberately repeated envelopes. This is a consistency gate, **not** a production first-write verification.

## Critical insufficiencies

An encrypted/signed-looking prediction is **not** independently precommitted merely because a supplied callback returned `True`. No authentic production original owner key registry, immutable first-write store, release-controlled database function, external timestamp anchoring, revoked-key historical authorization, or durable replay ledger is connected. Test signers and callback stubs do not establish real buyer intent or P&L.

A first-write append-only writer must atomically prevent the same prediction or evidence nonce being accepted twice, and do so in the original **EmpireDB PostgreSQL**, under restrictive existing roles. No new database is proposed.

## REVIEW-ONLY proposed EmpireDB design (do not run)

The following is a *proposal*, not a committed migration. Real schema/table name, retention, RLS, tenant roles, logging, backup and release prerequisites must be reconciled by the original EmpireDB + Security owners. The digest values are **purpose-scoped original-owner HMAC outputs**, NOT unsalted SHA-256 of guessable company/person IDs.

```sql
-- DESIGN SKETCH ONLY. DO NOT EXECUTE OR COPY TO PRODUCTION UNREVIEWED.
-- The existing EmpireDB owner must independently review existing schemas,
-- RLS, grants, key rotation, retention and expected request idempotency.
BEGIN;

CREATE TABLE IF NOT EXISTS public.prime_owner_nonce_guard_proposed (
  audience text NOT NULL,
  issuer_key_id text NOT NULL,
  tenant_scope_digest bytea NOT NULL CHECK (octet_length(tenant_scope_digest) = 32),
  nonce_digest bytea NOT NULL CHECK (octet_length(nonce_digest) = 32),
  source_event_digest bytea NOT NULL CHECK (octet_length(source_event_digest) = 32),
  inserted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (audience, issuer_key_id, tenant_scope_digest, nonce_digest),
  UNIQUE (audience, tenant_scope_digest, source_event_digest)
);

CREATE TABLE IF NOT EXISTS public.prime_forward_first_write_proposed (
  tenant_scope_digest bytea NOT NULL CHECK (octet_length(tenant_scope_digest) = 32),
  prediction_ref_digest bytea NOT NULL CHECK (octet_length(prediction_ref_digest) = 32),
  original_prediction_digest bytea NOT NULL CHECK (octet_length(original_prediction_digest) = 32),
  model_version_digest bytea NOT NULL CHECK (octet_length(model_version_digest) = 32),
  policy_version_digest bytea NOT NULL CHECK (octet_length(policy_version_digest) = 32),
  feature_lineage_digest bytea NOT NULL CHECK (octet_length(feature_lineage_digest) = 32),
  first_written_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (tenant_scope_digest, prediction_ref_digest)
);

-- Before an owner-approved release: FORCE RLS, deny all public/tenant DML,
-- allocate a dedicated function-security context, durable audit trail,
-- retention and irreversible unique-reservation design; none applied here.
ROLLBACK;
```

**One canonical transaction**, after signature verification and existing original canonical owner/rights/tenant/suppression checks, is required to reserve **every** nonce/event and write all the corresponding first-write immutable prediction rows. If any insert conflicts with the original unique indices, or any source/tenant/custody gate fails, abort the **whole** batch and return a non-identifying held response. Never `SELECT` then `INSERT` without a uniqueness constraint; never treat `INSERT ... ON CONFLICT DO NOTHING` as accepted until all expected rows were returned. No offline `set()`, local JSONL tail-only check, or cache TTL is a sufficient cross-process exactly-once authority.

Owner release review should decide the exact replay semantic: even genuine retries must not silently count twice. Raw nonce fingerprints and identifiers should not enter Founder outputs. The proposed unique event key intentionally blocks duplicate event acceptance; original owners must confirm its desired cross-key rotation semantics, scope, GDPR/retention limits and legitimate correction process. A nullable TTL row deletion could permit previously signed envelopes to replay later; retention or externally anchored revocation must close that hole. Avoid partial multi-row commit, service-triggered schema installation, or bypass of original EmpireDB RLS/security definer controls.

## Independent evidence required to move beyond HOLD

1. **Security / Original Data Cloud:** approve historical signing key/issuer provenance, tenant permissions, source licences, HMAC pseudonymisation, revocations, original buyer terms, and protected source readers.
2. **EmpireDB original owner:** approve reversible migrations and separate rollback, minimum grants and exact atomic insert/readback; verify transaction locks, unique index races, backup/PITR, audit, original 241 dirty production changes, staged test fixture / negative control; provision read-only private verification role.
3. **Original Predictive Cloud / Quant / Scientist:** review actual first-write timestamp after live signed producer starts; preregister horizon/model/policy, preserve abstain/negative/unknown; retain genuine losing economic outcomes, out-of-time holdout and base-rate control.
4. **Chief of Staff / ASTRA / Core:** reconcile and merge existing owner branches using original guarded release mechanism, original service config, rollback and authentication. No ASTRA SAFE_JOBS additions, no database changes, no true email reads, no outbound or trading activation from this research feature.

## Hard deployment barrier

Current code always returns `original_first_write_production_registry_authenticated=false`, `first_write_external_timestamp_anchor_verified=false`, `atomic_durable_nonce_replay_protection_verified=false`, `production_release_authorized=false`. It never writes the proposed tables.

**One original EmpireOS. One original EmpireDB. One Predictive Cloud / PRIME. All revenue and model-accuracy claims remain unverified pending genuine prospective evidence.**


## Verified scoped test evidence and handoff

- **397 tests passed**, one inherited Starlette deprecation warning, across the original PRIME/JEV-adjacent predictive bridge, first-write, forward-journal, signed-owner source, original calibration, Quant, Data Cloud source custody, Economic Signal Fabric, CRM signed auth, buyer evidence, tenant binding and Founder source review. This is **not** a whole-repository green assertion.
- The prior original-owner `tests/test_economic_signal_materializer.py` import of missing `ECONOMIC_SIGNAL_SOURCE_KEYS` remains outside this scoped regression suite; that materializer owner must reconcile it before broad release.
- No actual authorized owner key or source credentials were read, signed or written; the ephemeral Ed25519 keys and simulated canonical callbacks in this feature's tests are NOT production trusted proof.
- Owner release needs exact review of `empire_os/prime_first_write_attestation_preflight.py`, `empire_os/predictive_revenue_brain_bridge.py`, `tests/test_prime_first_write_attestation_preflight.py` and this proposal, then separate signing/first-write/nonce migration and operational release tickets under original Security, Data Cloud and EmpireDB owners.

**Current status: OFFLINE_SIGNED_FIRST_WRITE_READBACK_PREFLIGHT_PASS_RELEASE_HELD.** Real-world source trust and durable replay remain HOLD regardless of test outcomes.
