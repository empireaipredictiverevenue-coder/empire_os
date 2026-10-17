# Founder Directive OS

## Operating rule

A Founder instruction is not a chat note. It is an input to the business.

## FOUNDER PRIORITY OVERRIDE — 17 October 2026: Revenue first, finish what exists

The founder has explicitly directed a permanent change of working approach across Empire AI, EmpireOS, ASTRA and its agents. The aim is **a functioning business with genuinely live products, qualified organic traffic, real buyer conversations, accepted customers and verified revenue** — not endless architecture, gates, reports or internal systems. This rule governs how all future work is selected, planned, delegated, reviewed and reported.

1. **Revenue and customer value first.** Tie active work to an existing commercial goal or a registered blocker of that goal. Prioritise the shortest honest path to a real working capability, real traffic, conversion, delivery and realised revenue. Avoid optimising internal dashboards or test counts as if they were customer outcomes.
2. **Finish, integrate and ship before expanding.** Check the existing stack, worktrees, modules, ASTRA tasks and prior decisions first. Repair and reuse what we have. Do not invent agents, services, databases, frameworks, worktrees, handoffs, approval ceremonies or infrastructure unless an evidenced gap makes them necessary. No second server or paid traffic by default.
3. **No fabricated bureaucracy.** Distinguish actual law, customer consent, security, financial risk and platform requirements from optional EmpireOS procedures we imposed on ourselves. Challenge, simplify or remove disproportionate self-imposed gates, including mandatory paid counsel when no such legal duty has been established. Do not bypass genuine legal obligations or fabricate compliance evidence.
4. **Respect decisions already made.** Founder approvals and buyer confirmations stay valid for their approved scope. Do not repeatedly ask the same questions, resend the same emails, redo completed checks or re-open settled design decisions unless material facts, scope or law changed. Record what genuinely changed instead.
5. **Proportional verification, then real results.** Focus tests on the changed risk; do not build extra test infrastructure for its own sake. A green test is engineering evidence, **not proof of a live business capability**. Confirm the actual site/workflow, real source evidence, customer reachability, buyer route and ultimately payment where applicable. Never invent results or recognise unverified revenue.
6. **Communicate concisely and constructively.** Each update says what visibly shipped, what commercial effect was observed, and the one or two real blockers remaining. Prefer completing a task to producing another handoff or exhaustive checklist. Restore creativity, design quality, momentum and founder enjoyment; avoid tedious repetitive loops.
7. **Keep proportionate real-world safeguards.** Existing explicit founder authority requirements for live outbound, buyer delivery, money movement, binding commitments, sensitive data, destructive changes and production deployment remain in force. Keep truthful consent, privacy, recording responsibilities, unsubscribe and safety protections. No automatic live activation from this directive alone.

**Practical decision before any new task:** "Will this reuse existing capability and materially bring Empire AI closer to live customer value or verified revenue? If not, why are we doing it now?" If there is no compelling answer, defer or drop it rather than expanding the stack.

**Completion standard:** a working outcome demonstrated against reality, with concise evidence; not merely a passing test, an architectural diagram, a file written or another pending approval.

This founder priority takes precedence over procedural *preferences* elsewhere in historic docs that require blanket diagrams, elaborate planning or additional sign-off for low-risk tasks. It does not override genuine legal, security, privacy, financial or explicitly retained execution-authority requirements.

---


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
