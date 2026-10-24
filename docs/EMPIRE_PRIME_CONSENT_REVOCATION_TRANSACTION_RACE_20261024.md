# Original EmpireOS PRIME / ASTRA — Consent Revocation vs Callback Race

**Date:** 24 October 2026
**Branch:** `feature/prime-universal-evidence-fusion-20261024`
**Release status:** **ISOLATED RESEARCH / PRODUCTION HOLD** — no real provider, real consent authority, production EmpireDB migration, outbound notification, or money movement.

## Same original flagship, next precise gap

We continue the **same** original PRIME/ASTRA/Voice Lab timer notification path, never a separate platform or Supabase. Prior held original EmpireDB migrations 057–060, Ed25519 synthetic signed gateway and two separate SCRAM-authenticated fixture reader/writer logins were already tested in PostgreSQL 18. The signed reader can see metadata for only its fictional tenant, and the writer can call the single held 060 custody function with no direct table INSERT rights.

The remaining research question: **what if consent is revoked concurrently with a provider callback?** Do the consent read lock and revocation UPDATE serialize, or could a stale consent observation allow a fixture callback to be recorded after the revocation transaction wins?

## Work implemented and executed

Added `scripts/rehearse_prime_consent_revocation_race_20261024.py`, called by the existing `scripts/rehearse_prime_signed_gateway_pg_fixture_20261024.sh` after its signed fictitious callback and cross-tenant checks.

The new fixture creates two independent fictional timers with genuine original 058 atomic claims, in the **disposable** PostgreSQL `empire_timer_fixture` database. It uses the existing **SCRAM reader login** and fixture-only `fixture_lock_current_test_consent` function; the callback-only fixture **SCRAM writer login** retains no direct 059 table rights. A fixture admin is used **only** for isolated setup, active-consent change and readback/lock observation. No real Identity provider is contacted.

A PostgreSQL 18 `pg_stat_activity.wait_event_type = 'Lock'` probe makes the two critical orderings observable rather than inferring that a race occurred from sleep timing:

1. **Revocation acquires its UPDATE lock first.** The independent consent reader then blocks on the consent row lock. After the revocation commits, the reader sees `active=false` and refuses approval. **No callback writer invocation / no receipt row** in that case.
2. **Consent reader acquires its lock first.** The fictional revocation attempts an UPDATE and is observed blocked on that same consent row. The separately authenticated, function-only writer records **one** ACCEPTED metadata event while the earlier read transaction remains open. The reader commits, the waiting revocation completes, and a fresh read observes `active=false`. The existing earlier receipt remains immutable; no additional write is authorised by the read path.

Observed CLI status: `TWO_REAL_POSTGRESQL_REVOCATION_ORDERINGS_PASS` with both lock waits confirmed; no real provider network use or real device alert. The experiment is chained to the original 057–060 PostgreSQL fixture, which still refuses port 5432 and any non-temporary server data directory and drops the test cluster afterward.

New `tests/test_prime_consent_revocation_race_20261024.py` tests unsafe-target refusal and confirms the race script only uses the two separate identities and bounded locking/test database. The existing signed gateway/060 integration test now asserts the actual transaction-race status and absence of device alerts from a real fixture run.

**57 focused tests passed**, with one inherited Starlette/anyio deprecation warning. The tests exercise PostgreSQL behaviour, not real-world permission.

## Important finding: full production activation remains unsafe

**This is an isolated fixture consent-lock demonstration, not an actual live permission gate.** The held 060 SQL custody writer **does not independently query an authenticated production consent service**. A caller granted unchecked `EXECUTE` on 060 could bypass an external consent preflight, even though it cannot bypass the original 059 event ordering and nonce constraints. The test-only Identity table, fixed tenant RLS, SECURITY DEFINER consent lock and artificial signer are NOT production authority.

The “callback-first” case demonstrates ordering, **not that a user's real revocation was ignored or a real alert sent**. For real users, revocation timing, multiple devices, identity attestation, transaction coupling and lifetime cancellation must be independently specified and signed off by original Identity/Privacy/Security owners. A delivery callback's metadata still does not prove a real human or even an intended device received it.

## Next original owner boundary, no drift

1. **Original Identity/Privacy + EmpireDB/Security:** define a genuinely authenticated, revocable actor/device/tenant consent authority, with a safe DB-attested transaction boundary. No production grant of 060 EXECUTE until valid consent and claim authority can be enforced at the same trusted write boundary.
2. **Original ASTRA:** bind that authority to all callback and cancellation transitions, enforce a no-blind-retry policy for ambiguous provider outcomes, and audit access.
3. **Original Notification:** provision one approved provider sandbox and its genuine signature protocol/credential custody; prove accepted vs delivered semantics to a consenting test device separately.
4. **Original Founder/Voice:** keep the original private dashboard `NOT_CONNECTED` until the complete user-facing chain is independently demonstrated.

**One original EmpireOS. One original EmpireDB. One PRIME / ASTRA / Digital Twin / Voice Lab.**

## Final regression and isolation verification

- **57 focused adversarial tests passed**, including unsafe main-port refusal, the actual disposable PostgreSQL 18 fixture, two observed lock waits, separate SCRAM reader/writer, tenant/consent proof and the original signed notification gateway. One inherited Starlette/anyio deprecation warning remains.
- **1,261 scoped original-system regression tests passed**, including the original PRIME, ASTRA, Digital Twin, Voice Lab, AGI, Founder API, source/CRM/Quant and held EmpireDB migration 057–060 fixtures. This is not the entire repository gauntlet and does not represent original-owner production approval.
- The second phase's `ACCEPTED` callback is a **synthetic SQL metadata custody test through the restricted writer**, not a newly signed real provider notification. It demonstrates PostgreSQL ordering only.
- The temporary database, two fixture logins, callback rows, fake identity and test passwords were destroyed by `pg_virtualenv`; canonical PostgreSQL port 5432 was not contacted by the fixture for writes.
