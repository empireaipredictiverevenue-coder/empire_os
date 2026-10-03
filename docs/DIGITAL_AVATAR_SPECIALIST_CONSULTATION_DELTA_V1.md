# Empire Digital Avatar — Specialist Consultation Delta V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Architecture delta

## Purpose

Allow one visible Digital Avatar clone to privately consult EmpireOS specialist
departments during a meeting without spawning competing public avatars, leaking
authority, or bypassing evidence controls.

This is a multi-agent consultation planning layer, not a department-work queue,
not a meeting transport, and not an execution path.
## Existing owners reused

Consultation domains map to existing durable departments:

- sales -> sales_revenue
- product -> product
- technical -> engineering
- predictive_revenue -> data_quant
- research -> rd_innovation
- marketing -> marketing_growth
- strategy -> strategy

Department missions, components and agent roles come from
`departments.default_departments()`. The consultation planner does not invent
new specialist roles.
## Input contract

Required:
- validated tenant-scoped AvatarFleetRuntimeBinding;
- meeting_id and avatar_id matching that runtime;
- meeting mode SHADOW or COPILOT;
- one or more explicit consultation domains;
- buyer/question evidence ref;
- objective evidence ref;
- bounded maximum specialist departments.

V1 does not infer consultation domains from free-form buyer text. Domain
selection must come from a deterministic upstream rule or human/operator choice.
## Output contract

The plan contains:
- tenant_id / meeting_id / avatar_id;
- selected department keys;
- department missions;
- existing specialist agent roles;
- evidence refs to carry into consultation;
- consultation reason/domain;
- read_only=true;
- private_to_owner=true;
- external_execution_performed=false;
- department_work_enqueued=false;
- speech/commercial/payment/revenue authority=false;
- execution_authority=none.

No specialist response is automatically buyer-facing.
## Authority and data boundaries

Consultation may read approved evidence and return private advisory material.
It may not:
- enqueue Astra/department work;
- mutate department queues;
- call external tools on behalf of the buyer;
- speak in the meeting;
- send chat/email;
- quote or negotiate commercial terms unless those facts are separately
  resolved through the Digital Avatar canonical evidence layer;
- write Cortex/Economic Memory directly;
- grant REPRESENT/NEGOTIATE/CLOSE authority.

Specialist advice is advisory/inferred until grounded against canonical evidence.
## Failure behavior

Unknown consultation domain -> validation failure.
Missing evidence refs -> fail closed.
Runtime tenant/avatar mismatch -> deny.
More requested domains than max_specialists -> deterministic bounded selection
by the caller-provided order, with truncation reported explicitly.
Duplicate domains -> normalize/dedupe.
Missing department owner -> fail closed; never substitute another department.
SHADOW/COPILOT only.
## Future execution

A later consultation worker may call existing specialist adapters or internal
model/department surfaces under OBSERVE/read-only authority. That worker must
return a structured specialist packet with:
- advice;
- evidence refs consumed;
- unresolved evidence gaps;
- confidence/uncertainty;
- no execution authority.

Only the existing grounded response-draft pipeline may decide whether supported
specialist advice becomes part of a human-reviewed meeting response.
## Verification

Required:
- each consultation domain resolves to the canonical existing department;
- roles/components come from department registry;
- duplicate domains dedupe deterministically;
- max specialist bound enforced and truncation visible;
- unknown domain fails closed;
- runtime meeting/avatar/tenant mismatch denied;
- no department work enqueued;
- no external/speech/commercial/payment authority;
- full Avatar/Fleet regressions remain green.
