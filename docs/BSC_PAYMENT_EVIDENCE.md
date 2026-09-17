# BSC payment evidence — OBSERVE-only preview

The adapter in empire_os/bsc_payment_evidence.py reads approved requests from
canonical Supabase and independently calls the chain verifier. It does not write
evidence, recognize revenue, activate a buyer, create an invoice, or deliver.

The request binds a buyer UUID, fulfilment order UUID, approved USDT amount,
payer and treasury, terms fingerprint, expiry, and minimum payment block.
Amounts are selected as text to avoid JSON floating-point loss.
Existing ledger matches are rejected before chain verification.
These lookups are advisory, not a race-safe reservation.

The existing empty migration scaffold now contains a DRAFT schema.
Do not apply it to production yet. It grants service_role SELECT only.
Unique transaction_hash and request_id constraints are the planned reservation
boundary. A whole transaction may pay only one request in this first version.

Remaining gates:
1. Validate the draft in disposable Postgres, including RLS and concurrent inserts.
2. Add a human-approved request creation workflow that freezes commercial terms.
3. Implement/test an atomic restricted recorder that rechecks approval, order,
   terms, expiry and fresh chain evidence under lock and handles retries safely.
4. Replace the legacy verified_payment branch in migration 006 before activation.
5. Review revenue recognition separately; USDT amount is not automatically GBP/USD.
6. Obtain explicit approval for live migration and any production activation.

No runtime route, queue handler, service, or execution-mode change is included.
The adapter fails closed if the draft tables are absent. No SQLite fallback.
