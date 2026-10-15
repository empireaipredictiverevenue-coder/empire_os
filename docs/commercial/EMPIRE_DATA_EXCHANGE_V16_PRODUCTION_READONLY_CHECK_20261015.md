# Empire Data Exchange — V16 production read-only inspection

Production release scope: existing V15 EmpireDB canonical custody and V16
temporal quality. No new roles, table, service, timer, migration, cron,
model, new data source or customer-facing API.

## Root-only operational check

The production V15 DSN remains protected in
`/etc/empire/data-exchange-custody.env`, root-owned 0600.
The reviewer reads it **in memory only**, checks connection identity through
the dedicated V15 reader, verifies contiguous custody integrity and compares
the genesis SHA256 to the founder-provided original production receipt:

`c7c3b13bde6684168e07fc9af17c19b8183d8b43c7de5930fa55814210ae4f1c`

Invoke read-only production check through the **existing authorised root shell**
when needed, not through unprivileged Commander:

```bash
sudo -n bash -c '
cd /srv/empire_os
./.venv/bin/python -m scripts.inspect_data_exchange_v16_live --read-only
'
```

For an additional public-source GET of exactly three fixed official
UK Planning Data entity IDs, add `--recheck-official`. This does not
write an observation or prove an independently authenticated source.

Safe report fields:
- Canonical head sequence/hash, genesis matching, read-window completeness
- Latest captured timestamp, seconds until 24-hour eligibility, precise
  `capture_not_before_utc`
- Actual V14 historical change count and review state (if two real samples)
- Source recency, missing pilot IDs, optional repeat-source consistency
- Non-authority flags: rights, resale, commercial, buyer interest, outbound,
  customer delivery, payment and external anchoring remain false.

Once eligibility is reached, the existing manual founder-gated V16 follow-up
operator can capture a second genuine source observation. **This inspector
cannot do so.** Run no command that tries to bypass the 24-hour gate, and do
not extrapolate three records to regional market coverage.

Important: a valid local custody chain does not provide an externally
signed government attestation. The first V15 snapshot is not proof of a
planning event or buyer intent. No source field rights are cleared.
