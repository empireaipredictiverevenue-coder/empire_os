# Empire A2A — Source & Buyer Scout signed research pickup

Date: 20 October 2026
Branch: feature/a2a-commercial-signal-mining-20261020
Owner: empire.a2a.commercial_signal_miner.v1

## Scope

Extend the previously built hourly founder-prompted targeting research with a
practically inspectable local owner inbox and cryptographically verifiable
research-acknowledgement protocol.

This is not live task dispatch, not lead creation, not agent registration in
production, and not customer contact.

The existing Community Intent team already rotates compliant public research
sources every 15 minutes, while Buyer Scout has its own existing research
cycles. No second collector or competing buyer prospecting timer was created.

## Implemented and operating

- empire_os/a2a_owner_research_protocol_v1.py
  - splits 6 target research tickets into 3 Buyer Scout and 3 Community Intent
    requests with stable IDs, SHA-256 content digests and fixed source scope
  - keeps permission fields research-only and refuses authority escalation
  - verifies receipt signatures with Ed25519 and owner-specific trust keys
  - binds each receipt to the exact original ticket hash and responsible owner
  - rejects unknown ticket IDs, forged claims, stale receipts, missing source
    receipt hashes, owner/key mismatch and same-batch repeated nonces
  - distinguishes accepting a research assignment from proving buyer identity
    or commercial purchase intent
- empire_os/a2a_owner_receipt_intake_v1.py
  - checks strict filename, file count, file size and symlink controls
  - requires root-owned, non-group/world-writable public trust configuration
    at /etc/empire_ai_a2a_owner_public_keys_v1.json (NOT installed)
  - a worktree-writable acknowledgement JSON cannot self-certify trust
  - the owner-receipt directory is worktree-local
- empire_os/a2a_owner_pickup_change_tracking_v1.py
  - tracks new, changed, unchanged and retired requests across hourly cycles
  - exact same six current requests do not count as six new discoveries
  - preserves existing request documents for owner pickup; no automatic sends
- scripts/inspect_a2a_owner_pickup_20261020.py
  - can read just Buyer Scout or just Community Intent requests on EmpireOS
  - returns proposed bounded research queries, source IDs and acceptance
    requirements, without editing any owner system

Hourly source-to-outbox-and-receipt-observer flow:

  Founder prompts
      -> live owner Community Intent / Buyer Scout read-only snapshots
      -> 6 target-specific PREPARED_NOT_DELIVERED research tickets
      -> owner_research_pickup_v1.json
      -> owner_pickup_change_tracking_v1.json
      -> owner_signed_receipts_review_v1.json

No credential, social post author identity, raw post text or company contact
details are added to the ticket packets.

## Current runtime status

3 founder target profiles: Tampa roofing, Little Rock HVAC, NYC construction data
6 owner-review pickup requests (3 per owner)
0 actual owner jobs dispatched
0 signed owner receipts received
0 production owner trust public keys installed
0 independently verified new buyers
0 CRM changes, public posts, contact messages, ads, or payment actions

The pickup is accessible to authorised operators on the existing EmpireOS host:

cd /home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.inspect_a2a_owner_pickup_20261020 \
  --owner buyer_scout --detail

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.inspect_a2a_owner_pickup_20261020 \
  --owner community_intent --detail

These commands do NOT execute the suggested searches. Existing owner agents
should inspect requests, confirm source permissions and handle approved research
within their existing job orchestration.

## Production owner acceptance work

The A2A identity owner must provision independently managed keys for
buyer_scout and community_intent. The signed receipt schema is:
empire.a2a.owner_research_receipt.v1

Fields (one per ticket):
schema_version, ticket_id, ticket_sha256, owner, status,
occurred_at, nonce, source_snapshot_sha256, evidence_reference_ids,
no_external_outbound, execution_authority, signature_b64url

Permitted signed statuses:
- ACCEPTED_FOR_RESEARCH
- DECLINED
- EVIDENCE_REVIEW_AVAILABLE

Ed25519 signing bytes are canonical JSON, sort keys, compact separators,
all fields except signature_b64url. Accepted receipts still do not prove
financial transactions or buyer intent. Verified evidence/source decisions
must be independently read back from the source owner's system.

Trusted public configuration must be installed by the A2A identity owner as
a root-owned file, with schema version empire.a2a.trusted_owner_keys.v1 and
trusted_owners mapping from exact owning identities to base64url public keys.
Private keys should remain in their relevant agent's authorised secure key
store and must never be copied into ChatGPT or committed.

After production A2A trust activation, add durable cross-run replay/sequence
protection at the owning identity service. Current receipt review prevents
same-batch nonce repetition, but does NOT provide a persistent, authenticated
replay registry across process restarts. It never triggers executing actions,
so no authorization relies on it today.

## Next meaningful integration

1. Community Intent agent owner: accept the three source-topic requests and
   run permitted research via the existing public RSS/approved data collector.
   Do not claim its overall Reddit feed success means Tampa evidence is present.
2. Buyer Scout owner: ingest the three scoped query requests, reuse canonical
   dedupe/identity gates, classify verified company buying requirements and
   obtain legal/commercial review before contact.
3. Both owners: return independently signed bounded receipts and original
   source snapshot references for our A2A miner to review.
4. Campaign/Finance owners: separate approval for any real messaging, campaigns
   or invoices once actual buyer requirements are evidenced.

No files in /srv/empire_os, its source owners, their databases or production
services were changed; only the isolated research branch and its own local
report files are modified by this implementation.
