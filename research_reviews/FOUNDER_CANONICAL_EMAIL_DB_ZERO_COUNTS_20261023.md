# Founder historical Gmail to EmpireDB — read-only, incomplete reconciliation

Date: 23 October 2026. The original nine-contact founder-acquisition ledger is the only candidate set. No new sender, campaign, database role, table, worker, timer or CRM intake was created.

## Direct evidence
The founder executed a read-only PostgreSQL transaction using the original root-owned EMPIRE_OUTBOUND_SENDER_DSN and SET LOCAL ROLE empire_outbound_sender. Authentication, current_user restricted role, transaction_read_only and SELECT privileges for public.outbound_suppressions and public.outbound_intents were reported verified.

For all nine historical Gmail SENT recipients (Plena Health, Alloovium, Libra Robotics, Acolite, Qlo, Propaya, Andco, LunaBill and ProhostAI):
- Exact-address, domain and @domain suppression matches VISIBLE UNDER THAT ROLE: 0 for each
- Canonical email outbound intents VISIBLE UNDER THAT ROLE: 0 for each
- New emails and database writes: 0

These observations were obtained from the user's own server terminal output. The audit was not a proof of PostgreSQL row-level security policy visibility, other mailbox suppression systems, recipient consent, person binding, customer interest or sender authorisation. Zero recorded intents is consistent with known direct Gmail sends having no canonical outbound-governor intent; never issue retroactive approval.

## Narrow owner-only follow-up
Read-only script scripts/audit_founder_email_db_visibility_20261023.py verifies the current restricted sender identity, table SELECT rights and RLS policy full visibility before repeating the original nine company-level counts. A restrictive, conditional, absent or unprovable policy yields HELD without even attempting recipient counts.

The script uses only the existing root-protected outbound.env and existing original founder ledger, and emits neither private email addresses nor secrets. It never calls an outbound sender, never writes DB data, never sends mail and never activates a service.

Even on full visible-count success, the report remains historical_email_clearance NOT_VERIFIED and new_send_authorized false. Any further contact or customer-facing commitments must pass a fresh, prospective, exact bound-intent policy review and the original compliance owners.
