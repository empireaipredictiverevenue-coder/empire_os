# Original EmpireOS PRIME / ASTRA — Signed Callback to EmpireDB 059

Date: 24 October 2026
Location: isolated original `feature/prime-universal-evidence-fusion-20261024` research worktree.
Release: **RESEARCH FIXTURE ONLY. NO PRODUCTION ACTIVATION.**

## Why this is an incremental flagship build, not a new service

Earlier verified original components:
- Original Voice Lab Kokoro/Whisper processed fictional audio, started and expired one in-process two-second timer, and issued a local-only expiry receipt.
- Held original EmpireDB migrations 057 (append-only timer ledger), 058 (atomic claim/cancel with protected event transitions) and 059 (provider callback receipt custody) were separately exercised in disposable PostgreSQL 18.
- Original PRIME/ASTRA `prime_flagship_notification_gateway_shadow.py` verified *two independently signed, fictional Ed25519 authorities* (provider + Identity/Consent owner) against a set of supplied scope/consent/claim/replay-reader contracts. It deliberately did not write any database record.
- Original Founder private cockpit reports NOT_CONNECTED for the gateway and notification provider.

**This milestone tests the connection**: can signed gateway verification, independently rechecked fixture consent, original timer-claim verification and migration 059 custody work together in real PostgreSQL transactions, with bad inputs leaving the ledger unchanged?

## Added

- `scripts/rehearse_prime_signed_gateway_db_receipt_20261024.py`: one-shot, synthetic-only bridge exercise using native `psycopg`, ephemeral Ed25519 keys and the existing original signed notification gateway module. It connects only to a disposable `empire_timer_fixture` PostgreSQL database with port 5433+ and server-verified `/tmp/pg_virtualenv.*/data/18/regress`. It refuses normal PostgreSQL port 5432 **before connecting**.
- `scripts/rehearse_prime_signed_gateway_pg_fixture_20261024.sh`: outside-only wrapper with independent PostgreSQL temporary-data-directory check, creation of disposable database, original held migrations 057–059, then execution of the signed gateway bridge. No production schema, runtime login, provider account or send transport is installed.
- `tests/test_prime_signed_gateway_db_bridge_fixture_20261024.py`: repeatable PostgreSQL-backed integration regression, explicit refusal of main port 5432, source-and-signature invariants, and examination of the sanitized output.

## Actual observed acceptance flow

Ran:

```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024
pg_virtualenv -t bash scripts/rehearse_prime_signed_gateway_pg_fixture_20261024.sh
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m pytest -q tests/test_prime_signed_gateway_db_bridge_fixture_20261024.py \
  tests/test_prime_flagship_notification_gateway_shadow.py
```

The actual disposable PostgreSQL bridge **PASSED** with status `SIGNED_SYNTHETIC_CALLBACKS_PERSISTED_IN_TEMP_POSTGRES`. The bridge returned six independently exercised checks:

1. A first **signed ACCEPTED** fictional provider callback, with a separately signed fictional consent owner and a real original 058 claim row, was admitted and stored in PostgreSQL 059.
2. New database connections could not replay that same signed callback nonce; the ledger row count remained one.
3. A forged provider signature was refused before insert; the ledger row count remained one.
4. A signed but explicitly REVOKED fictional owner declaration was refused before insert.
5. A separate real SQL UPDATE revoked the fictional test-device consent. The next signed callback was denied by the current fixture authority readers, leaving the ledger unchanged.
6. After explicitly restoring the fictional test-consent row, a correctly signed DELIVERED-*REPORTED* callback was admitted as sequence two, preceded by ACCEPTED. The final PostgreSQL ledger held exactly **two valid fixture receipts**.

**51 gateway + integrated fixture focused tests PASSED**, with one inherited Starlette/anyio deprecation warning.

All submitted PostgreSQL metadata is derived **directly from the cryptographically verified provider envelope payload**, not an independent input dictionary. The fixture rechecks the fictional consent record under a PostgreSQL `FOR SHARE` row lock **in the same insert transaction** to reduce check/insert races for this synthetic on-DB identity model. The original 059 INSERT trigger and unique indexes enforce nonce replay and event order atomically regardless of this preliminary reader.

## Important authority limits

- Every key, user, device, consent, tenant and provider callback in this test is **fictional**. The consent table `fixture_authorised_device` exists only in the disposable PostgreSQL fixture; it is NOT original production Identity authority.
- The bridge uses a disposable fixture database connection with owner/superuser permissions so the held 057/058/059 code can be tested; it does **not** provision a safe runtime role, prove a real original Identity service, or establish production access authority.
- The previous original gateway `scope_current`, `consent_current`, `claim_current`, `callback_nonce_unseen` and `prior_provider_acceptance` are now exercised with **actual SQL reads against a fictional local fixture**, not the production original EmpireDB.
- A successful receipt INSERT means **synthetic metadata custody in an ephemeral PostgreSQL database**, not a real provider acknowledgement, authenticated user consent, mobile delivery, device visibility, spoken alert or human listening.
- The injected test Ed25519 callback format is not asserted to match Apple, Google, ntfy, APNs, FCM, a web push provider or any actual vendor. A provider-specific signature verifier and approved sandbox credentials are still absent.
- The PostgreSQL fixture is destroyed by `pg_virtualenv` at process exit. Production EmpireDB migrations 057–059 remain **HELD and unapplied**.
- No new assistant, database, webhook, live sender, cron, phone, customer notification, model inference, paid deal or verified revenue exists as a result of this integration.

## Next original owner work

1. Original Notification + Security owner selects and approves a permitted **single real sandbox provider** and its authentic signed webhook protocol, approved key custody, tenant/account rights and callback semantics.
2. Original Identity/Privacy owner connects an authenticated, revocable user/device consent authority and retention/purpose framework. A fixture-owned boolean cannot be used as real consent.
3. Original EmpireDB + ASTRA owner reviews 057–059 against canonical production roles and migration procedures, and designs a strictly privilege-limited **atomic callback custody writer**. There must be no direct app INSERT permission, unrestricted SECURITY DEFINER or unverified source signature.
4. Original ASTRA owner implements a reconciliation-only dispatcher for ambiguous provider acknowledgements; an accepted or delivered-reported provider callback still needs independently verified device receipt semantics. No blind duplicate send.
5. Original Founder/Security owner approves private browser/consented-device acceptance only after those gates. The existing read-only Founder cockpit must stay NOT_CONNECTED until an authorised live source is available.

**One original EmpireOS. One original EmpireDB PostgreSQL. One PRIME, ASTRA, Digital Twin and Voice Lab.**


## Verified affected-system acceptance

- **1,255 scoped original-system regressions passed**, including the added signed gateway→DB 059 fixture, original migrations 057/058/059, two-worker claim/receipt race tests, ASTRA signed preflight, PRIME/Voice Lab, Digital Twin, Founder and original source/CRM/Quant checks. One inherited Starlette/anyio deprecation warning remains. This is not the complete repository gauntlet or a signed release.
- **51 focused signed gateway/bridge tests passed**, including a real disposable PostgreSQL launch, signatures, consent revocation and replay rejection, before the wider affected-system suite.
- The two accepted PostgreSQL records represent **synthetic provider ACCEPTED and DELIVERED-REPORTED stages**; they are not a real user notification or independently attested device-delivery proof. The test uses a PostgreSQL fixture superuser, never a production app role.
- No real sender, real provider sandbox, production EmpireDB 057–059 migration, original Smart CRM, real microphone, person or payments were involved. The throwaway PostgreSQL cluster is automatically dropped.
