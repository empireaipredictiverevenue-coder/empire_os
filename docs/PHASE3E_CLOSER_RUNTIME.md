# Phase 3E Governed Closer Runtime

Status: local implementation complete; production activation gated
Execution authority: OBSERVE only

## Purpose

The governed closer runtime replaces legacy SQLite/LLM closing behavior with
separated PostgreSQL authorities tied to real classified replies and the
canonical Supabase closer state machine.

Current flow:

```
real outbound reply
→ deterministic reply classification
→ bounded closer work projection
→ OBSERVE-only closer recommendation
→ planner role (future gated)
→ human/governed approver role
→ canonical fulfilment/payment gates
→ verified outcome/revenue
```

The observer never sends outreach, creates commercial terms, changes closer
state, marks a deal won, recognizes revenue, or invents deal value.

## Runtime Authorities

Migration:

`supabase/migrations/20260918144500_phase3e_closer_runtime_identities.sql`

Roles:

- `empire_closer_observer`
  - execute `list_closer_work(integer)` only;
  - cannot open cases, recommend, advance cases or write tables.
- `empire_closer_planner`
  - may list closer work;
  - may open a canonical case from a genuine classified reply;
  - may record a recommendation;
  - cannot advance closer state.
- `empire_closer_approver`
  - may execute the existing governed `advance_closer_case(...)` RPC only;
  - cannot open cases or record recommendations.

Each authority has a separate staged login role with:
- password NULL;
- NOINHERIT;
- no superuser/database/role/replication/RLS bypass authority;
- connection limit 5;
- 15-second statement timeout;
- 30-second idle-in-transaction timeout.

No login credential has been provisioned in production.

## Work Projection

`list_closer_work(p_limit)` returns a bounded, non-PII projection of genuine
classified commercial replies:

- reply ID;
- outbound intent ID;
- classification and confidence;
- received timestamp;
- closer case ID/state when present;
- canonical prospect/entity/buyer/opportunity/order identifiers.

Only `positive`, `question`, and `objection` replies enter closer work.
Terminal won/lost cases are excluded.

The projection intentionally excludes reply bodies and contact addresses from
the observer work queue.

## OBSERVE Worker

Modules:
- `empire_os/closer_role_transport.py`
- `empire_os/closer_observer.py`
- `scripts/closer_observer.py`

The active worker:
- accepts `EMPIRE_CLOSER_MODE=OBSERVE` only;
- requires the dedicated observer DSN;
- bounds work to 1..500 rows;
- creates deterministic recommendations from canonical state/classification;
- does not generate outbound copy;
- does not call planner or approver roles;
- writes only an atomic local JSON artifact at
  `runtime/closer/latest.json`.

Recommendation examples:
- no case + genuine engaged reply → `open_case`;
- engaged positive → `qualify`;
- engaged question → `answer_question`;
- engaged objection → `handle_objection`;
- qualified → `prepare_proposal`;
- proposal-ready → `escalate_human`;
- proposal-approved / awaiting-payment → `await_payment`.

Every recommendation has `execution_allowed=false`.

## Legacy Runtime Retirement

The following legacy runtime paths now fail closed:

- `POST /v1/agi/closer/tick`;
- `POST /v1/ai-closer/close`;
- `POST /v1/funnel/price-and-settle`.

The legacy `AgiCloserAgent` remains as a compatibility observer only. It
cannot mutate funnel state, invent settlement amounts, simulate replies or
send outreach.

## Production Gates

Before activation, explicit approval is required for:

1. applying the closer runtime identity migration to canonical Supabase;
2. provisioning observer/planner/approver login passwords/DSNs;
3. installing/enabling the closer observer service/timer;
4. enabling planner execution;
5. enabling any outbound send or state advancement.

The current worker remains OBSERVE-only regardless of those future roles.
