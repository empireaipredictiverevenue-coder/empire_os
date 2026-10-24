# Empire AI / Original PRIME — held device-bound reminder consent (062)

**Date:** 24 October 2026
**Original research branch:** `feature/prime-universal-evidence-fusion-20261024`
**Release:** HELD / isolated original EmpireDB PostgreSQL 18 fixture only. Not an owner-approved Identity connector, production migration or notification service.

## Same original flagship, concrete gap closed

Prior original 057–061 work provided a tenant/actor-bound timer, atomic claim/cancel, immutable provider-reported callback receipts, separate scoped SCRAM fixture reader/writer, and a DB-side 061 consent function that **intentionally returns FALSE** without a trusted Identity/Privacy authority.

The original 057 request had actor/source/consent digests but lacked a **destination device binding**. The inspected canonical prospect-consent API (`empire_os/consent_api.py`) remains **unbound in the original hub** and is prospect/channel-scoped, not verified person/device reminder consent. Original CRM `crm:read` scope is not device consent. No authentic current person/device consent source or provider sandbox has been verified or approved.

**This increment designs and exercises the missing device-bound consent data contract without activating production authority or weakening 061.**

## Held migration 062

`migrations/empiredb/062_flagship_device_binding_consent_events_held.sql`

The migration requires original canonical EmpireDB/predecessor 057–061 objects, the restricted NOLOGIN migration owner, FORCE RLS on predecessors, correct database and absence of prior installed objects. It creates:

1. **`public.empire_prime_reminder_devices_held`**: proposed opaque tenant/actor/device and attestation digests. A row is **not** evidence of real device ownership/registration.
2. **`public.empire_prime_reminder_timer_devices_held`**: one destination device per tenant/timer, bound by composite foreign keys to that same tenant's actor/device enrolment and the original 057 request. A database insert trigger locks the original timer row and validates identical actor, source attestation and consent evidence. A different device cannot be silently substituted for the same timer.
3. **`public.empire_prime_reminder_consent_events_held`**: append-only, purpose/channel-specific GRANTED and REVOKED metadata with ordered event sequence, source and evidence digests. A trigger locks the same enrolment row used by the fixture callback consent reader. It rejects revocation before the first grant, duplicate decisions, sequence gaps, future/stale timestamps and duplicate event digests.

All three tables use **FORCE ROW LEVEL SECURITY**; only the existing original restricted **NOLOGIN migration-owner policy** is prepared. No app/runtime LOGIN, INSERT, SELECT, EXECUTE or public rights are granted. UPDATE/DELETE are denied by the original 057 append-only trigger. No raw name, email, phone, payload, audio, location, token or provider secret is stored.

**Crucially, migration 062 does not modify the 061 consent authority function. Its deny-by-default behaviour remains in force.** Digest fields are metadata, not a cryptographic user attestation.

## Executed real, disposable PostgreSQL verification

- `scripts/rehearse_prime_device_binding_062_20261024.sh`: runs only with the explicit **`EMPIRE_REHEARSE_HELD_DEVICE_062=disposable_only`** and prior `EMPIRE_REHEARSE_HELD_CONSENT_061=disposable_only`, after the original existing 057–061 fixture checks. Both scripts refuse port 5432 or an unexpected PostgreSQL data directory and run in `pg_virtualenv -t` temporary PostgreSQL 18.
- `tests/test_prime_timer_device_binding_062_20261024.py`: automated static role/grant checks, opt-in and unsafe-target refusal, and actual PostgreSQL fixture acceptance.

### Positive/negative SQL acceptance observations

- Wrong database and repeat application **refused**.
- Forced RLS, three owner-only policies, no public function EXECUTE.
- Mismatched original timer actor/source/consent evidence **refused**.
- Attempt to rebind one timer to a different enrolment **refused**.
- First consent event must be GRANTED, exact incremented sequence required, duplicate decision or event sequence gaps **refused**.
- UPDATE to recorded consent event **refused**; append-only preserved.
- Even with recorded fictional device grant, **061 still denied** the original callback writer before any verified Identity authority. This proves **no automatic consent promotion**.
- A **disposable-fixture-only** owner adapter then reads the new device/consent tables, checks test tenant and test SCRAM writer `session_user`, locks the enrolled device under `FOR SHARE` and requires latest consent event be GRANTED with exactly matching evidence. That is a simulated trusted boundary, **not approved production Identity authority**.
- The fixture's active fictional consent admitted one synthetically signed-off metadata callback; revocation for the **bound** device denied the next metadata write even while the other fictional device had its own active grant.
- An explicit separate append-only regrant admitted only an otherwise legally ordered fictional DELIVERED-REPORTED receipt.
- In **two real PostgreSQL sessions**, an append-only REVOKED event got the enrolment lock first; the separately authenticated restricted writer then waited, observed revoked consent and was denied. **Zero** callback rows were created for the raced timer.
- All temporary PostgreSQL roles, fixture data and secrets were deleted on cluster destruction. Canonical EmpireDB 5432 was not migrated.

Manual command:

```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024
EMPIRE_REHEARSE_HELD_CONSENT_061=disposable_only \
EMPIRE_REHEARSE_HELD_DEVICE_062=disposable_only \
pg_virtualenv -t bash scripts/rehearse_prime_signed_gateway_pg_fixture_20261024.sh
```

The receipt acceptance in this test is **only fictional provider-reported metadata**, not an independently authenticated real callback, destination delivery or human acknowledgement. A generic permitted metadata INSERT remains **unsafe** until the actual original Identity/Privacy owners have signed off live actor-device enrolment and the true source of consent.

## Exact remaining original owner release gates

1. **Identity/Privacy owner:** identify or create genuine original tenant-actor-device registration and explicit purpose/channel consent with tamper-proof source, real device attestation, lawful basis, renewal, revocation, retention and user control. The 062 tables are a candidate, not user identity authority.
2. **Security owner:** independently verify signing/credential ownership, authorised device/account enrolment, suspended identities, actor transfer, revocation precedence, key rotation and retention rights. Never equate a caller-supplied 64-hex value with attestation.
3. **EmpireDB owner:** review 057–062 SQL, restrictive role and RLS, SQL definer/triggers, append-only events, migrations, backups and rollback, and a real authenticated atomic 061 consent decision; **no production 060 EXECUTE grant** and 061 remains deny-all.
4. **Notification owner:** authorise ONE real sandbox, genuine provider-specific signed callback verification, expected device receipt semantics, delivery retention and no blind retry.
5. **ASTRA/Founder/Voice:** after independent authorisations, verify a real explicitly consenting test device, its acknowledgement and cancellation using an isolated private route. Until then original Founder should continue displaying NOT_CONNECTED.

**One original EmpireOS. One canonical EmpireDB PostgreSQL. One PRIME, ASTRA, Digital Twin and Voice Lab. No production sends, money or claimed live approvals.**

## Final executed acceptance

- **1,289 scoped original-system regression tests passed**, including the initial new 062 fixture, prior 057–061 disposable PostgreSQL fixtures, original Voice Lab, ASTRA, PRIME, Digital Twin, Founder, CRM and source contracts. One inherited Starlette/anyio deprecation warning remains. This is not the whole-repository release gauntlet.
- Following the broader run, the 062 fixture was extended with an explicit **second enrolled actor**. Its attempt to bind its enrolled device to the first actor's already-created timer was **rejected by PostgreSQL's original timer/actor binding guard**. The restricted writer and independent reader also lacked direct 062 table privileges. **4/4 updated focused 062 tests passed** in a fresh disposable PostgreSQL cluster.
- Original 061 continues to **DENY callback custody by default**, even after new device and consent rows are present. The only test that permits metadata receipts explicitly replaces that placeholder with a **temporary, fictional, fixed-tenant adapter** inside the disposable cluster and never grants application or production authority.
- No production EmpireDB 5432 migration, actual Identity/Privacy approval, authentic registered device, provider webhook, real notification, customer data or payment was created. The temporary PostgreSQL instance, fixture credentials and all fictional metadata were deleted.
