# Empire AI — Historical USB Market/Forecast Data Truth
**19 October 2026 — Lead Revenue Fabric owner — source census, not ingestion**

## Actual original ApexEngine USB (D:, FAT32 Warning)

Verified via read-only local metadata and aggregate parsing, no records
exported or changed.

1. `D:\\phase1_metro_sweep_data.json`: 4,896,561 bytes; historical
   timestamp **27 June 2026 23:58:51**. Eight US metro groups, **3,856**
   company rows, **680 unique normalized company names, email addresses,
   websites**. No source/provenance fields were present in any company
   row. All company confidence values were identical; all records also
   occurred in their metro's `whale_companies` bucket.
   **Not 3,856 verified companies, not buyers, not real revenue.**
2. `D:\\Expected Value.csv`: 2,358,536 bytes,
   **43,746 historical modelled roofing expected-value rows** across
   **8,600 distinct ZIP codes**. There are **29,157** distinct
   category/service/ZIP keys and **14,589 duplicate keys**.
   No first-party source, actual outcome or verified revenue fields.
   Numeric values ranged 1.0 to 13.75 but the unit, model, base
   rate, calibration and intended target are unverified.
   `Expected Value (1).csv` has an identical SHA-256 digest.
   **These are prediction-like inputs, not observed outcome labels.**
3. `D:\\omega_hot_leads_export.csv`: 179 bytes, **three data rows**
   with score/tier/revenue-potential fields. Scores do not independently
   evidence a buyer, verified business identity, or payment.
4. `/srv/empire_os/runtime/hermes_control/worker_code/si_buyer_outreach.db`
   exists, but its current observed size is **zero bytes**.
   It is NOT recovered evidence of the historic 628/629 subscribers.
5. `D:\\empire-v49-complete.tar.gz` and
   `D:\\empire-v49-deploy.tar.gz` had identical SHA-256 digests and
   valid 40-entry archive listing. Their source modules are a legacy
   reference only. Historic Supabase and Solana/USDC routes remain retired.
6. `D:\\IncusRoot\\ubuntu.tar.gz`: 340.21 MiB,
   timestamp 10 July 2026; `D:\\IncusRoot\\ext4.vhdx` ~4.0 GiB,
   timestamp 19 October. Contents are not yet attested, and neither
   is evidence that the later July Twenty/Listmonk/PostHog fleet was
   recovered. Do not mount writable or repair FAT32 media.

## Safe recovery module implemented

- `empire_os/legacy_market_archive_review_20261019.py`:
  aggregate-only read-only parsers for explicitly supplied local USB
  files. Max 8MB, 100k records, no row/contact/ZIP values emitted,
  no network, no canonical writes, no auto-lead approval.
- `scripts/review_legacy_usb_market_archives_20261019.py --read-only`
  accepts `--metro-json` and/or `--expected-value-csv` only.
  Returns HOLD safely on unsupported/malformed data.
- `tests/test_legacy_market_archive_review_20261019.py`:
  synthetic fixtures cover duplicate records, absent source evidence,
  modelled-value contamination, private contact non-disclosure and
  invalid inputs.
- `empire_os/revenue_data_fabric_edges.py` adds this as a
  **source-code edge only**, not a live pipeline connection.

## Example review on a separately verified local archive copy

```bash
cd /home/ubuntu/empire_worktrees/lead_revenue_fabric_unified_20261019
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_legacy_usb_market_archives_20261019 \
  --read-only --metro-json /path/to/offline/phase1_metro_sweep_data.json \
  --expected-value-csv '/path/to/offline/Expected Value.csv'
```

The raw original files remain only on ApexEngine USB; no assumption
that Windows D: can be read from Linux. Do not copy raw historical
contacts to server before independent source, licence, legal basis,
suppression, canonical identity and tenant-rights review.

## Predictive Intelligence handoff boundary

The separate Predictive Intelligence owner may use **aggregate
anomalies** for research on data leakage, duplication and calibration
bias, but must not train/fine-tune on these old scores as labels,
promote the expected values to realised revenue or overwrite models.
Valid calibration requires independently linked first-party
predictions issued before independently verified terminal outcomes,
time-safe splits, tenant authority and source permission.

## Next commercial actions (bounded)

1. Recover verifiable first-party buyer demand/capacity and actual
   conversion/settlement evidence already held in EmpireDB and Gmail.
2. Independently validate a small sample of historical firm identities
   against licensed current first-party business sources; never count
   source rows as canonical inventory until approved.
3. If historic subscriber/data restore is required, inspect protected
   original backups with its dedicated LXD/DR owner; do not infer
   customer data from source code or use old outbound engines.

**Approval status:** all imports, sending, funds and production
deployment remain OFF. No other agent's files were changed.
