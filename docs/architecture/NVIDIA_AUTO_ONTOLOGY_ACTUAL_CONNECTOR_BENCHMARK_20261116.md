# NVIDIA Auto Ontology — actual connector benchmark

Date: 2026-11-16
Owner: Existing EmpireOS identity / Buyer Demand Graph owners
Status: NVIDIA SQLite connector executed and compared; full NVIDIA server/MCP not deployed.

## Source and scope
- NVIDIA upstream `https://github.com/NVIDIA/auto-ontology`, checked-out commit `3825917ac61ff3081035ae61445025f1314d157a`.
- Pinned source checkout: `/tmp/empire-nvidia-auto-ontology-source-audit-20261116` (separate from EmpireOS worktree).
- Isolated dependency: `sqlglot` installed under `/tmp/empire-nvidia-ontology-deps-20261116` only.
- Adapter already committed: `empire_os/nvidia_ontology_shadow.py` (original commit `ec7fc53dc`).
- Benchmark code: `scripts/benchmark_nvidia_ontology_shadow_20261116.py`.
- Offline regression: `tests/test_nvidia_ontology_vendor_offline.py`.
- No production customer data, provider calls, credentials, migrations, outbound or deployment.

## Measured result
The benchmark loaded and instantiated NVIDIA's **real** upstream SQLiteDatabase
connector, validated our ontology document using NVIDIA's
AutoOntologyModelDocument class, and used the connector to query a separate
SQLite snapshot created from the unchanged canonical EmpireOS graph builder.

| Measurement | Result |
|---|---|
| Upstream commit validated | pass |
| NVIDIA model validated | pass |
| Vendor-discovered tables | 4 of 4 |
| Vendor-discovered columns | 18 |
| Vendor-discovered FKs | 4 of 4 |
| Queries matched exact graph-derived expectations | 6 of 6 |
| Raw private buyer identifiers absent from snapshot | pass |
| Evidence refs HMAC-pseudonymized | pass |
| Distinguishes unknown demand from known zero | pass |
| Verified revenue falsely claimed | no (not available in source) |
| Production data accessed | no |
| NVIDIA natural-language agent or MCP tested | no |

The connector is placed in SQLite `PRAGMA query_only=ON` mode before metadata
reads and SQL. The raw data is synthetic; the benchmark explicitly distinguishes
fixture results from genuine buyer proof.

### Six independent query checks
1. Buyer demand edges: expected 2; returned 2.
2. Buyer capacity edges: expected 1; returned 1.
3. Unknown demand quantity: expected 1; returned 1.
4. Actual zero demand quantity: expected 1; returned 1.
5. Demand edges with explicit product/market lane joins: expected 2; returned 2.
6. Demand edges with explicit positive capacity: expected 1; returned 1.

## Reproduce

```bash
cd /srv/empire_os
.venv/bin/python -B scripts/benchmark_nvidia_ontology_shadow_20261116.py
.venv/bin/python -B -m pytest -q \
 tests/test_nvidia_ontology_shadow.py \
 tests/test_nvidia_ontology_vendor_offline.py \
 tests/test_buyer_demand_graph.py
```

Optional vendor checkout and dependencies are not committed into EmpireOS.
If absent, the optional vendor pytest module skips, rather than substituting
a fake implementation. The benchmark executable fails closed when vendor files
are missing or upstream commit is different.

## Deployment gap and next evidence threshold

The host has Docker CLI but access to the daemon socket was denied to the
current process; Compose v2 was not found. NVIDIA's model-service credentials
were absent in the current shell. An Ollama service is present locally but
is **not** the full NVIDIA semantic compilation and MCP runtime.

A full runtime claim requires a separately authenticated and isolated
Auto Ontology backend + catalog DB + ingestion + MCP server, a working model
and embedding endpoint, `check_readiness`, then `ask_question` answers with
SQL and actual rows compared to trusted controls. This benchmark **does not**
satisfy that higher threshold.

No manual release, database migration, source access, spend or service restart
is authorised or performed by this benchmark.
