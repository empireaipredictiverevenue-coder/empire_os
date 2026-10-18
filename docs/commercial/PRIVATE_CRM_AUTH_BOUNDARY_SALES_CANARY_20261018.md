# Empire AI — public enquiry to private CRM access-boundary proof
18 October 2026 | Read-only first-party observability, no test buyer

## Existing diagnostic correction
The canonical scripts.probe_first_party_sales_http_readonly previously did
not parse arguments. Invoking it with --check-private-inbox silently ran
the standard public GET-only probe and printed the public-surface status,
which could be mistaken for a private CRM check. The missing option has
now been implemented in the same existing script; unknown options fail.

## What --check-private-inbox now actually checks
The original public read-only probe remains unchanged for default use:
it GETs the public commercial / Predictive Revenue pages and existing
compiled JavaScript to verify the exact intake routes, and GETs the two
approved commercial offer/product catalogues without submitting forms.

The opt-in --check-private-inbox mode additionally GETs only these
fixed local first-party CRM URLs (NO redirects, cookies or credentials):
- http://127.0.0.1:8783/health
- http://127.0.0.1:8783/v1/revenue-crm/prospects
- http://127.0.0.1:8783/v1/revenue-crm/buyers

It requires the exact existing CRM pilot service identity, health mode
APPROVED_READ_ONLY_PILOT, disabled outbound/payment/database provisioning,
and anonymous 401/403 denial from both protected lists with private
no-store, frame-deny and content-sniffing protection headers. Error bodies
are discarded and never logged. The server remains private loopback.

The successful status is PRIVATE_CRM_AUTH_GATE_READY_NO_RECEIPT_READ.

Fields explicitly say founder_login_authenticated=false,
private_crm_customer_rows_read=false,
canonical_sales_acquisitions_checked=false, and
founder_crm_delivery_verified=false.

This tests access and infrastructure, not buyer acquisition. The founder
already has a working Workspace login; no sign-in or customer row read
was attempted. Passing does NOT mean real enquiries have been received.

## Real read-only production observation
The existing public canary verifies 2 pages, 2 compiled intake paths,
10 commercial offers and 5 Predictive Revenue products. Private CRM
health and both anonymous access denials were verified. No outbound,
customer POST, payment or DB write occurred.

## Independent next proof
For a real buyer, preserve explicit response consent and verify exact
canonical EmpireDB immutable acquisition receipt against the tenant-
scoped authenticated founder CRM reader. Existing aggregate reconciliation
is scripts.reconcile_founder_sales_handoff_aggregate_readonly and
must remain a privileged, least-privilege one-shot task. Aggregate counts
alone cannot prove an individual enquiry. Never create a pretend buyer
to make this gate turn green.

This patch adds NO database migration, new service, task, email, source-
attribution cookie, approval bypass, secrets, API publishing or live site
changes.
