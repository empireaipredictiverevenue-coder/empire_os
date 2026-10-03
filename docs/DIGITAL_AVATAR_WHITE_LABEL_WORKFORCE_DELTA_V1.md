# Empire Digital Avatar — White-Label Workforce Projection V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Product/control-plane architecture delta

## Purpose

Provide a tenant-branded view of the Digital Avatar Clone Fleet product without
using legacy SQLite white-label state and without allowing branding to change
identity, capability, disclosure or execution authority.

V1 is projection only: no persistence, domain setup, DNS, file upload or HTTP
tenant self-service.

## Canonical ownership

The existing empire_os/whitelabel.py is legacy SQLite compatibility state and
is NOT canonical for Clone Fleet.

V1 consumes an explicitly supplied trusted tenant branding configuration and the
global authority-free clone role-template catalog.

Future persistence must use approved canonical tenant configuration after its
own EmpireDB tenant-context architecture gate.

## Configurable fields

V1 may configure:
- tenant_id;
- brand_name;
- workforce_product_name;
- allowed approved clone-role template keys;
- optional brand_asset_ref pointing to separately governed brand evidence.

V1 may NOT configure:
- avatar owner/person identity;
- owner consent;
- voice/visual clone identity;
- capability contents inside a template;
- meeting authority;
- commercial/payment/close authority;
- AI disclosure removal/suppression;
- arbitrary prompt/system instructions;
- secrets/API keys;
- provider meeting credentials.

## Role projection

Only role templates from the canonical Clone Role Template catalog may appear.

A white-label config chooses a subset. It cannot add capability labels or
specialist domains and cannot rename a role in a way that changes its semantic
authority.

The global template remains immutable; projection returns a tenant-branded
presentation wrapper around the unchanged template facts.

## AI disclosure

White-label branding never hides that the representative is AI.

Every projection has:
- mandatory_ai_disclosure=true;
- disclosure_override_allowed=false;
- live_identity_disclosure_still_required=true.

Actual live-meeting disclosure remains owned by DigitalAvatarIdentity and the
meeting runtime. This projection cannot satisfy or bypass that gate.

## Authority

Always:
- mode=OBSERVE;
- projection_only=true;
- identity_created=false;
- consent_granted=false;
- tenant_configuration_persisted=false;
- DNS/domain_mutation=false;
- speech/commercial/payment/revenue authority=false;
- execution_authority=none.

## Isolation

The output is tenant-keyed but V1 does not authenticate the caller. No public
HTTP endpoint is allowed until trusted tenant authentication exists.

No legacy tenants.py or whitelabel.py storage access is permitted.

## Verification

Required:
- allowed template subset projects deterministically;
- unknown/duplicate template keys fail closed;
- template capabilities/consultation defaults remain unchanged;
- brand projection contains no owner/consent/secrets;
- AI disclosure cannot be disabled;
- legacy SQLite white-label modules are not imported;
- no persistence/DNS/provider/execution authority;
- full Fleet/Avatar regression remains green.
