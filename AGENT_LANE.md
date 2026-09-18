# Agent Lane: Astra / Phase 4
Branch: agent/astra-phase4
Worktree: /home/ubuntu/empire_agents/astra

Mission: finish Phase 4 Astra observer/calibration safely.

Own: empire_os/astra.py, empire_os/astra_feedback.py, Astra observer transport/worker, Phase 4 migration/tests/docs/config.
Do not own: payment verification semantics, closer UX, SaaS tenancy, production service activation.

Invariants:
- OBSERVE or DRY_RUN only.
- Real Phase 3F outcome/revenue evidence only; no synthetic or mock inputs.
- Dedicated read-only Astra DB role.
- Never apply migrations to canonical Supabase.
- Never provision production credentials.
- Never enable live outbound or financial authority.
- Do not touch /srv/empire_os/recovery or /srv/empire_os/toop.

Deliver: code + isolated tests + docs + commit(s). Stop at production activation gates.
