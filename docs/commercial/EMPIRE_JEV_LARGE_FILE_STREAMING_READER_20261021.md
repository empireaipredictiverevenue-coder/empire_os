# EmpireOS — large-file reader for historical prospects

**21 October 2026 · Jev commercial intelligence · new development-only, read-only capability**

## Actual limitation and solution

EmpireOS's old `runtime/data_cloud/supabase_public_data.sql` is a
**233,910,763-byte (223 MiB / approximately 234 MB) PostgreSQL plain COPY dump**.
It contains sensitive contact-related columns among the 19 columns in
`public.prospects`. Loading the entire export into Jev's prompt or a DataFrame
would be wasteful and would create unnecessary personal-data exposure.

The production virtual environment already has `psycopg`, Python's standard
streaming facilities and the original, tested COPY decoder in
`empire_os/data_cloud_shadow_dump_import.py`. It does **not** currently have
DuckDB, Polars, PyArrow or ijson. The present file is well within the server's
available RAM, but streaming is safer and supports larger source archives
without constructing huge lists of contact rows.

## Implemented, tested and actually run

The new `empire_os/jev_large_prospect_dump_reader.py`:

- Reuses the existing PostgreSQL COPY header/escaping rules, including
  suppressing other schemas' contents without decoding them.
- Reads at most 128 KiB per physical source line; handles the file with a
  bounded buffered binary iterator rather than `read_text()`/`json.load()`.
- Allows at most 16 GiB of one file and 5 million prospect rows per scan,
  *configuration ceilings, not claims of tested performance at those sizes*.
  Exact sorted-ID checksum tracking is bounded to 250,000 source IDs;
  beyond that the scan is aggregate-only with the strong-ID-match flag OFF.
- Reads only primary key (briefly, in local process memory), source niche,
  metro, month and unverified status. Phone, address, website, contact names,
  titles, notes and other personal fields are **never decoded or exported**.
- Cross-checks original prospect ID digest and row count with the existing
  independently verified old EmpireDB shadow-copy receipts; rejects a
  mismatched file or forged/changed recovery verification.
- Suppresses small location/sector groups in published results.
- Never connects to EmpireDB, calls a model, sends email, edits CRM,
  changes filesystem permissions, restarts services or authorises leads.

**Observed run:** 32,899 prospect rows, 233,910,763 input bytes,
original historical ID-set checksum matching, **2.286 seconds** total scan
on this server after sector taxonomy expansion. The original produced
observations from June, July and September 2026; that is file content
history, not current market demand.

**Coarse business category results (unverified as marketable leads):**
general contractor 5,726; roofing 3,674; HVAC 2,340; solar 2,583;
commercial roofing 2,035; restoration 2,078; managed IT 1,562;
automotive insurance 1,147; debt relief 1,138; merchant services 1,135;
commercial solar 1,095; medical claims 1,047; and multiple other business
sectors. After the expanded, closed taxonomy, 2,913 source labels remain
unmapped; none should automatically become contactable prospects.

The committed `JEV_LARGE_PROSPECT_DUMP_STREAM_20261021.json` is an
aggregate-only observation receipt, never a customer list or an authorised
commercial product. No contact, identity or person IDs are included.

## Repeatable, independently reviewable operation

From the development worktree:

```bash
cd /home/ubuntu/empire_worktrees/jev_commercial_signal_portfolio_20261021
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_jev_large_prospect_dump_20261021 \
  --read-only \
  --receipt-tag 20261021T230000Z
```

The receipt tag is a **new output name** in the existing research documents
directory. The script refuses to overwrite an existing receipt. It always
reads the same allowlisted original historical dump and the same two
read-only recovery proofs; it does **not** accept arbitrary file paths,
database credentials or unbounded queries.

## More formats and even larger future datasets

Recommended incremental upgrade, when needed and after a separate reviewed
dependency/rights change:

1. **DuckDB** for large CSV/JSONL/Parquet analysis and SQL aggregates.
   It supports streaming scans, memory limits and disk spill, with
   outputs restricted to allowlisted aggregate projections. Start with
   a nonproduction venv; no installation is needed for today's .sql dump.
2. **Polars lazy scanning** (`scan_csv`, `scan_parquet`, streaming collection)
   for fast niche/geo/cohort transforms and column projection, again without
   moving person records to an LLM.
3. **Restricted EmpireDB materializer** for current counts and provenance
   aggregates, preserving its original dedicated role and SQL/tenant gates.
   A streaming offline copy is *not* a substitute for live restricted DB
   access; last current DB health check did not confirm the 32,899 figure.

**Jev integration:** feed only the audited, coarse, rights-cleared summaries
into the commercial review portfolio, plus verified Buyer Scout buy-box,
CRM consent/suppression and accepted commercial events once approved.
Do not run 32,899 individual model calls or infer real buyers, consent,
lead ownership, publisher rights, revenue or permissions from archive rows.

**Production unchanged, no package installs, no actual contact record export,
no outbound, no DB writes, no payments, no auto-approval.**
