# EmpireOS AI Receptionist / Missed Revenue: existing system map

## Canonical checkout and owner
- Preferred active branch (check git first): `feature/inbound-revenue-recovery-20261020`, worktree `/home/ubuntu/empire_worktrees/inbound_revenue_recovery_20261020`.
- Other worktrees can be older and are not deployment truth: `/home/ubuntu/empire_worktrees/inbound_recovery_integration_20261020`, `/home/ubuntu/empire_worktrees/inbound_ai_department_handoff_20261017`.
- Production shared checkout `/srv/empire_os`: observe/read. No opportunistic code edits, merges or restarts.
- Original owner docs: `docs/commercial/INBOUND_REVENUE_RECOVERY_OWNER_BUILD_20261020.md`, `docs/commercial/EMPIRE_AI_RECEPTIONIST_SIGNED_CALL_CONTROLLER_20261020.md`.
- Existing GitHub coordination: `empireaipredictiverevenue-coder/empire_os`, issue 71 (multi-topic historical status; do not substitute for current receipts).

## Product flow: avoid double-counting

| Stage | Existing owner implementation | What counts as evidence |
|---|---|---|
| DID to tenant | `inbound_provider_contract.py` | Registered DID plus independent ownership check |
| Signed Voice callback | `inbound_signature_verification.py`, `inbound_reception_voice_api.py` | Valid signed webhook and integrity hash; offline tests are not live telephony |
| Answer / listen / consent | `inbound_reception_call_flow.py`, `inbound_reception_intake.py` | Bounded spoken/scripted response and explicit contact permission |
| Customer service/hours | `inbound_tenant_knowledge.py`, `inbound_business_hours.py` | Reviewed approved facts and verified staffed schedule |
| Enquiry for review | `CRMEnquiryDraft` in `inbound_reception_intake.py` | In-memory synthetic draft only until verified CRM owner receipt |
| Provider terminal missed call | `inbound_provider_contract.py`, `inbound_recovery_store.py` | Signed and durable provider outcome in real trusted source |
| Missed opportunity | `inbound_opportunity_intelligence.py` | Trusted unanswered/busy/rejected event not yet verified recovered/suppressed |
| Consent and appointment workflow | `inbound_booking_workflow.py`, `inbound_booking_store.py` | Immutable order of verified real provider/calendar/consent evidence |
| Calendar booking | `inbound_google_calendar_adapter.py`, `inbound_google_calendar_completion.py` | Authorised owner-linked provider readback and confirmed un-cancelled appointment |
| Recovered call | `inbound_revenue_recovery.py` / `RecoveryLedger.report` | Verified callback connection / calendar booking after missed event, same canonical call |
| Money, sources, scorecard | `inbound_source_attribution.py`, `inbound_recovery_scorecard.py` | Genuine paid receipt after verified recovered event, separately sourced advertising attribution |

## Installed/runtime truth that must be revalidated
- The separately deployed `empire-inbound-recovery-staging.service` is *private Calendar staging* on localhost `127.0.0.1:8794`, not a deployed voice answering system.
- New signed receptionist API is isolated and default-disabled; it is not attached to real Vonage numbers and relies on in-process replay/session state.
- Current `CRMEnquiryDraft` has no real caller contact identity and does **not** write to `public.empire_crm_tenant_memberships`, canonical prospects, or payment sources.
- Version 057 native PostgreSQL RLS migration is held/unapplied in the last checked state. Do not infer schema activation from source existence. Only production DBA can authorise/verify a migration.
- No first-party paid recovery is proven by the current synthetic demo or feature tests.

## Fast self-checks
```bash
cd /home/ubuntu/empire_worktrees/inbound_revenue_recovery_20261020
git status --short --branch
git log -3 --oneline
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.demo_ai_receptionist_call_20261020 --synthetic-only appointment
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q tests/test_inbound_*.py tests/test_voice_gateway_api.py
systemctl show empire-inbound-recovery-staging.service -p ActiveState -p SubState --no-pager
```

No `sudo`, customer phone call, DB DDL or live network execution is part of these checks.
