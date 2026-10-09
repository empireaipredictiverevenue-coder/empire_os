# EmpireOS existing Deal Room — Documenso integration, 9 October 2026

**Decision:** Use the existing EmpireOS platform and its existing `/v1/deal-room` router. Documenso is an external signing provider already selected by the founder. This change does NOT create a new platform, replace the CRM, install Docker, deploy another signing application, create a standalone dashboard or start new background agents.

## Code path already built

- `empire_os/deal_room.py`: existing envelope-plan preview, now bound to a configurable existing Documenso V2 instance, read-only status function, and fail-closed legacy completed-webhook normalization. Webhook alone is **not** verified contractual evidence.
- `empire_os/deal_room_api.py`: existing Deal Room health/previews, now includes safe Documenso connection-readiness metadata (no token values, no signing links).
- `empire_os/deal_room_documenso_provider.py`: strict exact-origin allowlist, read-only `GET /api/v2/envelope/{id}` using configured existing API token; response shape, binding, signer and status reconciliation. It never creates/sends envelopes.
- `empire_os/contract_signing/`: internal provider policy and deterministic V2 request plan, not an independent service or separate platform.
- Contract completion requires provider read-back **and signed PDF/audit validation**; PDF integrity checking and canonical signed agreement registration remain separately gated. A completed envelope is not payment or realised revenue.

## Existing Documenso connection variables

Set only in the *existing* EmpireOS service-secret environment, not in Git:

- `DOCUMENSO_API_BASE_URL`: defaults to `https://app.documenso.com/api/v2` (set to the existing Documenso instance if self-hosted).
- `DOCUMENSO_TRUSTED_HOST`: defaults to `app.documenso.com`; must exactly match the configured service hostname.
- `DOCUMENSO_API_KEY`: team API token from that account; **never** print it or copy it into chat.
- `DOCUMENSO_WEBHOOK_SECRET`: if webhook previews are configured, provision the provider's exact secret through the existing service environment.

No signing operation, deployment, or mailbox change may be inferred from merely setting environment variables.

## Production boundaries

- This stage only changes source in the **already existing** EmpireOS repo. Do not restart systemd or enable calls without authenticated tenant authority, published reviewed contract terms, consent/suppression controls, confirmed provider credentials, and explicit founder approval.
- The existing Deal Room has a preview webhook endpoint. Its `verified_webhook` flag means the header matched the configured shared secret, **not** that a contract is signed. `agreement_evidence_verified` remains false pending authenticated API + artifact checks.
- The provider read-only API is called internally; no new unauthenticated public status route is exposed.
- The new readback client enforces the provider's configured HTTPS hostname and blocks redirects. It returns no signatures, signing links, secret tokens, or recipient email addresses.
- No real Documenso instance access, send/draft API write, contract execution, payment request, CRM write, or settlement-fee authorisation was performed.

## Specific next activation proof

1. Verify the existing Documenso account and its official instance URL/token are configured under EmpireOS.
2. Verify authenticated readback for an existing non-sensitive test envelope linked to a real tenant and agreement version.
3. Add the reviewed, owner-approved create/distribute capability behind the existing Deal Room founder/tenant authority, not an exposed endpoint.
4. Verify signatures, finalized PDF bytes, audit trail and immutable canonical contract event in EmpireDB.
5. Prove a test signature without creating a financial transaction, then separately activate live binding-signature delivery with founder authorisation.

Current Documenso V2 documentation:
- https://docs.documenso.com/docs/developers/api/documents
- https://docs.documenso.com/docs/developers/getting-started/authentication
- https://docs.documenso.com/docs/developers/webhooks/verification
