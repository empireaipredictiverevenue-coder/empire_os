# Empire Data Exchange V19 — Release Evidence and Transient Source Privacy

**Date:** 15 October 2026
**Current production starting point:** canonical V15 genesis sequence 0,
verified V16–V18 OBSERVE-only readback, no second historical observation.

## Completed V19 work

1. Reuse the existing V18 rights docket and eight independent-review
   control IDs. For each control, specify **two concrete evidentiary
   deliverables**, an owner/reviewer verification requirement and an
   unsubmitted review status. No synthetic sign-off or legal clearance.
2. Attach the V19 evidence collection register to the **existing**
   `scripts.inspect_data_exchange_v16_live --read-only --rights-docket`.
   The register is pinned to the real canonical head SHA256 and sequence.
   The local scope digest is NOT an external digital signature.
3. Distinguish **persisted projection** from **transient raw HTTP source**:
   - The V15 custody schema accepts only an exact strict public-data
     record projection (verified from the stored canonical hash).
   - The existing official GET adapter decodes the **full** JSON response
     transiently in memory before discarding unapproved fields.
   - It is inaccurate to assert that no personal data was ever fetched
     just because no contact field was stored.
   - Therefore raw-source personal-information presence remains
     **UNKNOWN_NOT_REVIEWED** pending independent assessment.
4. Add one separate explicit read-only, non-persistent source-field-key
   audit using the EXISTING fixed three-entity official GET adapter.
   Aggregate counts only; NO raw keys or values are printed.

## Real public-source bounded key inventory

The live, one-shot source audit on 15 October 2026 returned:

- **3** accepted fixed official entity responses.
- **59** JSON key occurrences across the three responses
  (not necessarily unique keys).
- **35** occurrences outside the existing source normalizer's
  allowed raw input key set, dropped during canonical projection.
- **6** occurrences whose *key names* matched potentially sensitive
  tokens such as email/owner/contact/address; NO raw values were analyzed
  or persisted by this audit.
- `projection_fields_strictly_validated=true`.
- `raw_response_logged_or_persisted_by_audit=false`.
- `personal_information_in_raw_payload=UNKNOWN_NOT_REVIEWED`.
- No DB write, public product, outbound, timer, payment or resale.

This is **not** proof that there are six personal-data records, nor that
the raw payload is compliant or non-compliant. It is evidence for the
separate privacy reviewer to check without allowing sensitive values to
appear in telemetry or release documents.

## Safe operator commands

Nonprivileged source key audit (three allowlisted public GETs only):

```bash
cd /srv/empire_os
./.venv/bin/python -m scripts.audit_data_exchange_raw_source_shape_v19 --read-only
```

Root-only canonical release evidence check, reusing the single V15
read-only EmpireDB transaction and protected login:

```bash
sudo -n bash -c '
cd /srv/empire_os
./.venv/bin/python -m scripts.inspect_data_exchange_v16_live \
  --read-only --rights-docket
'
```

No customer-facing release is enabled by either command. There are
still eight unsubmitted independent review controls; collect real signed
or otherwise reviewable supporting artifacts before explicit founder
release approval under existing governance.

## No duplicate platform

No new database, DB role, credential, agent, systemd service, timer,
source scraper, commercial offer, external LLM or outbound workflow.
No second canonical observation, no modification to V16 24-hour gate,
and no mutation of raw source values or source publisher content.

## Next evidence decisions

- Independently review transient raw source payload field *values* safely
  in a protected local environment, without emitting them in logs.
- Verify source-specific third-party rights and field-level exceptions.
- Define retention, supersession, correction, privacy rights handling,
  and withdrawal conditions for a future product.
- Verify publication date separate from Empire fetch timestamp.
- Complete a bounded source revision comparison after tomorrow's
  legitimate second V16 observation (>= 2026-10-16 08:53:59 UTC).
- Require explicit founder release authority only after all independent
  reviews. No automatic promotion to resale or buyer outreach.
