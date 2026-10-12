# EmpireOS — Founder Sales Enquiry to CRM Visibility Closure

**12 October 2026 — source-to-tenant diagnostic prepared; production writes HELD**

## Verified current position

- The public `/commercial` and `/predictive-revenue` forms call the existing nonbinding first-party checkout/interest intake. Their source functions `empire_os/first_party_sales_interest.py` and `empire_os/predictive_revenue_self_serve.py` invoke canonical `ingest_prospect_atomic`, which creates/reuses prospects and append-only `public.prospect_acquisitions` records. They do **not** also create `prospect_entity_links` or `tenant_business_entity_bindings`.
- The existing CRM's `empire_crm_prospect_authorized` deliberately requires one active, evidenced prospect-to-business entity link and one founder-tenant business binding before a record appears. The authenticated founder-scoped read and all three dedicated login authority checks passed, but the read returned **0 visible prospects**, including 0 commercial and 0 Predictive Revenue. That is **not** proof of 0 globally ingested source records.
- To distinguish an empty sales funnel from an inaccessible one without fabricating production buyers, `scripts/probe_canonical_sales_intake_aggregate_readonly.py` is now staged. It uses an explicit 10-second statement timeout and a **single PostgreSQL REPEATABLE READ / READ ONLY transaction**, aggregates only the two precise first-party acquisition sources, checks source-evidence consistency and the exact founder-tenant linkage predicate from CRM migration 040, and **returns counts only**. It does not expose email, customer, website, business identity, prospect ID, tenant ID, sales narrative, external contact or credential information. It does not send, mutate a link, approve a proposal, provision a new role, read or change a wallet, or restart services.

## One privileged operator read required

The canonical PostgreSQL reader and its configuration are not accessible to the connected unprivileged Remote Commander account. This restriction must remain intact. The following **one-time, read-only local command** must be run by the founder/operator in their Ubuntu shell after reviewing the committed source:

```bash
cd /srv/empire_os && sudo -n ./.venv/bin/python -m scripts.probe_canonical_sales_intake_aggregate_readonly
```

The script requires root only to launch an existing local PostgreSQL `postgres` reader via `runuser`; it uses no network connection, passes no private credentials, and executes only `SELECT` under a read-only transaction. It emits a sanitized JSON document. The user-visible JSON is safe to share in the chat; no database environment file, credentials or raw prospect rows should be posted.

**Do not retry the same privileged command through Remote Commander once its policy denies it.**

## Decision after the exact result

1. `sales_acquisition_rows = 0`: no canonical acquisition evidence for the two exact sources is observed. CRM's 0 visible rows is expected for these sources. **No tenant link mutation is warranted.** Verify one real, voluntary buyer enquiry when it occurs, not a fabricated production test.
2. `sales_acquisition_rows > 0` and `founder_binding_exact_one_rows = 0`: genuine acquisition records exist but none satisfy the founder's tenant visibility policy. Perform founder/private identity review of the original acquisition and real consented company identity. Stage one exact validated `prospect_entity_links` and `tenant_business_entity_bindings` proposal **only if supported by immutable provenance**, backup and separately approved production data changes. Never infer the owner tenant from the buyer's claimed domain alone.
3. `sales_acquisition_rows > 0` and `founder_binding_exact_one_rows > 0`: compare these **candidate** identity bindings to the authenticated CRM read for the same tenant, accounting for distinct prospects, active evidence, RLS policy validity and duplicates. Do not treat aggregate counts as proof of a working founder UI.
4. `source_evidence_consistent_rows < sales_acquisition_rows`: explicitly hold any linking; investigate malformed/missing consent/source evidence before founder assignment.
5. Any `BLOCKED` or `UNVERIFIED` status: stop. Do not change DB grants, automatically contact a person, assign prospects or activate payment.

**Do not guess the result.** Customer/partner readiness and payment/traffic gates are still separate.

## Verification and release gates

- Positive/negative unit tests `tests/test_canonical_sales_intake_aggregate_readonly.py` are evidence-only. They assert exact SQL READ ONLY, no DML/GRANT/ROLE changes, source classes, safe count parsing, unprivileged denial, sanitized driver errors and zero contact disclosure. They use only synthetic count fixtures—not real customer records.
- New source diagnostic is standalone and has no new service, migration, timer, dependency or daemon.
- Live website gateway protection commit `11f67279` is still **not deployed** until an independently approved restart. Neither this diagnostic nor current CRM health automatically deploys it.
- The existing CRM transport module currently has changes belonging to another engineer and must **not** be overwritten or combined with this diagnostic.
