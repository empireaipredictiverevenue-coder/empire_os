# Empire AI — Predictive Commercial Original Evidence Custody (20 October 2026)

## Scope

This is a bounded, **on-demand OBSERVE-only** continuation of intake release `19023e39`.
It changes the existing Predictive Intelligence worktree only. Existing A2A,
Buyer Scout, Lead Supply, Marketing, Procurement, Finance, Quant and Cloud
departments remain sole owners of their original sources and permissions.
No new collector, agent, queue, database table, signing key, service or timer.

## The integration improvement

`scripts/review_predictive_commercial_requirements_20261020.py` now reads one
bounded intake as exact bytes from the opened regular file descriptor, rejects
symlink/non-regular/oversized/changing files and records their SHA256 fingerprint.
The fingerprint is an **untrusted original file identity**, NOT a customer
signature, permission, approved offer or order. Other existing owner inputs use
the same bounded file reader.

Once the six real planning fields are complete, the operator supplies
`authenticated_original_commercial_evidence_chain`. It checks that:
- commercial revision matches original fulfilment, A2A and eight-owner review;
- Lead Supply country/state/city/industry match the original requirement;
- A2A's industry and city/region match the requirement;
- original owner tickets remain research-only, undelivered and unsigned;
- upstream data cannot self-promote to customer order or commercial execution.

The six explicit held stages are original buyer/customer order; requirement-bound
cryptographic owner acceptance; consented geo-eligible unique supply; accepted
customer price and true costs; original prospective forecast; and original settled
profit plus forecast error. All remain **unverified** on this deployment. A global
sellable count, A2A source-reported replies and Finance aggregate status are
explicitly **not** customer-specific evidence.

A2A cryptographic verification remains in the existing owner's
`a2a_owner_receipt_intake_v1.py` and its root-owned key custody; Predictive
does not duplicate or impersonate that verifier. The A2A existing profile
receipt alone is not an acceptance of a new commercial requirement.

## Real customer next step

An actual founder/customer instruction must supply the original intake's
`country`, `state`, `city`, `industry`, `currency` and
`requested_qualified_leads` before any scoped research can begin.

```bash
nano /home/ubuntu/commercial_requirement.json
~/.local/bin/empire-predictive-observe commercial-intake /home/ubuntu/commercial_requirement.json
```

Editing is an **operator choice**, not performed by this release. Customer
identity, authority, accepted price, ZIPs, lead definitions, data rights,
refunds, settlement, owner receipts and original predictions still require
their respective authenticated source-owner readbacks. Do not enter invented
"receipt" objects in the customer file.

## Reproducible regression and release controls

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_predictive_commercial_evidence_chain.py \
  tests/test_predictive_commercial_requirements_operator.py \
  tests/test_predictive_existing_owner_pickup.py \
  tests/test_predictive_commercial_intake_template.py \
  tests/test_predictive_commercial_intake_readiness.py

bash -n scripts/prepare_predictive_readonly_release_20261020.sh
```

The read-only builder refuses dirty commits, stages a distinct commit-pinned
release, hashes the new custody/evidence-chain code, checks the illustrative
plan remains held, validates blank-intake digest against the exact file and
rejects nonexistent source files. Separate launcher promotion is atomic with
a saved prior launcher for rollback.

## Unchanged authority boundaries

- No default customer, market, supplier quote, qualified lead or inventory.
- No authentication claim based on a locally calculated SHA256.
- No advertising or outbound, RFQs, CRM writes, supplier purchases or payments.
- No inference of settled revenue, gross profit or cloud model calibration.
- No merge or service change to concurrently edited `/srv/empire_os`.
- No read-only owner research report may be treated as original signed consent.

Next implementation dependency: obtain a genuine original scoped requirement;
then existing owner departments supply authenticated customer acceptance,
source-rights/unique-event evidence, prices/costs and prospective predictions.
Only those independent source readbacks can support a future gated commercial
execution design.
