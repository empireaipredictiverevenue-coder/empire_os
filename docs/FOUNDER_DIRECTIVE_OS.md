# Founder Directive OS

## Operating rule

A Founder instruction is not a chat note. It is an input to the business.

Canonical lifecycle:

```
Founder directive
-> durable capture
-> dedupe
-> business-area classification
-> authority classification
-> Empire Coder refined plan
-> reuse-vs-new architecture decision
-> acceptance tests / observability / rollout plan
-> implementation-ready OR founder-gate
-> implementation under current execution policy
-> verification
-> rollout
-> Daily Results / Founder Console
```

## Why this exists

EmpireOS must eventually operate without ChatGPT being present. ChatGPT,
voice, the Founder Console, Ops MCP or another interface may originate an
instruction, but the instruction must become durable EmpireOS state before
work depends on it.

## Authority

Planning is automatic.

Reversible internal implementation can become `implementation_ready`, but
the current global runtime remains OBSERVE. The Directive OS does not by
itself grant production execution.

Fund movement, binding terms, revenue recognition, destructive production
changes and authority expansion are always marked `founder_gate`. They may
still be researched and planned automatically.

## Dedupe and reuse

The planner is explicitly instructed to search existing repo/docs/runtime
contracts first. The default is to extend or compose existing modules rather
than create parallel versions of the same capability.

## Inputs

Current supported native intake:

```
scripts/ingest_founder_directive.py --text "..."
```

Ops MCP and Founder Console integrations can call the same durable store.
Future chat/voice bridges should only need to translate the founder message
into this intake contract.

## Visibility

`runtime/founder_directives/latest.json` exposes:
- total directives;
- status/category counts;
- founder-gate count;
- latest directives;
- associated Coder task/job ids;
- explicit execution mode.

The Founder Read API exposes the same state read-only at:
- `/v1/founder-directives/status`
- `/v1/founder-directives/latest`

## Non-goals

Directive intake never:
- sends outbound;
- accepts terms;
- moves funds;
- verifies payment by mutation;
- recognizes revenue;
- destroys infrastructure;
- expands its own authority.
