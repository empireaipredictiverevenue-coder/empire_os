# Authentik Identity Intake — 2026-09-21

## Decision

**Adopt as the planned Empire identity edge, not as an immediate replacement
for Supabase or Cloudflare Access.**

Authentik is a strong fit once Empire has multiple internal apps, partner
portals, enterprise SSO requirements, and service/user provisioning needs.

Official repository:
https://github.com/goauthentik/authentik

## Why it fits Empire

Authentik can provide:
- OIDC/OAuth2 identity provider and relying-party flows;
- SAML for enterprise customers and partner applications;
- LDAP/RADIUS compatibility where legacy integrations require it;
- proxy/forward-auth for applications that do not implement native OIDC;
- SCIM provisioning/deprovisioning for users and groups;
- centralized groups/roles/policies across Founder Console, Search Command
  Centre, partner portals, internal ops tools and future white-label surfaces.

## Empire architecture

Cloudflare
-> Authentik identity edge
-> OIDC/proxy authorization
-> Founder Console / Search / CRM / partner applications
-> application-specific authorization
-> Supabase canonical business data.

Supabase remains the canonical business database and may continue to provide
customer-facing application auth where it is already appropriate. Authentik
should initially federate/protect applications rather than forcing a risky
auth rewrite.

## First deployment target

1. Stage Authentik on an isolated host/container.
2. Protect a non-production internal application first.
3. Bind Founder Console through OIDC or forward auth.
4. Create groups/roles:
   - founder
   - operator
   - closer
   - analyst
   - partner
   - service
5. Require strong authentication for founder/operator roles.
6. Map Authentik identity claims into application-level authorization.
7. Add SCIM only where automated provisioning is required.
8. Preserve Cloudflare Access as a compensating outer control until Authentik
   is proven stable and recovery procedures are tested.

## Do not do yet

- Do not replace every Supabase user/session path.
- Do not remove Cloudflare Access before staged validation.
- Do not make Authentik the only route to emergency administration without a
  documented break-glass path.
- Do not expose Authentik admin publicly without strict access controls.

## Gate

Identity cutover changes who can access production applications and is a
founder/security gate. This document authorizes design and staging only, not a
production identity cutover.
