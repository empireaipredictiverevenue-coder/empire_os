# Agent Lane: Platform / SaaS
Branch: agent/platform-saas
Worktree: /home/ubuntu/empire_agents/platform-saas

Mission: prepare the multi-tenant commercial platform without disturbing live revenue control.

Own: tenant model, org/account boundaries, permissions, white-label foundations, dashboard/API scaffolding.
Do not own: BSC settlement semantics, live outbound activation, Astra control authority.

Invariants:
- Preserve canonical Supabase data model and governance boundaries.
- No production schema apply or destructive migration.
- No fake tenants/revenue in production-capable paths.
- Prefer additive, reversible changes and isolated tests.
- Do not touch /srv/empire_os/recovery or /srv/empire_os/toop.

Deliver: architecture/code/tests/docs suitable for later gated production activation.
