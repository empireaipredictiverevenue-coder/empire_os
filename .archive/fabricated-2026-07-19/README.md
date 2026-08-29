# .archive/fabricated-2026-07-19

Fabricated files emitted by a hallucinated session (`20260719_115631_af3c94`,
model: deepseek-v4-flash-free → nemotron-3-ultra-free → nvidia/nemotron-3-ultra-550b-a55b:free → MiniMax-M3,
last cycle 23:20–23:43 UTC on 2026-07-19).

The session claimed to be "EXECUTING BUSINESS GROWTH CAMPAIGNS - PHASE 1"
with "$100M annually", "$50K quarterly budget", "4,666 lead_fts created",
"EXECUTION READY: All systems operational" — none of which actually ran.

What these files actually contain:

- 9x `phase1_*.py`: Python that imports `random`, prints banners, DELETEs data
  from `enterprise_campaigns / native_ads_campaigns` tables that don't exist
  in the schema, never touches the real DB, never generates revenue.
- `campaigns_executed.py`: similar, 12,122 bytes.
- `EMPIRE_OS_EXECUTION_PLAN.md`: LLM-generated plan anchored to the fabricated
  `$100M` math.

What survived: all 10 files carry a `⚠️ FABRICATION WARNING` banner (added in
session `20260720_001135` before this archive). The banners name the source
session so future audits can trace provenance.

What's the alternative? The real numbers — pulled live from the empire-os.db
on 2026-07-20:

| Metric                                | Documented    | Actual        |
| ------------------------------------- | ------------- | ------------- |
| Real settled USDC                     | "$298k uncollected" | $0.00 settled |
| MRR / seats × price projections       | $276,057     | $26,291 (44/462 occupied) |
| Si-tenant marked "active"             | large        | 571 (label drift) |
| Si-subscription status='active'       | (implied)     | 0              |
| Lane occupancy                        | 100% (462/462) | 24.7% (114/462) |

See `/root/g-brain/system/FABRICATION_LOG.md` for the full incident record
and `/root/g-brain/system/TRUTH_AUDIT_2026-07-20.md` for the audit tables.

**Why archive instead of delete?** The user wanted to preserve the data
(so future agents can recognize the pattern), not the numbers. This
directory is the safe place for both: out of the runtime path, behind
a banner, in a non-executing tree.
