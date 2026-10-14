# JEV GTM V2 — Wave 10 Signed First-Party Transport Observation Boundary

Date: 2026-10-14
Isolated branch: `feature/jev-gtm-v2-20261014`
Starting commit: `dcc29168`
Status: OBSERVE. No production keys, receipts, signer, MTA listener, webhook, scheduler, database migration, live outbound or payment work.

## What is actually proven

Existing first-party `OwnedIMAPMailboxProvider` proves only bounded, read-only IMAP accessibility of messages. IMAP UIDVALIDITY and a matching RFC `Message-ID` / `In-Reply-To` are **not independent proof of original SMTP ingress**. Email `Authentication-Results` headers are not trustworthy when read as untrusted MIME text without verifying the receiving trusted MTA's header boundary; mail content cannot grant buyer or canonical contact status.

EmpireOS already has an Ed25519 trust pattern in `empire_os/revenue_crm_signed_auth.py`. Wave 10 uses the same public-key verification primitive in a **different, strictly domain-separated signed ingress receipt contract**. The Revenue CRM bearer keys are not reused; JEV does not mint transport receipts or expose a private key.

## New verification module

`empire_os/jev_gtm_signed_transport_review.py`:
- Accepts a strict, signed source packet containing exact schema, pinned `key_id`, claims and Ed25519 signature.
- Caller must inject the independently approved trusted *first-party SMTP ingress* public key, distinct from the separate minimum 32-byte operator HMAC key used to pseudonymize mailbox RFC/header IDs.
- Cryptographically verifies canonical, domain-separated JSON content. Rejects changed data, wrong key IDs, unexpected fields, invalid Ed25519 signature, untrusted origin/audience, missing RFC chain, unsupported claimed ingress states, malformed raw-message SHA-256 and invalid timestamps.
- Bounds maximum 25 source packets, checks freshness (maximum 7 days), generation within 5 minutes of asserted ingress, no future timestamps, unique event IDs and no two accepted receipts claiming the same RFC/alias triplet.
- Verifies signed *tenant assertion* matches the request-scoped trusted CRM tenant ID, but does **not** claim signer has independently proved canonical tenant/contact membership.
- Matches signed RFC `Message-ID`, original parent and canonical-looking intent UUID to **HMAC-only fields** in the previously validated owned-mailbox review, and only if the outbound parent match is unique and structural blockers are exclusively the known original-authentication and contact-binding gaps.
- No raw MIME body, sender, recipient, subject, original RFC ID or tenant UUID emitted in a review response. Only HMAC references, candidate counts, cryptographic statement and explicit non-authority fields.
- A valid Ed25519 signature means *the pinned private key signed that assertion*. It **does not independently prove** a real production ingress producer was hardened, a raw message digest matches the entire mailbox message, the authenticated source actually originated from the buyer, or a canonical contact/tenant match.
- Consequently `original_smtp_provider_authentication_independently_proven=false`, `canonical_tenant_contact_binding_verified=false`, `buyer_reply_count_verified=null`, `recognized_revenue=null`, suppression clearance FALSE, outbound FALSE.

The original `jev_gtm_mailbox_header_review.py` now emits a separately HMAC-keyed `inbound_rfc_ref` so signed transport assertions can be compared without exposing original RFC identities. The Founder API response allowlist is updated accordingly. Existing mailbox provider is not modified.

## Optional, guarded Founder API route

`GET /v1/founder-jev/crm-prospects/{prospect_id}/signed-transport/review?limit=25`

Registration requires **all** external owner-provided dependencies:
1. Independently trusted founder authorizer.
2. Existing request-scoped authenticated Revenue CRM resolver with session-user tenant reader.
3. Concrete read-only owned IMAP provider.
4. Independent mailbox HMAC key.
5. Independently trusted first-party receipt source callback (not request body/client JSON).
6. Pinned first-party ingress Ed25519 public keys.

Authorization runs before DB, receipt or mailbox calls. CRM prospect identity is checked against existing tenant-scoped `PostgresRevenueCrmRepository.prospect()` before ingesting the signed source, and all errors are sanitized. The route is **absent by default**. Exact response shape and no-PII allowlist refuse unexpected fields or fabricated positive buyer approval.

The signer/issuer and transport-boundary collector do not exist in this branch. The host is not allowed to construct or fetch arbitrary signed receipts from request-controlled fields. Do not consider this activated merely because the verifier passes test vectors.

Founder `/v1/founder-jev/status` and standalone `/founder/jev` now show:
- code verifier implemented = TRUE;
- externally injected producer configured (only if all gate dependencies provided);
- ingress producer independently audited = FALSE;
- independently verified buyer replies = UNKNOWN/null.

## Test proof

- `tests/test_jev_gtm_signed_transport_review.py` exercises an **independently generated ephemeral test-only Ed25519 keypair**: positive signature+header-chain proof, altered payload/signature rejection, wrong pinned key, wrong tenant, unsupported boundary/DMARC assertion, stale/future receipts, duplicate provider events, conflicting attestations, unmatched RFC aliases, HMAC key separation, untrusted MIME header and no raw/private data.
- `tests/test_founder_jev_signed_ingress_api.py` exercises route registration fail-close, founder-before-source ordering, request-scoped tenant/prospect check, no keys, bad UUID, missing original proof, tampered signatures and strict non-authority API output.
- Mandatory existing JEV/CRM/Conversation/IMAP tests continue as regressions, with frontend TypeScript and exact API schema validation.
- **Final broad integration gauntlet: 694 tests passed, 10 subtests passed, 0 failures, 1 existing Starlette/AnyIO deprecation warning.**
- **Frontend TypeScript type-check: PASS.** Isolated source syntax, diff and commit checks verified separately.

No real transport signing key, real original-provider receipts or customer personal data were accessed, minted or provisioned. The production deployment is intentionally *not* complete, and no real buyer reply is certified by this code alone.

## Next real activation proof requirements

1. Independent mail-transport owner audits actual first-party receiving MTA, authentication-results trust boundary, TLS delivery path, original SMTP event log, raw message digest custody, signer key protection and signature issuance. Signatures must originate at that trusted boundary, not from self-attesting MIME or a convenient developer command.
2. Review each signer/issuer role and public key pins; launch by separate approval under controlled service identity, with observable revocation, replay controls and privacy retention.
3. Match the signed original event to a canonically authenticated prospect and sender contact, using existing EmpireDB tenant authority, and validate independently complete suppression/consent readback before any outbound action.
4. Obtain independently labelled genuine buying-intent cases and check commercial economics. Classifier score or positive language is not buyer proof; quote/funds remain founder gated.
5. Resolve Wave 6 prepared migration 051 approval, canonical DB access and actual live readback separately from this release. Do not patch production ad hoc or enable any outbound service in this wave.

**Completion scope:** signed-transport observation verifier and gated, privacy-minimal review API only; no real-world provider attestation or commercial activation.
