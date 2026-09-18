# Agent Lane: Revenue / Payments
Branch: agent/revenue-payments
Worktree: /home/ubuntu/empire_agents/revenue-payments

Mission: harden verified USDT-on-BSC payment and Phase 3F revenue truth.

Own: BSC verification, payment evidence, escrow/release, revenue recognition tests, finance integrity.
Do not own: Astra decision policy, general outbound, SaaS UI.

Invariants:
- Canonical rail is USDT on BSC.
- Actual revenue requires independently verifiable buyer/payment evidence.
- No replay, mock settlement, synthetic revenue or manual revenue assertions.
- No mainnet action, fund movement or production credential changes.
- Do not apply production migrations.
- Do not touch /srv/empire_os/recovery or /srv/empire_os/toop.

Deliver: hardening + regression tests + docs. Stop before consequential production actions.
