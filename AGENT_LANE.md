# Agent Lane: Closer / Outreach
Branch: agent/closer-outreach
Worktree: /home/ubuntu/empire_agents/closer-outreach

Mission: complete governed buyer outreach, reply handling and closer flow.

Own: governed outbound lifecycle, reply ingestion, closer state machine, buyer pipeline integration and tests.
Do not own: payment recognition, Astra calibration, tenancy architecture.

Invariants:
- Autonomous execution remains OBSERVE.
- No real buyer email/SMS/call send without explicit production approval.
- Legacy direct-send paths stay retired.
- Human/review gates remain authoritative.
- No synthetic buyer replies or conversions.
- Do not touch /srv/empire_os/recovery or /srv/empire_os/toop.

Deliver: implementation + tests + docs/config. Stop at live-provider activation gates.
