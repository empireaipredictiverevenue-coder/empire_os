# Empire Digital Avatar — Commercial Packaging & Entitlement Projection V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Commercial product architecture delta

## Purpose

Define sellable Digital Avatar / Clone Fleet product shapes without inventing
pricing, usage limits, tenant entitlements or live commercial readiness.

V1 bridges Digital Avatar product structure into Empire's existing canonical
commercial-product catalog and evidence-first SaaS usage model.

## Product shapes

V1 defines three product shapes:

1. digital_avatar_copilot
   - one or more authorised human clones;
   - SHADOW and COPILOT product capability;
   - grounded response support;
   - specialist consultation;
   - verified meeting usage metering.

2. digital_avatar_workforce
   - multi-clone fleet;
   - role-template routing;
   - concurrency planning;
   - continuity memory;
   - specialist consultation;
   - verified usage/quota review.

3. digital_avatar_white_label_workforce
   - workforce capabilities above;
   - tenant-branded workforce projection;
   - mandatory AI disclosure remains non-overridable.

These are product definitions, not active catalog products and not prices.

## Canonical commercial truth

Commercial readiness requires a matching canonical EmpireDB product row where:
- product_code matches the package product_code;
- active == true;
- catalog_state == VERIFIED;
- version_state == VERIFIED;
- price_basis == VERIFIED;
- acquisition_cost_basis == VERIFIED;
- fulfilment_cost_basis == VERIFIED;
- margin_policy == VERIFIED;
- binding_terms_ready == true.

The existing commercial_product_catalog.assess_catalog_item() remains canonical
for product/version readiness.

No amount, currency or billing model is hard-coded into this module.

## Entitlement truth

Feature/usage entitlement is a separate verified commercial-terms fact.

AvatarCommercialEntitlementEvidence contains:
- verified boolean;
- reference;
- verified_at;
- tenant_id;
- product_code;
- allowed_role_template_keys;
- allowed_meeting_modes;
- max_active_avatars;
- included_verified_meetings_per_month;
- white_label_allowed.

No defaults are invented for limits. Missing limits/terms block entitlement
readiness.

The commercial catalog proves product price/economics readiness.
Entitlement evidence proves what this specific tenant bought.

## Role / authority separation

A commercial entitlement may permit a product feature, but it does not:
- create AvatarFleetBinding;
- create DigitalAvatarIdentity;
- create owner consent;
- assign a clone to a meeting;
- approve a Recall join;
- approve speech;
- approve commercial negotiation/close;
- create a payment request;
- recognize revenue.

Meeting/runtime authority stays owned by the existing Digital Avatar gates.

## Projection output

AvatarCommercialPackageProjection contains:
- package key / product_code;
- catalog product identity/version when verified;
- verified public price projection only when canonical catalog is ready;
- verified tenant entitlement limits;
- commercially_ready;
- entitlement_ready;
- blockers;
- actual_revenue=false;
- checkout_created=false;
- subscription_mutation=false;
- payment_request_creation=false;
- funds_movement=false;
- recognized_revenue=false;
- execution_authority=none.

## Current production truth

As of the current runtime catalog snapshot, no verified Digital Avatar product
row exists. Therefore V1 product definitions must project commercially_ready
false until governed catalog activation occurs.

## Verification

Required:
- product-shape registry is deterministic and contains no prices;
- unknown package fails closed;
- missing catalog row blocks commercial readiness;
- unverified/inactive catalog row blocks;
- verified catalog row may expose only canonical public price fields;
- missing/unverified entitlement evidence blocks;
- entitlement product/tenant mismatch blocks;
- role-template keys must come from canonical clone-role registry;
- meeting modes above package capability fail entitlement validation;
- package projection grants zero runtime/payment/revenue authority;
- current catalog snapshot cannot falsely make Avatar product live;
- full Avatar/Fleet regression remains green.
