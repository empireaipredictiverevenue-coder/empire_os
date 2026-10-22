# EmpireOS — Jev sector-level research priorities from the historical prospect reservoir

**22 October 2026 · Isolated development branch · Research, Buyer Scout and source-rights review only.**

This is the next increment after the proven ~234 MB streaming archive reader.
It uses the *existing* Intent Brain, Buyer Scout and commercial evidence
contracts rather than creating a new agent, CRM, public prospect database or
marketing-list exporter.

The historical `public.prospects` source contained **32,899 rows** and
matched the earlier independent recovery ID checksum. It remains an
**offline historical source**, not a current EmpireDB count, transferable
commercial inventory or consent to contact anyone. The sector aggregates were
produced without exporting people, addresses, websites, phones or email.

## What was actually evaluated

Three separate evidence types, never person-level joined:

1. **Historical sector aggregates:** 28 privacy-minimised niche buckets
   (`JEV_LARGE_PROSPECT_DUMP_STREAM_20261021.json`), with the source
   receipt SHA-256 pinned in the one-shot runner.
2. **Current Market GPS:** time-bounded, aggregate research activity across
   sectors/locations (read-only); an acquisition count is not customer intent,
   first-party consent, a buyer conversation or a payable lead.
3. **Buyer Scout readiness:** the current signed-off reader reports
   **NO_VERIFIED_COMMERCIAL_CAPACITY**. Aggregate buyer records, positive
   configured capacity, a delivery destination or a company name cannot
   establish a specific buyer's currently approved buy-box.

One optional *existing local* Jev/Laya shadow call used only the aggregate
`general_contractor` niche code, archive count and recent GPS count. It
suggested `VERIFY_BUYER_CAPACITY`, reported about **2.25 seconds** latency
and was escalated to human review. The original deterministic lane remains
`CORROBORATE_RECENT_ORIGINAL_DEMAND`; no change to the workflow was applied.

## Five existing-owner work packets

| Review lane | Niche buckets | Historical rows | Required real evidence |
|---|---:|---:|---|
| CORROBORATE_RECENT_ORIGINAL_DEMAND | 3 | 11,740 | An independently inspected current commercial/procurement request and original context |
| VERIFY_ARCHIVE_SOURCE_AND_FRESHNESS | 6 | 10,488 | An allowed original business-source, identity lineage, current source, permitted research use |
| REGULATED_SOURCE_RIGHTS_REVIEW | 10 | 5,024 | A sector-specific rights/compliance review; never automatic consumer/claimant targeting |
| BACKGROUND_RIGHTS_REVIEW | 8 | 2,734 | Licensed source custody, original date and human relevance checks |
| REMAP_TAXONOMY | 1 | 2,913 | Independently remap suppressed/unknown industry classifications without inventing identity |
| **Total** | **28** | **32,899** | **Zero automatic dispatch or commercial approvals** |

The three highest initial research sectors have historical inventory **and**
some recent Market GPS observations:

- General contractors: **5,726 historic rows**, **53 recent market
  acquisitions observed**.
- Roofing: **3,674 historic rows**, **9 recent observations**.
- HVAC: **2,340 historic rows**, **10 recent observations**.

Those recent numbers are from restricted acquisition aggregates in a
seven-day GPS window; they are not leads offered for sale, current owner
requests or verified demand. Historic archive geography must not be presumed
to match a recent market row. Separate original-source identity/market
intersection proofs are still required. The current archive and GPS evidence
does not demonstrate specific UK demand or consent; UK original-source
research remains a separate country verification task.

Other large, named sectors—solar, restoration, commercial roofing, managed
IT, merchant services and commercial solar—have enough archive volume to
justify original-source checks, but no matching GPS observations in the
checked window. Highly regulated sectors including medical claims,
insurance, debt relief and healthcare are deliberately held for
independent industry and data-rights review.

## Owner alignment

The output is **a structured proposal for the existing Research/Buyer Scout
owners to review**, not a persisted Department pickup ticket, launch or
scheduler activation. Existing ownership remains:

- Research / Intent Brain: independently inspect recent, original evidence
  of a business **explicitly seeking a solution**; distinguish needs from
  contractors, promotions, hiring or generic news.
- EmpireDB/Data Quality: refresh restricted live counts/cohorts and
  permissions, reconcile original keys and duplicates. Do not reuse old
  DB recovery logins or infer the archive is current.
- Buyer Scout: verify buyer identity, geography, niches, current terms,
  payout, exclusions, delivery and consent under the existing contract.
- CRM: check canonical tenant, relationship history, suppression, opt-out
  and current buyer correspondence before any draft becomes sendable.
- Economic Memory: only count independently accepted, settled receipts as
  realised revenue; do not turn a score or a converted-status flag into cash.

Before integration into an authenticated Founder workbench or Department
tasks, an owner must review the branch, exact source snapshots, source rights,
timezone freshness and negative/contradictory test examples.

**Hard gates:** no model reads individual archive records; no creation or
promotion of prospects; no bulk contact recommendations; no outbound;
no CRM or EmpireDB writes; no external paid Jev; no spend or money movement;
no automatic owner dispatch, skill approval, business terms or revenue claim.

## How to regenerate in this isolated workspace

```bash
cd /home/ubuntu/empire_worktrees/jev_sector_readiness_portfolio_20261022
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_jev_sector_research_priority_20261022 \
  --read-only --local-shadow --max-shadow-calls 1
```

This fixed-name release script refuses to replace a prior reviewed receipt.
For a fresh observation date, create a new explicit, reviewed output name
rather than overwriting or silently refreshing a historical evidence packet.
