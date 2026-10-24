# EmpireOS / PRIME Flagship — Original EmpireDB Timer Ledger & Restart Recovery

Date: 24 October 2026
Repository branch: feature/prime-universal-evidence-fusion-20261024
State: OWNER REVIEW ONLY / SYNTHETIC REPLAY. No production DB deployment, owner authorisation or real reminder delivery.

## Why this is the next original flagship milestone

The previous milestone proved **actual local Kokoro speech → Whisper speech recognition → timer intent → in-process two-second timer expiry → one local sink receipt**, with zero duplicate expiration. That timer is **not durable**: it vanishes when the process exits, and no real user device received a notification. The next missing boundary is the ORIGINAL EmpireDB durable clock, cancellation and provider-receipt authority. We have not repurposed the separate legacy lead appointment scheduling agent or external alerting sender, nor created a second database.

## Built, testable code

1. `empire_os/prime_flagship_timer_recovery_shadow.py` — a pure *reconstruction* state machine for a proposed original tenant-bound immutable EmpireDB timer ledger. It accepts strictly sequential, synthetic-only metadata events. No raw transcript, message body, address, phone, device name, notification content or credential. Every event has opaque digest, UUID tenant, timer digest, sequence, event type and timezone-aware timestamp. The CREATE event binds a 1–3600-second due deadline; later events cannot mutate that schedule.
2. `migrations/empiredb/057_flagship_voice_timer_ledger_held.sql` — **PREPARED DDL ONLY, NEVER APPLIED**. Two original EmpireDB PostgreSQL metadata tables (`empire_prime_voice_timer_requests` and `empire_prime_voice_timer_events`) with scoped tenant composite keys, replay uniqueness, FK integrity, append-only trigger, role/DB preflight checks, FORCE row-level security, no policies, no LOGIN and no app/writer/reader grant. Digests are reference fields, NOT verifiable user consent or original-owner signatures in this migration. A production Atomic CLAIM RPC/worker is deliberately absent.
3. `scripts/rehearse_prime_original_timer_recovery_20261024.py` — four separate fresh Python child-process replays from fictional JSON event rows delivered only through standard input. No disk database, customer source, outbound or clock daemon. Tests an independent fresh process recovering the same hypothetical state rather than trusting an in-memory object.
4. `tests/test_prime_flagship_timer_recovery_shadow.py` — interruption, cancellation, early/duplicate claim, replay, cross-tenant binding, provider accept/deliver, timestamp impossible cases, restricted immutable DDL static contract and Founder projection safety.
5. Existing original `empire_os/prime_digital_twin_cockpit.py`, Founder `/v1/founder-dashboard/prime-digital-twin` GET and original Search Command Centre cockpit page now expose **original_timer_recovery = NOT_CONNECTED**. The read model never connects to DB, writes a timer, calls the LLM or displays a real notification as delivered.

## State machine: what is and is not permitted

| Proposed ledger state | Safe recovery decision |
|---|---|
| SCHEDULED_WAITING | Wait until due; no notification |
| DUE_UNCLAIMED_REQUIRES_ATOMIC_DB_CLAIM | Require approved atomic DB claim; not permission to send |
| CANCELLED_BEFORE_DISPATCH | Never notify |
| CLAIMED_RECONCILIATION_REQUIRED | Stop and reconcile with provider before retry |
| PROVIDER_ACCEPTED_NOT_DELIVERED | Do not call provider acceptance a delivery |
| DELIVERY_REPORTED_NOT_INDEPENDENTLY_VERIFIED | Independent original provider receipt/custody verification required |
| DELIVERY_FAILED_REPORTED_NO_AUTO_RETRY | Manual review; no blind replay |

Replay cannot reuse an event nonce, skip a sequence, change tenant/timer scope, move a due date, cancel a claimed/expired timer, dispatch before due, create acceptance before claim or infer a delivered alert from customer silence. Synthetic "delivered" claims are *reported*, **never verified real delivery**. The Founder projection strips tenant/timer/event identifiers and cannot grant execution authority.

## Actual synthetic fresh-process proof

Ran:
```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  scripts/rehearse_prime_original_timer_recovery_20261024.py
```
Observed **FOUR_FICTIONAL_RESTART_CONTRACTS_PASS** with four fresh processes and these statuses:
- `cancelled` → `CANCELLED_BEFORE_DISPATCH`
- `claimed_crash` → `CLAIMED_RECONCILIATION_REQUIRED`
- `provider_accepted` → `PROVIDER_ACCEPTED_NOT_DELIVERED`
- `provider_reported_delivered` → `DELIVERY_REPORTED_NOT_INDEPENDENTLY_VERIFIED`

This uses ephemeral fictional event JSON through stdin and an independently launched Python interpreter. **It does not persist to EmpireDB or prove genuine crash recovery of PostgreSQL, transactional exactly-once provider delivery, user notification, source attestation, real tenant identity or permission.**

## Next original-owner work, not a separate platform

- **EmpireDB/Security owner:** independently approve 057 DDL before any migration; run disposable DBA fixture validation, RLS/cross-tenant isolation, append-only, replay and rollback gauntlet; reconcile actual current original schema/roles and real privacy purpose. No other agent may assume this permission.
- **Identity/Voice owner:** attest genuine opt-in user/device binding, microphone rights, source custody, tenant authority, cancellation and deletion; integrate original Voice Lab without the deprecated/noncanonical Supabase voice gateway.
- **ASTRA/Scheduler owner:** add a single authorised atomic claim transaction with proper lease/reconciliation and bounded delivery rate. A PostgreSQL INSERT or lock alone does not prove exactly-once external side effects. A claimed-but-unacknowledged dispatch must not be blindly resent.
- **Notification owner:** approved device channel; independent provider acceptance vs actual device delivery receipt; attempts, expiry and consent revocation. No inference from successful TTS or synthetic speech that a person heard it.
- **Founder/Private Console owner:** review real authentication, owner ingress and UI acceptance. The current prototype must remain marked **NOT_CONNECTED** rather than suggesting delivery.
- **Model owner:** resolve prior bounded llama.cpp inference timeout separately. The actual 2-second original local speech-to-timer proof did not depend on it.

## Release and commercial truth

No migration was applied, no real scheduler or alert installed, no customer notification was sent, no personal data used, no original DB or Smart CRM modified, no funds moved and no live revenue earned. This artifact is not evidence supporting a £250k independent market value by itself. The design advances one measurable capability without the endless script-only loop.

One original EmpireOS. One original EmpireDB. One PRIME. One ASTRA. One Digital Twin and Voice Lab.


## Observed validation and release boundary

- **1,168 scoped original Voice Lab, PRIME, Digital Twin, AGI, Founder API, source/CRM and Quant regressions passed** in the research worktree, with one inherited Starlette/anyio deprecation warning. This is not a full-repository gauntlet or a production release review.
- The original Founder Console Next.js TypeScript `tsc --noEmit -p tsconfig.json` **passed**. The private cockpit has a timer recovery status panel but no scheduling POST endpoint, no database reader and no actual user-facing delivery.
- The new cross-process synthetic replay CLI executed successfully: **four fresh child processes, four expected recovery dispositions, zero observed real notification delivery, zero DB writes**.
- `migrations/empiredb/057_flagship_voice_timer_ledger_held.sql` has static assertions for database/role guard, FORCE RLS, replay constraints, append-only trigger, no policy or runtime GRANT. **The SQL has not been parsed/executed against a real PostgreSQL fixture, and no database migration was applied.** DBA acceptance still requires an isolated actual PostgreSQL fixture migration, transactionally atomic claim verification, RLS cross-tenant role simulations, constraint/trigger tests, rollback evidence, approved identity/consent design and signed owner proof.
- Production/current canonical original EmpireOS checkout was observed but not modified by this build. Research GitHub branch commit and remote hash are separately verified after source control actions.
