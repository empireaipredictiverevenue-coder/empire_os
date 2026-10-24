# Empire AI / Original EmpireOS: ASTRA Signed Notification Preflight

Date: 24 October 2026
Original research branch: `feature/prime-universal-evidence-fusion-20261024`
Status: OBSERVE-only research. No provider network integration, deployed webhook, real user/device binding, production DB migration, notification send, payment or model change.

## Exact original work continued

We continue **one original EmpireOS / PRIME / ASTRA / Digital Twin / Voice Lab / EmpireDB** flagship, not a separate assistant or Supabase service.

The original Cockpit and offline Kokoro/Whisper Voice Lab already proved a fictional spoken request for a two-second in-process timer that expired and produced one local-only receipt. The existing original timer worktree subsequently added:
- Held original EmpireDB 057 append-only tenant timer/event ledger.
- Held original EmpireDB 058 atomic claim, cancellation and server-side state-guard, validated in throwaway PostgreSQL with two competing sessions.
- Held original EmpireDB 059 callback metadata custody, with durable nonce/receipt uniqueness, exact original claim binding, accepted-before-delivered ordering, forced RLS and append-only safeguards. Passed 35 real PostgreSQL fixture assertions including a two-writer duplicate nonce race. **None is applied to production.**
- `prime_flagship_provider_reconciliation_shadow.py` validated fake HMAC signed callback order in memory. No external provider rights or device delivery were claimed.

The new gateway is **the next narrow gap**: verifying a signed provider callback *and* separately signed Identity/Privacy consent authority BEFORE any hypothetical callback may be considered for the protected original EmpireDB 059 custody ledger.

## Implemented in this milestone

### Original signed gateway research code

`empire_os/prime_flagship_notification_gateway_shadow.py`

Follows the pinned, domain-separated Ed25519 pattern used by the existing `empire_os/prime_signed_owner_evidence_gateway.py`. It uses original `empire_os.agi_capabilities.review_capability_request()` to explicitly keep live notification dispatch **not registered, not approved and not executable**.

It requires **two separate pinned public key registries** and refuses overlapping key IDs:
- A **synthetic notification-provider callback** with signed stage (ACCEPTED/DELIVERED/FAILED), provider identity, callback nonce, receipt digest, original tenant/timer/atomic-claim digest, delivery reference and device digest.
- A **synthetic signed Identity/Consent owner record** with original tenant/timer/claim/device binding, actor digest, consent evidence digest, explicit opt-in declaration, short issued/expires window and signed nonce.

The records use **separate signature domain prefixes and audiences**, strict allowlisted fields and digest formats, canonical UTC timestamps, a hard five-minute consent issuance window and prior-accepted callback requirement for synthetic DELIVERED status. An outer envelope cannot supply its own trusted key. The provider callback cannot impersonate the separate consent-owner key.

The gateway requires five **separately injected original-authority reader contracts**: current tenant/device scope, current actor/device consent, original timer claim readback, unseen callback nonce and prior acceptance (required for DELIVERED). A false/missing/throwing authority reader fails closed. Readers in this research are **test doubles**, not authenticated EmpireDB/Security production connectors.

Return values are exclusively non-executing. The gateway NEVER invokes a provider, queries production EmpireDB, reserves a nonce, sends an alert, writes customer data, creates a web server, issues credentials, schedules a timer or exposes raw phone, voice, person, device or contact details.

### Offline actual Ed25519 signature demonstration

`scripts/rehearse_prime_notification_gateway_20261024.py`

Generates **two separate ephemeral Ed25519 private keys in memory**, signs one fictional provider callback and one fictional Identity owner consent, verifies the signatures with pinned public keys and passes five synthetic owner-reader checks. The script prints only sanitized status flags, not private keys or raw user/device/token identifiers.

Observed command:

```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B scripts/rehearse_prime_notification_gateway_20261024.py
```

Observed status: `TWO_EPHEMERAL_ED25519_SIGNATURES_PASSED_LIVE_GATE_HELD`:
- Provider synthetic signature verified: true
- Identity/consent owner synthetic signature verified: true
- Mock authority checks passed: 5
- Real provider connected: false
- Consenting real user verified: false
- Production EmpireDB writes: false
- Real notifications sent: false
- Execution authority: none

### Existing Founder cockpit integration

- `empire_os/prime_digital_twin_cockpit.py` adds `original_notification_gateway=NOT_CONNECTED` to the existing GET-only Founder read model. It does **not** run cryptography on GET or turn a local demonstration into proof of a live provider.
- `apps/search-command-centre/src/lib/founder-api.ts` gets a typed response field.
- `apps/search-command-centre/src/app/founder/prime-digital-twin/page.tsx` displays provider/consent authority and explicitly says live webhook, real device delivery and owner credential provisioning are absent.
- `tests/test_prime_flagship_notification_gateway_shadow.py` adversarial checks include forged signatures, swapped tenant/timer/device/claim, separate issuer keys, invalid consent, expired/revoked proof, stale callbacks, replay-detected nonce, down authority reader, unsupported extra data, fake outbound/DB-success claims, original Founder API GET/POST separation and the one-shot offline demo.

## Crucial boundaries and next exact owner tasks

1. **Original Provider/Notification owner:** select and document ONE legitimate sandbox provider. Review its real signature scheme and actual accepted/delivered/device-receipt semantics (Ed25519 fixture scheme here is NOT a claim about that provider), issue authenticated sender and callback credentials under managed custody and test key rotation. No provider is selected or configured here.
2. **Original Identity/Privacy/Security owner:** implement separately authenticated consent/device-scope/revocation checks and current tenant membership. Synthetic `ACTIVE_EXPLICIT_TEST_OPT_IN` does NOT grant consent.
3. **Original EmpireDB owner:** review original 057/058/059 held migrations and actual canonical roles before approval. Build a separate safe restricted callback-custody transaction that atomically reserves 059 nonce and binds it to the claimed timer only AFTER genuine provider authentication. The current Python injected `callback_nonce_unseen` check is **not** an atomic reservation and cannot prevent two independent service workers racing without the held database.
4. **Original ASTRA and Voice owners:** after approvals, integrate a bounded delivery-attempt reconciler that never blindly resends an ambiguous claim. Capture source-authenticated provider receipts and real intended-device receipt status; no inference of human reading/listening solely from a provider delivered status.
5. **Original Founder/Security:** approve private ingress/auth/rollback and human browser/device acceptance before publishing this research page.

## Current truth

This increment demonstrates **cryptographic and authority-flow preflight logic** using independently generated fake keys and fixture authority checks. It **does not establish** a real connected provider, person, consent, actual device alert, production capability, verified payment, independent £250k appraisal or true machine consciousness.

One original EmpireOS. One canonical EmpireDB. One PRIME, ASTRA, Digital Twin and Voice Lab.


## Verified this increment

- **1,251 scoped original-system regression tests PASSED** on the research branch with one inherited Starlette/anyio deprecation warning. Includes original held PostgreSQL 057/058/059 disposable fixtures, speech/timer tests, provider reconciliation, PRIME/AGI, Founder API, original buyer/source/CRM/Quant evidence and the new signature gateway. Not a complete repository release gauntlet.
- Gateway/receipt/Founder focused tests: **87 passed** before adding one extra offline CLI regression. The added signed gateway test suite contains **47 checks**, including GET-only Founder behaviour and the manual two-ephemeral-key signature program.
- The original Search Command Centre `tsc --noEmit -p tsconfig.json` check **PASSED** with the new GET-only provider-signature status panel.
- One-shot original synthetic provider + consent-owner signing/review test **PASSED**. This verifies signature and binding logic with fake keys; owner-reader callbacks are mock trusted contracts, not actual connected production authority.
- **No live provider, consent proof, authentic device, endpoint, schedule, CRM or EmpireDB mutation or financial transaction.** Original 057–059 migrations remain unapplied to production.
