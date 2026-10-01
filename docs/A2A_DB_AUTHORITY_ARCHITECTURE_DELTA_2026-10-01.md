# A2A DB Authority Architecture Delta — 2026-10-01

Migration 026 owns the two PostgreSQL RPC contracts already required by the A2A runtime:

- consume_a2a_identity_nonce
- record_a2a_commercial_intent

The migration adds only nonce replay protection and non-binding commercial-intent persistence. Capability roles are NOLOGIN and may execute only their respective RPC. The generic app role and PUBLIC receive no authority.

Commercial intents are permanently constrained to pending_approval with execution_authority=none, payment_authority=false and allocation_authority=false. This migration creates no terms acceptance, allocation, payment, fulfilment, outbound-send or revenue-recognition path.

Dedicated LOGIN roles and passwords are provisioned outside the migration during the founder-approved root activation, then granted exactly one capability role each.
