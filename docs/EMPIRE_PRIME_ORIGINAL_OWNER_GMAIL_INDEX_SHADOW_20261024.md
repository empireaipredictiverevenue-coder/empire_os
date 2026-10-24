# PRIME — Original Gmail Buyer-Partner Metadata Shadow Integration

**24 October 2026 — OBSERVE / original EmpireOS only / original production unchanged.**

## Delivered, not a new product

- `empire_os/prime_original_partner_index_adapter.py` is a pure in-memory adapter from **existing, permissioned original Buyer Acquisition Gmail metadata index** and **existing original Buyer Relationship source** to original PRIME's `review_partner_signal_codes` + `founder_partner_signal_status`.
- `scripts/review_prime_original_partner_semantics_readonly_20261024.py` loads only the two already present protected private owner snapshots through the original `_private()` reader, and calls the adapter. It does not access Gmail/OAuth/EmpireDB directly; never writes snapshots, new credentials, Smart CRM, sender queues or production services.
- It enforces exact original schemas, original owner source/scope, absence-of-stored-message-body declaration, currentness (up to three hours), complete original known-thread/partner linkage, no duplicated provider IDs, bounded metadata, exact existing Buyer Acquisition code vocabulary, non-DRAFT/non-SPAM original inbound vs outbound labels, per-code direction consistency, and bounded UTC message observations.
- The original Gmail poll stores UTC message timestamps *without an offset*. The adapter accepts precisely its original `YYYY-MM-DDTHH:MM:SS` source contract and normalises internally to UTC. It rejects arbitrary naïve timestamps from other origins.
- On each review, a fresh **in-memory 256-bit key** HMACs original provider message/thread identifiers for temporary multi-code deduplication. The key and opaque HMACs are not persisted or returned. This fingerprinting DOES NOT assert canonical proof of sender identity, source rights or replay prevention.
- The Founder aggregate suppresses category cells below five, never shows individuals or raw messages, and never treats event codes as direct buyer enquiries. The original Research Bridge's existing optional `original_partner_signal_codes` path remains separately controlled by its caller; no invented tenant identity is used.

## Real read-only source observation

The command was run against `/srv/empire_os` (without changing its working files):

```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  scripts/review_prime_original_partner_semantics_readonly_20261024.py --root /srv/empire_os
```

The original protected snapshot was fresh (8 minutes old during this observation) and showed:

| Aggregate | Count | Commercial interpretation |
|---|---:|---|
| Existing warm buyer-partner threads indexed | 5 | Not five verified buyers |
| All indexed source messages | 93 | Not 93 inbound buyer replies |
| Original semantic-code occurrences | 28 | Not 28 direct purchase enquiries |
| Inbound code occurrences | 9 | Not verified intent, unique buyers or money |
| Outbound code occurrences | 19 | Empire AI's own reported requirements; **NOT** received buying signals |
| Largest category | OUTBOUND_REQUIREMENTS_NOT_BUYER_RESPONSE (15–19 range) | Founder privacy-banded research category, not profit |

This is real original owner **metadata observation**, not original source-owner signing. All outputs explicitly hold `real_buyer_intent_verified=false`, `signed_owner_receipts_admitted=false`, `atomic_nonce_replay_registry_verified=false`, `realized_revenue_cents=null`, `database_writes=false` and `outbound_sent=false`. Missing private snapshots yield **UNKNOWN/HOLD**, never a manufactured count of zero buyers.

**No original source addresses, message IDs, sender names, raw email bodies, message subjects, access keys or tenant data are copied to GitHub or Founder output.**

## Source-owner release path

1. Original Buyer Acquisition / Gmail owner: certify the existing metadata reader's evidence provenance, legal message processing, original inbound vs sent labels, deletion requests and thread identity ownership. Verify any direct consumer/buyer intent **independently** against original provider/canonical conversation, not classifier codes.
2. Original Data Cloud + Security: authorise source rights, tenant binding, approved use, purpose-keyed identifiers, signed Ed25519 issuer credentials, source custody and revocation policy; never infer these from the index.
3. Original EmpireDB/Security: complete separately reviewed atomic persistent replay reservation and first-write guarantees. Existing branch's migration proposal is NOT an applied migration; no live source admission.
4. Original Predictive Cloud/Quant/Science: preserve inbound/outbound separation and negative, unresolved, abstained evidence in prospective forecasts; never convert technical progress or partner-interest codes into paid revenue.
5. Chief of Staff/ASTRA/Core: merge only following original production owner approval, complete gauntlet and rollback evidence. Production remains unmodified.

## Test scope

- 23 new pure adapter tests exercise one-run anonymised counts, correct owner source join, duplicates, manipulated partner label, missing source, stale/future, spoofed direction, draft/spam, source code drift, untrusted bodies, malformed timestamps and fail-closed hold.
- Original classifier tests still prohibit inferred buying, outbound and financial authority. **557 scoped regression tests passed with one inherited Starlette deprecation warning**, including original PRIME, buyer-source, Conversation OS, CRM signed auth, Quant, and original Data Cloud source custody. This is **not** a complete repository regression claim. The feature grants no authority.

**One EmpireOS. One original EmpireDB. One Smart CRM. One Predictive Cloud / PRIME.**

## 24 October continuation — temporal denominator and freshness hardening

The existing prime_original_partner_index_adapter.py was upgraded IN PLACE. No additional service, database, or authority role.

- Differentiates a fresh metadata index poll from message event dates: a newly collected index must not revive old commercial evidence.
- Reconciles all indexed message-direction denominators: original INBOX, SENT, excluded DRAFT/SPAM/TRASH, and unclassified. These are owner-provided labels, NOT independent provider authentication.
- Separately counts messages with recognised codes and individual code occurrences. A message with no semantic code is UNKNOWN, not a verified negative or nonbuyer.
- Four mutually exclusive event age cohorts: 0_7_DAYS, 8_30_DAYS, 31_45_DAYS and OLDER_THAN_45_DAYS, split into inbound versus outbound, and cross-checked for exact reconciliation.
- Rejects post-collection messages by more than five minutes, even if uncoded; rejects malformed original UTC wall-clock timestamps, future observation dates and duplicate message labels.
- Founder output suppresses small recent signal cells (null if below five). Historical signals do not imply current buyer demand. The internal owner diagnostic contains more detailed aggregates and must not be exposed as a public API.

### Observed existing protected original source, read-only

| Aggregate | Count |
|---|---:|
| Indexed source messages | 93 |
| Messages carrying one or more semantic codes | 23 |
| Uncoded messages, unknown not negatives | 70 |
| Original SENT messages | 54 |
| Original INBOX messages | 37 |
| Excluded drafts/spam/trash | 2 |
| Total semantic-code occurrences | 28 |
| Inbound code occurrences | 9 |
| Outbound code occurrences | 19 |
| Code occurrences 0–7 days old | 3 |
| Code occurrences 8–30 days old | 23 |
| Code occurrences 31–45 days old | 2 |
| Older than 45 days | 0 |

Of the three last-seven-day code occurrences, two were recorded in inbound messages and one in outbound messages. None is authenticated as direct buying intent by this review. All amounts are source-owner metadata observations, not uniquely verified people, buyers, lawful processing rights, settled orders, or revenue.

### Validation and security boundary

New tests check denominators and multi-code messages, stale messages in fresh polls, post-collection time paradoxes, missing or unrecognised labels, draft/spam exclusion, invalid time on uncoded records, small Founder group suppression, and unchanged no-buyer/no-outbound authority.

564 scoped regression tests passed, with one inherited Starlette deprecation warning. This is not a full repository test claim. No external emails, trade or payment executed, source credentials read, production schema altered, or production process restarted.

Original Buyer Acquisition / Conversation OS + Security + original EmpireDB owners still control genuine provider-to-contact/tenant readback, source licence/purpose and deletion rules, signing custody, atomic durable replay protections, and release. Until those are independently authorised and observed, original PRIME buyer intent remains on HOLD.
