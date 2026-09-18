# Agent Lane: Infra / QA
Branch: agent/infra-qa
Worktree: /home/ubuntu/empire_agents/infra-qa

Mission: increase reliability, observability and regression coverage.

Own: test harnesses, health checks, systemd packaging, monitoring, CI-safe checks and pre-existing test blockers.
Do not own: commercial policy changes or product behavior unless required for a confirmed defect.

Invariants:
- Do not restart/enable production services without explicit approval.
- Preserve autonomous execution in OBSERVE.
- Never apply production migrations or rotate credentials.
- Keep tests isolated from canonical Supabase.
- Do not touch /srv/empire_os/recovery or /srv/empire_os/toop.

Deliver: reliability fixes, tests and packaging; no consequential runtime activation.
