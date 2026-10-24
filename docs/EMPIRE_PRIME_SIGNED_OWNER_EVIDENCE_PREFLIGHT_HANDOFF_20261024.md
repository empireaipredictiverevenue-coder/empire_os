# EmpireOS / PRIME — Original Owner Signed Evidence Preflight

**24 October 2026 — Research feature only — production release HOLD**

Parent: `eb03ca7be07379190eb2acfde96aa680e81b0aa7`, original branch `feature/prime-universal-evidence-fusion-20261024`.
One EmpireOS; original Predictive Cloud, Data Cloud, Chief/ASTRA, Quant, Risk, Buyer Acquisition, Smart CRM, Economic Memory and original EmpireDB untouched in production.

## New code and integration

- `empire_os/prime_signed_owner_evidence_gateway.py`: bounded, pure **Ed25519 pinned-original-owner-key** review preflight for detached signed owner summaries. Reuses design from the original `revenue_crm_signed_auth.py` and `gtm_signed_reviewer_gate.py` contracts. No new service, key, cloud, database, agent or customer-data store.
- `empire_os/predictive_revenue_brain_bridge.py`: new optional `signed_owner_evidence_envelopes` and `original_owner_signature_verifier` path. Signed+unsigned mixing is rejected. Existing unsigned owner summaries remain explicitly unverified/research only. Both paths expose only the existing privacy-coarsened `prime_universal_evidence_shadow` aggregate, no entity-level original receipt payloads.
- `tests/test_prime_signed_owner_evidence_gateway.py`: ephemeral offline keys and fictional receipts. Tests tampered signatures, wrong key, audience, tenant and source owner, forged authority, expired/future timestamps, nonce duplicates, cross-batch replay limitation, missing owner scope/source rights/entity binding, caller-supplied fake keys, no raw customer export, bridge guard and no external execution.

## Required first-party original-owner trust dependencies

An original, separately authenticated original-owner deployment **must** provision:
1. Pinned Ed25519 public keys with `kid -> (original_department_owner, public_key)`, ideally rotated/revocable through existing Security key registry. This module never generates or stores a production key.
2. `owner_scope_active(owner, authenticated_tenant, predictive:owner-evidence:review)` from the authoritative original owner roles/membership, not a signed user claim.
3. `canonical_binding_current(tenant, canonical_entity_digest, binding_digest, now)` from independently permissioned original canonical EmpireDB tenant-business-entity binding reader. This is an interface callback only; no live DB query configured.
4. `source_custody_current(owner, tenant, canonical_source_digest, originating_evidence_digest, event_digest, now)` from original Data Cloud's authorised rights/provenance records and consent/privacy governance. A signed `OWNER_REVIEWED_PERMITTED` string does not substitute for authoritative custody.
5. **Atomic durable nonce/replay receipt authority** independently designed/approved by original Security + EmpireDB owners; **NOT built or claimed** here. Same signed receipt can otherwise be replayed in a later batch; batch-local duplicates are rejected. Without a safe once-only gate, **live admission is prohibited**.
6. Original owner release authorisation for each exact producer and use purpose; original CRM inbound, buyer acquisition emails/threads, suppression and source consent unchanged.

### Exact signature scope

`empire-prime-owner-evidence-ed25519-v1:` domain-separated canonical `sort_keys=True`, compact JSON bytes. Signed `empire.prime.signed_original_owner_summary.v1` payload includes fixed `empire-prime-owner-evidence-observe` audience, `predictive:owner-evidence:review` scope, original owner name, tenant digest, UTC issue/expiry (max five minutes), bounded batch nonce, exact original private v1 receipt. The envelope contains only `kid`, signed payload and canonical base64url Ed25519 signature.

Wrong signers/scopes, expired/late keys, inactive owner, mismatched tenant, unverifiable binding or custody cause **fail-closed** rejection. Any upstream callback error becomes a generic hold message with no customer details.

Even when the test key, source, tenant and owner callbacks all pass, output is permanently labelled:

`SIGNATURE_AND_OWNER_LOOKUP_SHADOW_PASS_REPLAY_GATE_HELD`

The existing bridge surfaces only this status and a coarsened, privacy-reduced summary. Flags explicitly remain false for production key trust, durable replay ledger, source admission, commercial buyer intent, revenue, prediction accuracy, money, dispatch and outbound. Empty signed batches are not zero real-world buyer events.

## Security/accuracy limitations to preserve

- These are purely unit-test signature and delegate-contract checks; **no real key or live source owner callbacks have been provisioned or independently exercised**. A test callback returning true is not evidence of a legitimate source, source licence, tenant membership, consent or authenticated production data.
- Plain SHA-256 of guessable personal/customer/company keys is **pseudonymous**, not properly deidentified or tenant-isolated by itself. Original Security/Data Cloud owner must approve purpose-scoped secret-keyed digests or other safe canonical pseudonyms before any real sensitive evidence intake.
- No durable nonce reservation, atomic compare-and-commit, anti-replay persistent DB journal, erasure propagation, source-custody signature revocation or emergency reader kill switch has been integrated. An immutable signed envelope alone cannot prevent replay.
- Verifying that the source system issued a message still does not prove *the underlying assertion* is true; an authentic weather alert or permit does not become an authenticated customer buying request; an accepted CRM deal does not become recognised revenue. Quant/Science separate calibration and real economic outcomes remain unchanged.
- No model retraining, confidence inflation, source scraping, CRM contact or payment activity. A scientifically useful forward cohort still needs pre-outcome registration, holdout review and paired authentic outcomes.

## Next exact owner tasks

**Data Cloud + Security:** identify a rights-cleared, permitted **single original source** and independently provision a scoped issuer/signing/identity/binding/revocation capability with key rotation, an atomic durable nonce replay gate, and explicit read-only verified custody. No secret keys should enter general chat or files.

**Buyer Acquisition / Smart CRM owner:** after checks, prepare one narrow permitted authentic buyer-enquiry summary with no raw email/phone/names. Do not change mailbox, suppression, attribution, live outreach or tenant CRM logic.

**Chief/ASTRA/Core + Predictive/Scientific + Risk owner:** review minimal diff and signed path; merge via original owned clean release process only after wider original-owner regression repair and rollback approval. Never promote from fixture assertions to production truth.

## Engineering evidence

Focused signed/fusion/original bridge tests passed **92/92** including a demonstrative cross-batch replay limitation test. Expanded original-owner source/custody, CRM auth and reply qualification, tenant binding, PRIME, Quant, economic-signal, buyer-state and Founder source regression: **347 tests passed with one inherited Starlette deprecation warning**. This is a scoped regression suite, **not** a full repository-wide pass. Known inherited `tests/test_economic_signal_materializer.py` symbol import failure from the earlier parent remains external to this feature unless independently resolved.

Original research branch is intended to be committed and pushed for original owner review, never directly deployed.

**Original production `/srv/empire_os`, original EmpireDB, source service, live CRM, ASTRA routing, mailboxes, payments and trading stay unchanged.**
