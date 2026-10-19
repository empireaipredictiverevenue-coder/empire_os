# Empire AI Predictive Intelligence — signed customer model-preview identity

19 October 2026 | Source branch `feature/predictive-decision-control-20261018`
Owner of future runtime: CRM tenant authority + Model Router + Security, not
another independent agent or new data store.

## Problem closed in source

The previous `TrustedSandboxSession(authenticated_server_session=True)`
was a deliberately injectable TEST fixture, not actual customer identity.
Reusing a CRM `crm:read` bearer to authorize model calls would create
confused-deputy and tenant-isolation risks, especially with optional
customer-supplied external inference providers.

New `empire_os/flagship_signed_model_preview.py` introduces a dedicated
**offline / integration-test-only** cryptographic admission sequence:

1. Dedicated, separately provisioned, pinned Ed25519 MODEL PREVIEW public
   key ring; no signing secret or token issuer is implemented here.
2. Exact `aud=empire-predictive-model-preview` and
   `scope=model:preview` claims, distinct from existing
   `aud=empire-revenue-crm` / `scope=crm:read`.
   Key ID, JWT EdDSA algorithm, exact permitted claims, signatures, UTC
   lifetime limits and canonical UUIDs are verified using the existing
   strict signed CRM parsing primitives. CRM tokens are rejected by the
   model verifier, and model tokens are rejected by CRM.
3. Fresh canonical membership lookup on EVERY preview request.
   The same verified subject MUST be an active owner/admin of the signed
   tenant. No client header, query string, agent output or JSON boolean
   can substitute for this lookup; revoked, viewer, analyst and operator
   memberships are denied.
4. The server-controlled provider allowlist must permit the exact
   configured model mode. A customer cannot provide their own model URL,
   provider ID, tools or API key to this integration. Only known preview
   identifiers are accepted by the existing synthetic sandbox.
5. Check the reviewed, hash-pinned Empire SOUL and no-tools policy BEFORE
   spending a preview allowance.
6. Require a server-controlled **atomic one-time reservation** tied to
   signed tenant + token JTI. A denied or duplicate reservation blocks
   model invocation. Exception messages are masked. The test uses an
   injected in-memory duplicate check, NOT a production-valid rate store.
7. Create a no-tools/no-payment/no-outbound single-turn synthetic sandbox
   configuration internally from verified identity. Run only an
   independently injected test callback with safe built-in scenario.
   Output remains untrusted even when it conforms to the exact JSON schema.
8. Return only enum reason/status, safe SOUL digest, whether the model was
   called, and non-authority booleans. Never return tenant ID, subject, JWT,
   JTI, API credentials, raw model response or private commercial details.

## Tests / real truth

The suite exercises:
- cross-audience/scope confusion, incorrect or unsigned signatures,
  malformed/duplicate JWT claims, bad keys, expiry and future clocks;
- cross-tenant mismatches, revoked membership, non-owner/admin roles,
  canonical tenant ID rejection, and unavailable membership readers;
- unknown providers, unexpected model modes, invalid SOUL, injected
  tool/email/payment requests and outputs claiming verified buying intent;
- absent quota ledger, exception/false/boolean-like quota receipts, and
  duplicate attempts sharing a signed JTI; only one injected synthetic
  callback may execute;
- validated model input has no customer records, and all output remains
  advisory.

This feature reuses the existing CRM membership model and cryptographic
parsing but **does NOT extend CRM token scope or DB grants**. The
existing `SignedCrmTenantVerifier` implementation is unchanged.

The existing Founder Decision Control now returns the safe static
`flagship_signed_model_preview` readiness status. Its UI must explicitly
say the issuer, durable rate/nonce ledger, customer vault and public route
are NOT deployed. No model/API-key input widget is created.

## What is NOT built or verified

- No live token issuer and **no signing private key provisioned**.
- No independently deployed public-key ring, live customer authenticated
  endpoint, provider router, hosted model API client, vault, token
  revocation store, durable atomic replay/tenant-budget ledger, distributed
  concurrency controls or operational SLA.
- No tenant-owned model stored in EmpireDB and no client model/provider
  selection that affects production behaviour.
- No customer API credential, customer record, full prompt, payment or
  outbound sent. No new app routes, services, cron or database mutations.
- Signed membership cannot by itself authorize data retrieval, external
  model data disclosure or business actions. Each source request needs
  independently verified tenant authority, consent and data minimization.
- These tests demonstrate **policy enforcement for the synthetic scenario**,
  not resistance to all prompt injection or model quality. The previously
  tested local Qwen server had two transport holds and one rejected JSON
  response. No model met customer quality or availability benchmarks.

## Next real product milestones

1. Coordinate the owner of signed CRM/login authority to issue
   **independently audience-scoped model-preview tokens** with a dedicated
   model-preview key ring, revocation, key rotation and access policy.
2. Implement one atomic tenant-scoped nonce-and-budget reservation in the
   existing canonical authenticated billing/control fabric, with audit
   evidence, concurrency replay tests, TTL, fail-closed outages and
   reconciled per-tenant cost accounting. DO NOT accept a test lambda in a
   production route.
3. Secure an allowlisted provider registry and vaulted customer API
   credentials, tenant-controlled permitted data residency and explicit
   consent; no arbitrary URLs, redirect SSRF or logging of credentials.
4. Run robust representative model quality evaluations, zero-tool red-team
   and synthetic provider egress tests before customer traffic.
5. Independently bind actual source evidence, buyer intent and Quant
   results before the customer can see verified market or revenue claims.
6. Build a signed tenant customer UI with clear **Empire-managed** versus
   **Bring Your Own Model** pricing and disclosure, with accessible
   account settings and revocation controls, only after approvals.

**Release gate:** all work remains feature-branch only. No live buyer
service, CRM auth, API gateway, payments, website or model provider
configuration changed.

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -m pytest -q \
  tests/test_flagship_signed_model_preview.py \
  tests/test_flagship_customer_agent_sandbox.py \
  tests/test_revenue_crm_signed_auth.py
```
