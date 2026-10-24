# EmpireOS PRIME — First Authentic Buyer-Intent Receipt Path

**24 October 2026 | ORIGINAL Predictive Cloud / PRIME / Buyer Acquisition / Data Cloud | OBSERVE only**

**Research branch:** `feature/prime-universal-evidence-fusion-20261024`.
**Original parent:** `21ec7afca590bea1a455ef29319870915bd994bb`.

This handoff closes an engineering gap but **does not assert the first true authenticated buyer enquiry has been admitted**. It is not a new platform, agent, database, CRM, mailing pipeline, source licence, production feed or financial integration.

## What original owner evidence was actually inspected

The original root `/srv/empire_os` remains on branch `agent/data-cloud-wave4`, HEAD `b7df2cf91`, with ~241 original other-agent uncommitted changes. **None were modified.**

Read-only on 24 October 2026 (UTC around 01:06–01:13):

- Original `commercial_buyer_source_health.inspect_original_buyer_health`, reading only the two existing aggregate owner snapshots:
  - Buyer Capacity: FRESH
  - Buyer Scout quality: FRESH
  - Status: **`BUYER_CONTRACT_CAPACITY_EVIDENCE_HOLD`**
  - Provider reports **no independently verified buyer purchase**, binding commercial terms or recognised revenue from these sources.
- Original protected Gmail buyer-message index (using the original `scripts.import_connected_gmail_buyer_metadata._private` restricted reader, no Gmail API call):
  - **5 bounded existing warm source threads**
  - **93 indexed source messages**
  - **28 total semantic event codes**, NOT 28 different inbound replies, verified enquiries, unique buyers, accepted orders or purchase intent
  - Snapshot fresh (age under one hour at observation)
  - No raw message bodies, email addresses, contact names, subject lines, provider message IDs, OAuth credentials, signed secrets or customer data emitted
  - No source signer, independent contact/tenant proof or durable replay verified; **zero claims made** about the number of genuine enquiries.
- Canonical original read-only `scripts/probe_reply_identity_lineage.py` requires `EMPIREDB_DSN`. That credential was **not present** in this operator session. No secret discovery or bypass attempted, and no canonical provider/tenant/contact verification completed.

The counts above describe an **observed original owner metadata index**, not commercial intent. No generic first-party webpage claims or inferred buyer capacity are eligible for PRIME buyer-intent admission.

## New engineering

### 1. Original strict first-buyer-enquiry gate

`empire_os/prime_original_buyer_intent_preflight.py`:

- Uses the existing `PrimeOwnerSignatureVerifier` instance, with a single original **`buyer_acquisition` / `EXPLICIT_ENQUIRY`** signed envelope.
- Checks the exact pre-existing owner schema, read-only source and permitted purpose; blocks `GENERAL_INTEREST`, `REALIZED_OUTCOME`, externally sourced webpage purchase claims, added financial/outbound authority, conflicting support links or retrospective prediction metadata.
- Requires an **independently original-owner managed read-only lookup**, keyed by tenant and prevalidated event/entity/source digests. This callback must come from the original authorised provider/Conversation OS/EmpireDB owner, never from a user-supplied source claim.
- Requires returned proof fields for exact tenant, source, event, entity, origin, causal provider receipt time, review time, original inbound direction, provider authentication, original message/thread parent, canonical contact+tenant binding, intended research-use rights, suppression/deletion clearance, human review of a genuine enquiry, and read-only provenance.
- Rejects unauthenticated signers, tampered source digests, wrong tenants, unsupported classification, false/unknown proof fields, malformed timestamps, extra PII, reader failures and unsafe owner health reports.
- **All positive test callbacks remain only structurally reconcilable.** Response reports `SIGNED_OWNER_AND_INBOUND_PROOF_CALLBACK_PREFLIGHT_ONLY_RELEASE_HELD`, always retaining `buyer_intent_independently_verified=false`, `source_admission_authorized=false`, `durable_atomic_replay_prevention_verified=false`, `recognized_revenue_cents=null`, `execution_authority=none`. This prevents test callbacks from being mistaken for real owner verification.

### 2. Existing original PRIME bridge

`empire_os/predictive_revenue_brain_bridge.py` now optionally accepts:
- `original_single_buyer_enquiry_verifier`
- `original_buyer_source_health`

This path requires the **same** original pinned signed-owner verifier and **exactly one** original signed envelope. Bare buyer-capacity snapshots cannot authenticate an enquiry and are explicitly refused without a signed-source path. The original bridge outputs **status only**, not email data, prospect identity, original event digests or revenue. Other original CRM, Quant, forward journal, signed source, Economic Memory and Chief/ASTRA contracts remain unchanged.

### 3. Repeatable read-only source availability command

`scripts/review_prime_original_buyer_feed_readonly_20261024.py`:

```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024
PYTHONPATH="$PWD:$PWD/tests" /srv/empire_os/.venv/bin/python -B \
  scripts/review_prime_original_buyer_feed_readonly_20261024.py --root /srv/empire_os
```

The command reads only the original private index and existing capacity/Scout aggregated snapshots. It checks original source schemas, private file permissions, bounded thread/message counts, duplicate identifiers, semantic event-code allowlist and freshness. **Only aggregate counts and negative authority flags are printed**; no message bodies, personal contacts, credentials or private identifiers are returned. This is **read-only observation**, not a mail poll, Database query, signed source adapter, provider authorisation or ingestion. It never modifies the existing index.

## Definitive next original-owner prerequisites before one genuine receipt can be admitted

1. **Original Buyer Acquisition / Gmail / Conversation OS owner:** nominate **one existing lawful inbound reply** that truly contains a direct buyer enquiry (not an auto-reply, sent message, marketing page, supplier statement, lead prospect or classifier suggestion). With a permitted private source reader, independently establish the genuine original provider message/direction and RFC parent, uniquely bound original conversation, correct tenant/contact, non-suppressed and non-deleted state. **Do not expose the body to PRIME.**
2. **Security + Data Cloud:** approve source-use rights and retention/erasure, purpose-scoped cryptographic pseudonyms, trusted Ed25519 issuer identity and key rotation, exact source custody signature, original owner scope and revocation lookups.
3. **Original EmpireDB + Security:** deploy/approve the separately proposed **atomic, durable nonce/event reservation** and first-write readback under canonical roles, minimum grants, immutable uniqueness and independent audit. This is **not yet deployed**. The proposed SQL in the earlier PRIME owner document remains unapplied.
4. **Original Predictive Cloud / Science / Quant:** review just that single authenticated privacy-minimised source receipt, then independently log pre-outcome predictions and NO_TRADE/NO_OPPORTUNITY/negative observations. Do not train or score revenue without later owner-authenticated commercial outcome evidence and real costs.
5. **Core / Chief of Staff / ASTRA:** reconcile existing production owners' changes; run complete original release gauntlet, tenant/rights checks and rollback, then authorise a precisely scoped read-only adapter. No public or financial activation by default.

Without all required original authority, **do not call it verified buyer intent**. A 5-thread/93-message/28-event snapshot is neither a real prospect count nor evidence of profitable trading or economic outcomes.

## Reproducibility

Focused single-buyer-source + signed gateway + original brain bridge and read-only source probe: **91 passed**.

Full related scoped original regression expanded to include original Conversation OS reply binding/linkage, buyer source health, company claim provenance, CRM auth, Quant, PRIME signed receipt, original first-write and forward journal: **516 passed with one existing Starlette deprecation warning**. **Not a whole-repository test success**. Previous original materializer `ECONOMIC_SIGNAL_SOURCE_KEYS` import issue remains an existing owner integration blocker and was not patched here.

The source-availability probe was executed on the original root with fresh aggregated owner data; its output status was `FRESH_ORIGINAL_OWNER_METADATA_ONLY_NO_VERIFIED_BUYER`. It did **not** produce an authenticated buyer receipt.

**One EmpireOS. One original EmpireDB. One Smart CRM. One Predictive Cloud / PRIME. Production, owner email, outbound, payments, model learning and trading remain unchanged.**
