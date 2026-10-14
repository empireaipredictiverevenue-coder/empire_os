# JEV GTM V2 — Wave 9 Sovereign IMAP-to-CRM Evidence Review

Date: 2026-10-14
Branch: `feature/jev-gtm-v2-20261014`
Starting commit: `3acb63d8`
Mode: OBSERVE; source worktree only, no live sender, payment, DB migration or production deployment.

## Commercial problem

A raw reply row or `positive` classification is not a verified buyer conversation. Migration 051 (prepared-only) can expose tenant-scoped candidate reply UUIDs, intent UUIDs, original-message-reference *presence* and conversation cardinality, but intentionally cannot validate an original provider receipt, mailbox ownership, sender identity or commercial intent.

Existing `empire_os.owned_imap_mailbox.OwnedIMAPMailboxProvider` is our first-party mailbox reader. It already uses IMAP over verified TLS, SELECT readonly and bounded BODY.PEEK, enforces folder UIDVALIDITY and avoids STORE/EXPUNGE. It explicitly reports `source_received_at_verified=False`, `canonical_thread_identity_verified=False`, and `canonical_contact_identity_verified=False`. IMAP INTERNALDATE and sender RFC Date are not cryptographically authenticated SMTP-delivery evidence and may be sender/operator controlled.

Existing `empire_os.conversation_reply_binding_review.review_identity_bindings` checks structural uniqueness but explicitly cannot attest original provider authenticity. Existing `empire_os.empire_mailbox._intent_from_values` extracts canonical-looking reply aliases while treating them as untrusted.

## Completed implementation

### Standalone, no-PII mailbox review

`empire_os/jev_gtm_mailbox_header_review.py`:
- Accepts an explicitly provided concrete `OwnedIMAPMailboxProvider`, independent operator-owned HMAC key of minimum 32 bytes, and bounded limit 1–25.
- Invokes existing `list_received` and `list_sent` only. Does not automatically load secrets, create a mailbox, send, change IMAP flags, call a third-party sender, write a DB or persist content.
- Checks UIDVALIDITY-backed source IDs, `owned_imap` provider marker, unique inbound RFC Message-ID, unique sent parent RFC identifier, original `In-Reply-To` link, and whether an apparent reply alias exists.
- Explicitly quarantines missing/duplicate RFC headers, sent parents, duplicate inbox UID, untrustworthy source flags and other structural defects.
- Outputs only HMAC-SHA256 references, structural reason codes and counts. No original RFC IDs, recipient/company address, subject, body, secrets or full message transcript.
- Even structurally unique pairs remain `STRUCTURAL_REVIEW_ONLY`, not original-provider verified, not canonical contact, and not verified commercial buyer interest.

### Optional CRM candidate alignment

`compare_owned_mailbox_to_crm_candidates` aligns an IMAP reply+UUID recipient alias to a canonical tenant-scoped CRM reply-candidate intent UUID using the same independent HMAC key. Explicitly labels resulting matches `ALIAS_UNIQUE_UNAUTHENTICATED`, `ALIAS_AMBIGUOUS_UNAUTHENTICATED` or `NO_ALIAS_MATCH_IN_BOUNDED_INBOX`.

The alias is MIME-recipient-controlled and can be forged; HMAC comparison only provides *structural investigation hints*. This does not prove cross-source tenant binding, original provider delivery, canonical person identity, contact permission, actual buyer intent, revenue or send authority.

### Existing Founder Read API conditional routes

`empire_os/founder_jev_api.py` conditionally registers:
- `GET /v1/founder-jev/mailbox/headers/review?limit=25` **only** when the host injects a pre-authorised concrete `OwnedIMAPMailboxProvider`, an independent HMAC key and a separate founder authorizer.
- `GET /v1/founder-jev/crm-prospects/{prospect_id}/mailbox-alignment?limit=25` **only** when additionally supplied an existing request-scoped `AuthenticatedRevenueCrmRead` resolver. It authenticates founder before invoking scope or accessing mail; verifies canonical tenant before IMAP fetch; uses the already-built migration-051 candidate read, failing 503 when not available.

Both routes are absent from the default service configuration. No alternate public API or new auth system introduced. 401/403/503 follow fail-closed behavior; responses must match an exact privacy-minimal, non-authoritative allowlist.

The standalone `/founder/jev` page reports mailbox-reconciliation readiness and exact unverified cross-source status; no private contact data is displayed. This UI remains undeployed on the isolated branch.

## Verified engineering evidence

- New `tests/test_jev_gtm_mailbox_header_review.py`: original owned-IMAP RFC metadata fixtures, unique/ambiguous/missing parent, repeated message IDs, duplicate UID, missing alias, tampered source authority, HMAC pseudonymization, invalid limits, no PII and uncompromising zero commercial authority.
- New `tests/test_founder_jev_mailbox_alignment_api.py`: route absence by default, mandatory independent founder auth and operator key, authorization before mailbox/database, missing CRM/tenant denials, migration-not-applied safe 503, exact no-PII response schema and alias-only cross-source hints.
- Regress existing `tests/test_owned_imap_mailbox.py`, `tests/test_owned_imap_rfc_provenance.py`, Founder JEV routes, canonical CRM and original reply checks.
- **Final wide JEV/IMAP/CRM/Conversation/Research gauntlet: 618 tests passed, 10 subtests passed; zero failures; 1 existing Starlette/AnyIO deprecation warning.**
- **TypeScript type-check passed** with existing dependencies; Python compile/diff check passed.
- All mailbox/network interactions in acceptance tests are **synthetic controlled fixtures**; tests do not claim real customer replies or use live credentials.

## Production truth / release blockers

1. **No live mailbox read was performed for this integration**. The founder-access provider, private HMAC secret and tenant-scoped CRM resolver were not injected into production.
2. Migration 051 remains **PREPARED, NOT APPROVED/APPLIED**; it has real disposable-PG isolation proofs but no live canonical readback.
3. RFC Message-ID, IMAP UIDVALIDITY and header-matching do **not** authenticate original SMTP receipt. Original first-party transport provenance and provider/server trusted metadata must be proved independently.
4. A canonical contact/tenant match, durable suppression readback, independently confirmed buying intent and measurable paid outcomes all remain separate gates. Do not promote a `positive` classifier label to buying proof.
5. Source-only branch work must be merged under concurrent agent coordination, reviewed and deployed with founder approval. No automatic mailing or funds.

The implemented Wave 9 closes the **review and privacy-preserving reconciliation code path**, not the still-unverified live buyer conversation or first actual revenue.
