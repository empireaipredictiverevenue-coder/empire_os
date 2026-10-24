# Original PRIME / ASTRA — real reminder Identity-source integration audit

Date: 24 October 2026. Scope: original EmpireOS research branch `feature/prime-universal-evidence-fusion-20261024`; source-only, non-executing. No production Identity integration or approval has been obtained.

## Original code actually inspected

- `empire_os/hub.py` calls `app.include_router(create_consent_router())` without a repository argument. This original mount does not connect a canonical consent repository. The audit verifies the source-level contract, **not** the current running production process.
- `empire_os/consent_api.py` defaults its `ConsentRepository` to `None` and returns HTTP 503 for unbound prospect consent reads/updates. It manages **prospect ID and channel** consent; this is **not** actor-to-device reminder consent. A prospect voice opt-in cannot grant PRIME permission to notify a personal device.
- `empire_os/revenue_crm_signed_auth.py` has `crm:read` scope and pinned signed tenant JWT verification. It can establish limited CRM tenant read membership but does **not** authorise an individual device or notification.
- `migrations/empiredb/057*` through `061*` are held research migrations. Migration 061's default Identity-authority function returns `FALSE`, and the DB write trigger rejects all receipt insertions unless a distinct owner-approved replacement is supplied. No real Identity authority has been verified for such replacement.
- Existing fictional Ed25519 notification gateway tests, ephemeral PostgreSQL SCRAM identities and fabricated device consent demonstrate engineering behaviour only. They are not real provider or user consent evidence.

## Built this pass

- `empire_os/prime_original_notification_identity_source_audit.py`: bounded AST inspection of the existing original hub, consent and CRM auth contracts and held 061 default deny. A source change becomes `ORIGINAL_IDENTITY_CONTRACT_REVIEW_REQUIRED`, never an automatic production activation. The Founder projection strips source-specific/private fields and rejects attempts to insert a fake real-world activation state.
- `scripts/review_prime_notification_identity_sources_20261024.py`: repeatable read-only JSON operator audit, no server endpoint, credentials, DB connection or notification send.
- Original GET-only `prime_digital_twin_cockpit.py` and original Founder Console TypeScript/page surface a safe reminder Identity readiness label. Real reminder-device consent and provider state stay **unverified/unconnected**.
- `tests/test_prime_original_notification_identity_source_audit.py`: actual original source contract assertions, HTTP 503 fail-closed prospect consent route, mutated-code fail-closed case, forged Founder activation rejection and Founder GET/POST nonexecution.

Operator command:

```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B scripts/review_prime_notification_identity_sources_20261024.py
```

Observed result: `PROSPECT_CONSENT_ROUTER_UNBOUND_DEVICE_CONSENT_MISSING` and six outstanding owner/source gates. This does not imply real production API health is independently verified, since the audit reads source code only.

## Exact original owner release work

1. **Original Identity and Privacy owners:** identify or implement the genuine device registration and **user-specific opt-in, scoped to tenant, actor, destination device, channel and purpose**; obtain real authorised owner approval. Maintain an append-only revision and revocation semantics under the original Identity authority. `consent_api.py` prospect preferences alone are insufficient.
2. **Original Security owner:** approve the private signed identity issuer, signing keys, rotation and explicit actor/device claims. Prevent the caller from self-attesting or overriding the key registry; test suspension/revocation and device transfers.
3. **Original EmpireDB owner:** reconcile 057–061 with canonical production tables, privilege separation, tenant RLS, audit and rollback. Proposed DB authority must check **current genuine consent inside the same trusted transaction**; a fixture-owned `true` Boolean or metadata digest is never an approval. No application EXECUTE grant on held 060 in production.
4. **Original Notification owner:** choose one authorised sandbox provider, verify its actual callback signing protocol and the intended consenting test device; distinguish provider acceptance from transport/device receipt. No blind resend after ambiguous delivery.
5. **Original ASTRA/Founder/Voice owners:** exercise end-to-end consented user notification and cancellation using a deliberately limited staging channel and restore/rollback test. Keep original Founder status `NOT_CONNECTED` until independent owner evidence is present.

The real Identity/Privacy authority, provider sandbox credentials, genuine device and approvals remain absent. No production migration, real notification, financial action, autonomous worker or new parallel platform was created.

**One EmpireOS. One EmpireDB. One PRIME/ASTRA/Digital Twin/Voice Lab.**

## Verified research acceptance

- **1,285 scoped original-system tests passed**, including original PRIME, ASTRA, Voice Lab, Digital Twin, Founder API, consent API, CRM/source/Quant and actual disposable PostgreSQL 057–061 fixtures; one inherited Starlette/anyio deprecation warning. This is not a whole-repository release gauntlet.
- **14 focused new source-audit tests passed**, including a repeatable JSON operator command, modified-source fail-closed checks, canonical prospect 503 refusal, forged Founder activation refusal, and the original GET-only Founder API.
- Original Search Command Centre TypeScript `tsc --noEmit -p tsconfig.json` **passed** after the source-audit status field was added.
- No production source configuration was changed, no Identity owner key or permission was provisioned, no canonical EmpireDB write, and no real provider or device alert occurred. The audit reports repository-code evidence only; independent deployed-service and human owner verification remain required.
