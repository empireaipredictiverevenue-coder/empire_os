# Empire AI Predictive Revenue V4.20 — Three-Pillar Verification & Reconciliation (HELD)

**25 October 2026 | Original EmpireOS | Original EmpireDB | Original Smart CRM | Not trading**

## Design decision

The founder's V4.20 handoff calls for source authorisation, event coverage, two-way settlement reconciliation and three channel readiness tiers. This release implements a **safe, reproducible evidence-claim layer** rather than inventing independent licence or bank verification. Do **not** create a second `empire_tenants`, `empire_opportunities` or `empire_orders` table: original `gtm_opportunities`, `fulfilment_orders`, `buyers`, `bsc_payment_requests`, `bsc_payment_evidence`, V4.18 tenant custody and V4.19 source-lineage remain canonical.

**Migrations 066–071 remain HELD**, and new migration **072 is PREPARED ONLY**, not applied to production. V3.6 production observers and V4.9 live OBSERVE remain unchanged.

## Add-only deliverables

1. `migrations/empiredb/072_predictive_revenue_three_pillar_claims_held.sql`: requires the existing original restricted owner/login/session-tenant infrastructure and V4.19 lineage reader. It creates four small append-only, FORCE-RLS-protected, owner-managed **evidence claim** tables:
   - Source authorisation claims: scoped tenant/source/channel, document and publisher reference digests, bounded network-scope digest, declared consent framework and required consent-artifact digest for TCPA/GDPR/CASL claims, claimed active/expired/revoked state and declared validity. A separate append-only revocation tombstone **overrides an old CLAIMED_ACTIVE record**; no in-place mutability.
   - Channel event claims: one original V4.18 opportunity UUID, tenant, source digest, exact channel, original payload/CDR/tag reference digest, event type and event time; composite FK to source authorisation *claim*. A hash is not evidence of upstream intake completeness.
   - Financial matching claims: one original fulfilment order UUID, tenant, **two distinct** purported remittance/clearing digests, gross and cleared claims in integer minor units, explicit currency, claimed clearing time. The reader checks original order/buyer tenant and amount/currency for exact matching or discrepancies. **These are not authenticated bank receipts, on-chain proofs, refund finality or available cash.**
   - Owner-only append policy, explicit REVOKE ALL from PUBLIC and the original restricted reader on each claim table; no app insert/update/delete/select, no new login or direct reader table permissions.
2. `empire_os/predictive_revenue_v420_three_pillar_audit.py`: the existing Ed25519 signed CRM membership and V4.12 research-twin checks; session-user-controlled original EmpireDB reader; **REPEATABLE READ, READ ONLY** V4.19 and V4.20 snapshot; strict one tenant/one channel/31-day/5,000 opportunity caps, exact source and finance claim-count assertions, currency/amount bounds and fail-closed response sanitisation. Injections and fake connectors never promote source claims to independent proof.
3. `scripts/rehearse_predictive_revenue_v420_three_pillar_20261025.sh` and corresponding Python fixture: real disposable PostgreSQL18 test of migration chain 067–072, owner-only append-only claims, exact source and channel matching, mismatch detection, direct table SELECT denial, cross-tenant rejection, and **actual revocation impact**.
4. `tests/test_predictive_revenue_v420_three_pillar_20261025.py`: explicit forged rights and payment status denial, malformed data, 100%-claim non-promotion, tenant and original CRM restrictions, empty or future windows, role ACLs and PostgreSQL negative cases.

## Exactly what readiness means

The reader exposes `UNVERIFIED` and `PARTIAL_COVERAGE` **research-level** labels. `FULLY_AUDITED` is intentionally unreachable with today's un-attested source and finance records. This is **not a missing feature to toggle on**: the independent proof anchors are absent.

- **Unverified:** no usable claims or no authenticated database read; missing responses are **null**, not zero.
- **Partial Coverage:** at least one scoped source/event/financial *claim* exists. `claimed_source_event_coverage_bps` measures the fraction of **already stored, tenant-claimed channel opportunities** having both a temporally active licence *claim* and a consistent event *claim*. It is not a total population coverage score.
- **Fully Audited:** requires a separately authorised/licensed source register (including consent purpose, expiry/revocation), independently attested provider/carrier/tag intake census including missing opportunities, authentic tenant rights, real acquisition cost invoices and independently validated bank/on-chain settlement, refunds and reversals. No part of V4.20 claims that evidence exists yet.

**The handoff's 95% activation threshold is necessary at most—not sufficient.** Even a forged 100% ratio and paired remittance/bank reference hashes cannot unlock verified CVR, eCAC or live 30/60/90 cash. All outputs retain `fully_audited_independently_verified=false`, `verified_cvr_ecac_authorized=false`, `verified_30_60_90_cash_forecasts=null`, model learning, outbound, paid traffic, economic memory and funds movement OFF.

## Fabricated integration example (not real revenue)

The isolated tenant's `organic` channel has **six** claimed opportunities. All six share a source-licence claim; only **three** have consistent event claims (50% claimed source/event coverage), **three** are linked to accepted-or-later original orders, **one** has two amount-consistent but unverified remittance/clearing hashes, and **one** has mismatched claimed cleared amount. The status remains `PARTIAL_COVERAGE`; no money is verified. Appending a source-revocation tombstone makes active-source matches **zero** while preserving the old source evidence. A foreign tenant cannot read this cohort and the restricted reader cannot SELECT raw claim tables.

The handoff's Pay-Per-Call 94.2%, Storm Restoration 62.0%, SaaS 100%, E-Commerce 41.5% and settlement readiness rates are **illustrative figures only**. Do not display them as real EmpireOS coverage or treat “100% SaaS” as proof of reconciliation.

## Independent evidence still needed

- Trusted owner/consent/license provider that *authenticates* source documents, scope and rights, with per-channel revocation enforcement and an audited reconciliation against rights migration 066. No self-reported `CLAIMED_ACTIVE` should ever suffice for actual source admission.
- Independent carrier CDR / source-provider delivery logs and raw web-tag inbound event inventories that can **enumerate all** eligible events, not merely match opportunities that are already stored. Deduplication, attribution-window and channel-specific denominator specification must be approved.
- Bank/treasury/chain records from independent, accountable custodians. Match exact currency, amount, buyer, order, transaction identifier, settlement time, fees and refund/chargeback finality in both directions (unmatched internal orders **and** unmatched external receipts).
- Separate DBA/security approval, backups, restricted-role review, RLS/owner role permission review and rollback of the entire prepared migration chain 066–072 **before** any future production SQL is run. Private dashboard publication, economic-memory updates, forecasts, money and outbound remain separate gates.

**One EmpireOS. One EmpireDB. One Smart CRM. No new production daemon, source activation or paid traffic.**
