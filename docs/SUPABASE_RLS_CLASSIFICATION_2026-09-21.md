# Supabase RLS / Data API Classification — 2026-09-21

Canonical project: `owbeinlfcfdtwcwrttjy`

Mode: **read-only heuristic classification**. No policy, grant, RLS, function,
view, or schema mutation was performed.

## Result

The current public schema contains **222 tables**.

| Suggested class | Count | Meaning |
| --- | ---: | --- |
| Privileged/operator | 33 | Commercial, payment, outbound, fulfilment, audit, queue or execution state. Should normally be server/service-role only. |
| Tenant-owned candidate | 14 | Contains organization/user/owner style identifiers and likely needs tenant-scoped RLS. |
| Public-read candidate | 11 | Content/search/page-style data that may support a deliberately narrow read surface. Public access is not assumed. |
| Server-only/review | 164 | Internal/legacy/operational tables requiring explicit review before any client access remains. |

## Immediate priority examples

### Privileged/operator

- crypto_payment_requests
- empire_revenue_ledger
- fulfilment_orders
- gtm_jobs
- payout_log
- outbound_intents
- outbound_events
- commercial_terms_reviews
- commercial_outcomes
- bsc_escrow_evidence

### Tenant-owned candidates

- organizations
- operators
- operator_sessions
- buyers
- contractors
- call_logs
- dispatches
- email_drafts
- email_sequences
- inbound_leads

### Sensitive server-only/review examples

- advertisers — contact data, wallet/balance fields
- affiliates — contact and payout details
- ai_closer_decisions — lead identity/contact fields
- carrier_enrollments — contains API-key fields
- carrier_properties — includes policy-number/property information
- compliance_audit_logs — operator/IP audit data
- brain_training_log — prompts/outputs/context
- call/event tables — communication metadata and recording/transcript references

## Policy strategy

Do not solve this with a blanket `TO authenticated USING (true)` policy.

Use four patterns:

1. **Server-only**
   - revoke anon/authenticated grants;
   - service-role/server APIs only;
   - RLS may remain defense-in-depth.

2. **Tenant-owned**
   - RLS enabled;
   - explicit organization/owner binding;
   - separate SELECT/INSERT/UPDATE policies;
   - never trust client-supplied tenant identifiers without identity binding.

3. **Public-read**
   - expose only intentionally public columns/rows;
   - preferably through a narrow view or API;
   - no public write unless independently justified.

4. **Privileged/operator**
   - no anon/authenticated direct table access;
   - operator/service API boundary;
   - audit consequential mutations;
   - payment/revenue authority remains separately governed.

## Next security tranche

The already-staged migration
`20260921123000_high_risk_api_security_lockdown.sql`
handles the seven security-definer views, exposed Pulse materialized view, and
two anon-executable token RPCs.

The next migration should be assembled from **reviewed table semantics**, not
from this heuristic classification alone.

## Gate

This classification is evidence for a production migration review. It does not
authorize applying any database change.
