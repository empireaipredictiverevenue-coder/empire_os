# Empire AI — Genuine first-party enquiry receipt path

**20 October 2026** · Scope: LIVE read-only route checks and TEST-ONLY in-memory HTTP contract. The actual first customer receipt remains unproven.

## What is already live

The public `https://empire-ai.co.uk/buy` product-to-proposal handoff is published and browser-tested. Choosing a currently approved product and navigating to `/commercial?product=competitor_search_gap#commercial-enquiry` preselects that product in the existing commercial enquiry form. The public bridge preserves the existing checkout and premium-brokerage area, and it does not submit forms.

The deployed public gateway registers `POST /v1/checkout/commercial/interests`, and the deployed private checkout app preserves `POST /v1/commercial/interests` after the premium-brokerage systemd entrypoint. Both were **GET-probed** without touching submissions: `405 Allow: POST`. Same-origin, JSON, size and ephemeral rate controls remain intact.

The checkout app's `record_founder_led_interest` uses the existing canonical `empire_os.sb.request_json` compatibility boundary backed by **EmpireDB**, invoking `/rest/v1/rpc/ingest_prospect_atomic`. Independent SQL metadata confirmed `empiredb_app` may execute `ingest_prospect_atomic(jsonb,jsonb,text,text[])`. This permission check is **not** a live database write/connection test.

## Full HTTP handler test — real code, no real customer

`tests/test_agency_public_enquiry_to_empiredb_contract_20261020.py` runs the **real production public gateway, checkout API and domain intake code** through a local in-memory ASGI HTTP transport. Its one stub is the final EmpireDB RPC boundary; the stub does not connect to EmpireDB or generate a live record.

The synthetic, clearly marked `.example` company and email simulate a consented `competitor_search_gap` enquiry at $199 with approved, nonbinding terms. It proves that real application handlers:

- retain the governed product code, one-time USD price reference, specific response consent and anti-repeat ingestion key;
- construct one `ingest_prospect_atomic` request with `source=first_party_commercial_sales_enquiry`, no automatic outbound, payment or binding terms;
- return the domain's `commercial_enquiry_recorded`/FOUNDER_REVIEW contract after the stubbed RPC receipt;
- reject missing consent, spoofed Origin, honeypot spam fields and unapproved product codes before any RPC reaches the stub.

**Do not claim this as a real buyer, successful production DB insert, correct tenant attribution, delivered email, verified service fulfilment, or payment.** It's software-contract proof only.

## First real buyer → CRM owner acceptance

When a genuinely interested, specifically consenting buyer uses the real form:

1. Existing checkout owner verifies the actual production success status and canonical `prospect_acquisitions` immutable source/consent receipt (PII-private).
2. CRM owner validates identity, source and legitimate company entity mapping. The existing native SQL `ingest_prospect_atomic` only writes `prospects`, `prospect_identity_claims` and `prospect_acquisitions`; it does not itself create a `prospect_entity_links` record or a `tenant_business_entity_bindings` record. No business triggers exist on the three ingest tables.
3. The tenant-scoped CRM's `empire_crm_prospect_authorized` (migration 040) requires **exactly one** evidenced, active link plus an appropriate valid tenant binding. The existing CRM/identity owner, not a web-intake agent, must prove its reviewed mapping process and verify the real record appears in the correct authenticated `/prospects` view. No automatic domain-only founder binding and no relaxation of tenant RLS.
4. Existing Sales owner reviews the exact opt-in and all suppression flags before any reply. Specific response consent is **not** ongoing marketing or blanket outreach consent.
5. Finance/Checkout owners own separately accepted terms, settlement, costs and fulfilment. A $199 catalogue price is not cash received or product shipped.

Current founder-only canonical count-readback (with privacy-protecting SQL) showed **0** commercial first-party acquisitions and **0** Predictive Revenue acquisitions in the two queried sources. This is not evidence of zero traffic/demand or other absent channels.

Existing owner issue: https://github.com/empireaipredictiverevenue-coder/empire_os/issues/72

## Existing Workspace buyer mailbox monitoring status

The existing `empire-buyer-gmail-evidence.timer` runs successfully and its last three steps (poll, local metadata importer and relationship reconciliation) report PASS and no outbound authority. However its relationship reconciler reports `gmail_snapshot_fresh=false`, with **partial** newer updates. The current priority payer review shows 2 monitored threads, 0 new inbound header candidates and no verified full mailbox coverage. It is incorrect to infer no inbox replies everywhere until the original mailbox owner completes a full authenticated scan.

No new timer, duplicate Sales worker, email sender, customer record, pipeline table, live database write or public route was created by this research/QA task.

## Verification commands

```bash
cd /home/ubuntu/empire_worktrees/agency_reply_first_video_20261020

# Pure synthetic/in-memory — no production database or customer actions
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
 tests/test_agency_public_enquiry_to_empiredb_contract_20261020.py

# Existing authenticated founder-operated count-only readback, when authorised
cd /srv/empire_os
sudo -n .venv/bin/python -B -m scripts.probe_canonical_sales_intake_aggregate_readonly

# Existing Workspace Gmail relationship read-only summary, freshness is explicit
PYTHONPATH=. .venv/bin/python -B -m scripts.reconcile_buyer_email_relationships
```
