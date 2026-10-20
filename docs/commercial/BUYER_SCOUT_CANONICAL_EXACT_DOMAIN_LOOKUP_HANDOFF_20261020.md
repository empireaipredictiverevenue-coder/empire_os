# Buyer Scout — canonical exact-domain lookup handoff

20 October 2026, owner-side isolated research worktree.

## Added
- Source-bound owner queue now builds a separate exact-domain canonical lookup request document.
- Input is only the existing 7 eligible first-party company websites; 2 held websites and 7 historical permit business-name hypotheses are excluded.
- The output includes stable request IDs, company domain, site SHA256, location, vertical, and minimal task reference.
- Explicitly requests canonical prospective company website, buyer domain, prior relationship and suppression examination by the authorised canonical EmpireDB owner.
- No email addresses, contacts, phone numbers, raw query results, hidden source body or sales claims.
- Every result is marked UNKNOWN_NOT_CHECKED / AWAITING_AUTHORIZED_OWNER_EXECUTION.
- This worker does **not** access EmpireDB or assume a negative match is contact clearance.

## Output
Private, atomically written 0600 file:
runtime/buyer_acquisition/a2a_canonical_domain_lookup_requests_latest.json

## Acceptance and remaining gate
- Source is validated against original website source hashes and offline parser receipts.
- Existing hourly A2A Buyer Scout evidence review regenerates this scoped request list.
- Only an authorised EmpireDB CRM owner can perform fresh canonical reads, including tenant/RLS and suppression contract.
- No database-wide dedupe is claimed. No CRM writes or outreach authorisation.
- A buyer company can be called qualified only after independent evidence of actual lead buying need, buyer identity, budget, service territory and commercial terms; a website cannot establish these.
- Brave search remains transient/metered; its results are not saved into this queue.
- No edits were made to the active dirty /srv/empire_os checkout.

## Verification
```bash
cd /home/ubuntu/empire_worktrees/resilient_buyer_scout_business_release_996946a3
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_buyer_scout_canonical_lookup_contract_20261020.py \
  tests/test_buyer_scout_a2a_source_binding_queue_20261020.py \
  tests/test_buyer_scout_a2a_research_intake_20261020.py \
  tests/test_buyer_scout_reconciliation.py
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m \
  scripts.review_buyer_scout_a2a_source_intake_20261020 \
  --read-only-owner-review --write-local
```
