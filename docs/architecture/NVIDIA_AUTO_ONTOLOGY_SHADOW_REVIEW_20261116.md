# NVIDIA Auto Ontology — EmpireOS restricted compatibility review
Date: 2026-11-16
Status: LOCAL BRIDGE IMPLEMENTED; NVIDIA FULL RUNTIME NOT DEPLOYED

## Ownership and provenance

- NVIDIA upstream: https://github.com/NVIDIA/auto-ontology
- Inspected upstream commit: `3825917ac61ff3081035ae61445025f1314d157a`.
- Licence: Apache-2.0 (upstream).
- Working copy of upstream examined under `/tmp/empire-nvidia-auto-ontology-source-audit-20261116`, outside the EmpireOS repository.
- EmpireOS original owner: `empire_os/buyer_demand_graph.py` and `empire_os/graphify_dual_bridge.py`.
- New additive bridge: `empire_os/nvidia_ontology_shadow.py`.
- New regression tests: `tests/test_nvidia_ontology_shadow.py`.
- No canonical source, database, API, or production routing changed.

## What's implemented

`write_private_sqlite_shadow()` takes an *existing validated* BuyerDemandGraph
and a caller-supplied 32+ byte privacy key. It reuses `project_buyer_demand()`
to pseudonymize source IDs and evidence references with HMAC, suppress raw
buyer labels, and allow only explicitly approved public product/market labels.
It refuses an existing output path, creates a SQLite snapshot with mode 0600,
and validates foreign keys. This is a **local data snapshot**, not a
connection to production and not an outbound service.

`build_nvidia_model_document()` generates a native NVIDIA model interchange
payload with four tables, four glossary terms, four foreign-key relationships,
zero uncertified measures, and no asserted sale or buyer authentication.
Its structure was validated with NVIDIA's actual `AutoOntologyModelDocument`
Pydantic schema at the pinned upstream commit.

The bridge preserves `NULL` for unknown demand, distinct from genuine
reported zero. Explicitly supplied buyer-capacity evidence stays distinct from
demand. Every fact remains marked `EVIDENCE_REFERENCED_NOT_AUTHENTICATED`.

## What has NOT been verified

- The NVIDIA frontend, backend, model endpoints, embeddings, catalog compilation,
  and MCP server have **not** been deployed or tested end-to-end.
- The upstream model schema accepts the JSON payload, but the runtime model
  import/compile path has not been exercised with a running NVIDIA instance.
- No real tenant data was ingested or sent to a model API.
- No actual buyer, customer, qualification or revenue outcome was discovered.
- Caller is responsible for source authority and tenant membership before
  selecting a graph for later review; this bridge does not verify tenant membership.
- Docker exists on the checked EmpireOS host but `docker compose` v2 is absent.
- No inferred relationships are promoted to verified commercial truth.

## Verification commands (local, read-only except temporary pytest files)

```bash
cd /srv/empire_os
.venv/bin/python -B -m pytest -q \
  tests/test_nvidia_ontology_shadow.py tests/test_buyer_demand_graph.py
```

For live NVIDIA evaluation, establish a **separate** authenticated deployment
first, using test-only SQLite data. Scope source access to that dataset.
NVIDIA's `CONNECTION_STRINGS` option lacks table/schema allowlisting;
prefer the UI-managed connection for scoped future sources. Keep internal
backend and ingestion ports private, and protect model API keys and
catalog credentials. Do not import with `replace=true` into any live catalog.

When that environment is ready, test `check_readiness`, `search_terms`,
`check_answerable`, and `ask_question` with the controlled graph data.
For every answer, compare SQL and returned rows to independently executed
SQLite queries. Reject any answer that treats a referenced evidence link as
a verified customer, sale, or accepted buyer capacity.

## Commercial measurement

First benchmark: can the ontology identify an **explicit** buyer-to-lane demand
edge, the corresponding product and geography, and independently supplied
capacity without manufacturing unknown quantities? Compare accuracy against
EmpireOS's baseline graph traversal. A verified sales outcome requires
separate canonical CRM/customer and transaction evidence, not the ontology.
