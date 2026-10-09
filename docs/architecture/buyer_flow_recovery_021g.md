# Buyer Flow Recovery 021G — closed-loop evidence measurement

## Purpose
Close the gap between the established read-only Revenue Flow Meter and
existing evidence recovery capabilities. Do not create yet another buyer
agent, separate scheduling loop, database migration or outbound route.

## What is integrated
- Search Fabric Buyer Scout rejects a small explicit allowlist of **known
  discovery infrastructure domains** (currently `search.google` and
  `cybo.com`) from search candidate promotion. These are a search service
  and public business directory respectively, not reliable proof of a
  company buying lead inventory. Other companies and intermediaries
  continue through the existing evidence review gates.
- Scout exposes the number of unique excluded search-result domains;
  the Flow Meter reports that as *filtering*, not a commercial outcome.
- The existing Revenue Flow Meter produces two read-only, bounded outputs:
  ranked **holding-area blocker priorities** with the existing capability
  needed to resolve each block; and up to five exact-company Scout
  **evidence investigation suggestions**.
- These are *research recommendations*, not autonomous re-probes, tasks,
  approvals, verified buyers or commercial permissions.
- The existing Flow Meter private history now stores up to 96 samples,
  each with bounded SHA-256 domain fingerprints and three booleans:
  first-party direct-purchase statement, strict person/contact binding,
  canonical/first-party identity correlation.
- Comparing two separate Scout runs counts only **identical companies
  present in both runs** and records newly verified or no-longer-current
  evidence. It does not claim causation, same-run review conversions,
  sent messages, buyers or recognized revenue.

## Accuracy and prioritisation
Accumulated holding review returns only the first blocker for each queued
record. Its blocker counts are not an exhaustive missing-evidence inventory.
Prioritisation weighs direct-purchase evidence and official-identity
conflicts above generic website quality, but shows both count and weight.
The planner does not promote intermediaries or directories to verified
direct lead buyers. It recommends a partner-specific relationship review
for marketplaces without assuming they purchase third-party leads.

Proof is validated through the existing `buyer_claim_provenance` receipt
verifier and strict first-party person binding decision. A source-page
count by itself is **not** proof of buying intent. Missing/future/stale
source receipts fail closed and do not generate invented improvement.

## Performance and limits
The planner scans at most 100 current Scout records and suggests at most
five source-specific targets; historical domain states carry hashes and
boolean flags only, no emails, phone numbers, names, raw URLs or page bodies.
It adds no network requests. The regular scheduled Buyer Review worker
already refreshes the Flow Meter, so no new timer is installed.

To inspect safely:
```bash
cd /srv/empire_os
PYTHONPATH=. ./.venv/bin/python scripts/inspect_revenue_flow.py
```

All production permissions, suppression, founder approval and USDT-on-BSC
payment gates remain unchanged. Historical domain-hash continuity is not
a buyer-transaction ledger and offers no end-to-end conversion rate.
