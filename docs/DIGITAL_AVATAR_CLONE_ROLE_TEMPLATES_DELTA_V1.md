# Empire Digital Avatar — Clone Role Templates V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Product/control-plane architecture delta

## Purpose

Create reusable workforce templates for common Digital Avatar roles without
turning a role name into identity consent, meeting authority or commercial
authority.

V1 role templates package capability labels and suggested internal specialist
consultation domains only.

## Initial templates

- founder_executive
  - capabilities: founder, strategy, sales, product
  - consultation: strategy, sales, product, predictive_revenue
- sales_closer
  - capabilities: sales, qualification, objection_handling, product
  - consultation: sales, product, predictive_revenue
- account_manager
  - capabilities: account_management, customer_success, product
  - consultation: product, sales
- product_specialist
  - capabilities: product, discovery, solution_design
  - consultation: product, technical, research
- technical_specialist
  - capabilities: technical, integration, architecture
  - consultation: technical, product, research

These are product-role defaults, not evidence that a particular human possesses
a capability.

## Template / identity separation

Applying a template may propose:
- capability_labels;
- default consultation domains;
- display-role label;
- suggested meeting objectives.

Applying a template may NOT:
- create DigitalAvatarIdentity;
- create/assume owner consent;
- create voice/visual clone assets;
- grant tenant membership;
- change meeting mode;
- grant speech/commercial/payment/close authority;
- create product/pricing claims;
- schedule or join a meeting.

A real clone still requires AvatarFleetBinding + DigitalAvatarIdentity with exact
owner/consent evidence and the existing fleet runtime validator.

## Tenant / white-label semantics

Templates are globally reusable product definitions and contain no tenant data,
person data, secrets or commercial pricing.

A future tenant override may select a subset or rename the visible role, but may
not silently expand capabilities beyond an explicitly approved template/policy
contract.

V1 has no persistence and no HTTP surface.

## Authority

Template projection always:
- mode=OBSERVE;
- identity_created=false;
- consent_granted=false;
- meeting_authority=none;
- speech_execution_allowed=false;
- commercial_execution_allowed=false;
- payment_execution_allowed=false;
- execution_authority=none.

## Composition

Template -> proposed AvatarFleetBinding fields -> explicit owner/tenant
validation -> fleet runtime binding -> routing/assignment.

The routing engine may use template capability labels only after they have been
materialized into a validated fleet binding. It must not route directly from a
template name.

Specialist consultation domains are defaults only and must still be selected by
a bounded consultation request with evidence refs.

## Verification

Required:
- template catalog deterministic and unique;
- no template contains authority/consent/tenant/person data;
- applying template returns proposal only;
- capabilities and consultation domains dedupe deterministically;
- unknown template fails closed;
- template cannot overwrite avatar/owner consent inputs;
- routing only works after validated binding materialization;
- full Fleet/Avatar regression remains green.
