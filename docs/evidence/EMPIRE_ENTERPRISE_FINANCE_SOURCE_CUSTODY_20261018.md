# Empire AI — enterprise financial evidence custody and readiness

**18 October 2026 | Existing EmpireDB / Predictive Revenue enterprise diagnostic | read-only OBSERVE**

## What actually exists

The enterprise report and HTTP response claim-integrity guards are live and return `LIVE_REPORT_GUARDS_VERIFIED` for the JSON, HTML, and Markdown internal-draft paths. That only proves the running output boundary has the intended fail-closed validation logic; it does not prove a customer-level financial finding, client release entitlement, original order/settlement finality or recognized revenue.

The canonical product already includes:
- `empire_os/predictive_revenue_report_source_reconciliation.py`: bounded supplied event+order extract reconciler. The extract is supplied and internally checked; **source authenticity, complete daily count, record selection custody, payment finality and customer tenant authority remain unverified**. This file is currently untracked work owned by another agent and was deliberately NOT edited.
- `empire_os/predictive_revenue_canonical_reader.py`: isolated read-only, single event/order proof under dedicated `empire_predictive_revenue_evidence_reader` role. Its implementation **does not assert a full day aggregate**, and role provisioning/underlying public function were **not independently verified by this work**. No credentials or events were requested.
- `empire_os/predictive_revenue_crm_diagnostic_adapter.py`: existing authenticated CRM tenant-bound selected view, opt-in only. A scoped CRM snapshot **does not prove sale, final recognised revenue, entire tenant census or buying intent**. This other-agent file was not altered.
- Three existing private internal snapshots, `runtime/revenue_pulse/latest.json`, `runtime/economic_memory/latest.json`, and `runtime/buyer_capacity_readiness/latest.json`.

### Current snapshot observations — not audited fact

At the 18 October review:
- The 24-hour Revenue Pulse snapshot (self-labels source `canonical_empiredb_postgres`) records **0 recognised revenue cents, 0 verified payment count and 0 fulfilment count** for that bounded window. Local snapshot integrity SHA256 can show what bytes were present, **not** whether the original database query was complete or transactions were independently authenticated. Do not infer zero historic revenue or no past customer payments.
- Economic Memory reports `promoted_learning=false`, `calibration_evidence_count=0`, `accounting_authority=none`. This is an internal snapshot state, not an independent accounting finding.
- Buyer Capacity reports `capacity_verified=0`, `terms_verified=0`, `delivery_verified=0` in its current observed status. It does not establish all real market capacity is zero; only that the source's bounded evidence has no verified capacity.

## Added now — no duplicated finance infrastructure

`empire_os/enterprise_finance_evidence_readiness.py`: parses **only** those 3 explicit local status paths. It validates file bounds (<=150KB), symlink boundary, timestamp with timezone, 48-hour freshness, expected schema, OBSERVE/none authority, local SHA256, cardinality/field-type and bounded numeric consistency. It does **not** open an EmpireDB connection, a CRM view, customer file, secret, payment provider or commercial sender. In particular, the reported Revenue Pulse 24-hour recognised amount must agree with the self-labelled recognised-revenue truth value *within that snapshot*, and the forecast cannot be included in the truth total.

The output distinguishes:
- `INTERNAL_SNAPSHOT_ONLY`: a locally observed read-model status, even when the file says it came from EmpireDB.
- `STALE_OR_FUTURE_INTERNAL_SNAPSHOT`: >48h old or implausibly future; no implied current-state claims.
- `HOLD_MISSING_STALE_OR_INCONSISTENT_SOURCE_OBSERVATIONS`: missing, stale, tampered structure or cross-field disagreement. This is not proof of zero observations.
- `SOURCE_OBSERVATIONS_ONLY_FINANCE_NOT_ATTESTED`: exactly three fresh, mutually internally consistent, source-labelled snapshots **but never** independently audited finances.

The contract explicitly leaves **seven original-evidence requirements** open until genuinely sourced: (1) authorised original customer ledger and tenant record custody; (2) one canonical independently role-read, order-bound recognised event; (3) reconciled settlement, refunds and reversals; (4) authoritative full-day census including late-arrival cutoff and coverage; (5) buyer terms/capacity and deliverability; (6) forecast/outcome calibration on independent outcomes; (7) customer-specific rights to publish/deliver a reviewed report.

`scripts/review_enterprise_finance_evidence_readonly.py`: no-write on-demand command, requires `--read-only`. Emits source SHA256, observed time, bounded counts and the unresolved source requirements. Missing/inconsistent source status returns nonzero.

`scripts/preview_enterprise_report_evidence_readonly.py`: existing founder report validator now has optional `--finance-readiness` for verify format only. It returns the existing legitimate internal-report evidence guard **and separately** the finance/source-readiness evidence inventory. The existing Markdown and HTML render behavior is unchanged; no optional source-readiness data is permitted to bypass the original guard.

`tests/test_enterprise_finance_evidence_readiness_20261018.py`: test valid internal statuses and no-audit interpretation; stale/future/symlink/missing source; unsupported schema/authority; spoofed canonical source field; mismatched truth-window amount; positive fake numbers never becoming audited claims; read-only CLI requirement; existing report verifier opt-in. All tests use synthetic locally isolated fixtures; never feed fake financial events to production.

## How to review without assuming proof

```bash
cd /srv/empire_os
./.venv/bin/python -B -m scripts.review_enterprise_finance_evidence_readonly --read-only
./.venv/bin/python -B -m scripts.preview_enterprise_report_evidence_readonly --read-only --format verify --finance-readiness
```

Neither command writes to EmpireDB, customer CRM, payment or inbox. A file hash here is a fingerprint of an **internal status artifact only**; not a source-signed original event, independent financial audit, currency settlement or entitlement proof.

The next material verification requires *approved, authenticated access to an original record* via the existing tenant-bound reader and/or dedicated finance evidence role, then reconciling a clearly defined complete day of original ledger records. **Do not create an additional reader, import client data via an insecure file, claim a snapshot is independently authenticated, or turn client finance evidence into an outbound recipient.**

Owner overlap preserved: no edits to source reconciler, live enterprise API router, customer CRM adapter, source reader, scheduling, licences, payments or database roles. This is an additional bounded proof-inventory within the existing diagnostic workflow.
