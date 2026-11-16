# EmpireOS / NVIDIA Auto Ontology — authenticated semantic and NLP runtime verification

Date: 2026-11-16, 23:25 UTC
Owner: existing EmpireOS data-cloud integration branch `agent/data-cloud-wave4`
Scope: isolated NVIDIA Auto Ontology project `empire-nvidia-ontology-eval`, synthetic `empire_graph` SQLite only.
Verdict: **DOCKER + AUTH + PRIVATE MODEL ROUTES VERIFIED; CANONICAL SEMANTIC DESCRIPTIONS LIVE; AUTONOMOUS NLP-SQL NOT VERIFIED**.

## Completed with actual runtime evidence

1. The founder's guarded root-only Docker activation completed successfully at
   22:58:24 UTC (readback: `runtime/nvidia_ontology_eval/local_models_activation_readback.txt`).
   `ACTIVATION_EXIT_CODE=0`, `CONTAINER_TO_GATEWAY_EMBEDDING_PASS_768_DIM`,
   `CONTAINER_TO_GATEWAY_CHAT_PASS`, `UNTOUCHED_DB_AND_FRONTEND_IDS_CONFIRMED`.
   Only NVIDIA's backend and ingestion containers were recreated. PostgreSQL
   and NVIDIA frontend IDs were unchanged, and no EmpireOS production services
   were modified.
2. Authenticated NVIDIA admin sign-in on loopback `http://localhost:33000`
   returned HTTP 200 with a session cookie. `GET /api/datasources/dbs` returned
   exactly one catalog database, `empire_graph`. The app health endpoint
   returned `{"status":"ok","postgres":{"status":"ok"}}`.
   Credentials are read from the mode-0600 private runtime file into memory;
   no cookies, tokens or passwords are printed or committed.
3. The isolated ingestion source is the existing pseudonymized SQLite fixture:
   4 tables, 8 nodes and 7 edges. NVIDIA's ingest connected with the existing
   local `nomic-embed-text` model at `172.18.0.1:19999/v1` and processed
   the schema. A Docker-namespace canary returned a valid 768-dimensional
   vector. This is *not* customer data, real confirmed buyer demand, or sales.
4. Enabled the vendor's native semantic compilation using its authenticated
   `PUT /api/configurations/semantic-compilation`. NVIDIA created four Terms,
   but each initially contained its vendor fallback description
   `Business entity represented by table ...`. The pass ran for more than
   ten minutes, produced no completion receipt, and repeatedly stalled under
   concurrent CPU work. Live `last_success_at` and `last_failure_at` remained
   null; therefore **no successful automatic semantic compile was verified**.
5. To avoid a recurring unproductive process, disabled scheduled semantic
   compilation using the authenticated UI API. Then requested a graceful stop
   of the in-flight task through NVIDIA's own isolated ingestion
   `POST /semantic/stop` (HTTP 202), after verifying local app admin access,
   the sole synthetic catalog, disabled schedule and healthy isolated ingestion
   service. Subsequent `/semantic/status` reported `running:false`. No
   container kill, Docker restart, DB wipe, or production changes.
6. Preserved NVIDIA's pre-correction native model export privately as
   `runtime/nvidia_ontology_eval/nvidia-model-before-canonical-descriptions-20261116.yaml`
   (0600, four tables and three terms at snapshot time). Prepared and validated
   a vendor-native nonreplace candidate for the initially missing fourth term,
   but did **not** import it because NVIDIA generated the fourth term before
   stopping: the importer returned `FOUR_TERMS_ALREADY_PRESENT`, zero writes.
7. Via authenticated `PATCH /api/terms/{id}` updated only the four existing
   fallback descriptions to the verbatim approved descriptions in
   `empire_os/nvidia_ontology_shadow.TABLE_DESCRIPTIONS`.
   Readback: `CANONICAL_SYNTHETIC_DESCRIPTIONS_PASS`,
   `canonical_definitions_verified=4`, `founder_certified=false`.
   The Terms are: Ontology Nodes, Ontology Edges, Node Evidence Fingerprints,
   Edge Evidence Fingerprints. No model-generated claims were presented as
   verified customer, revenue, buyer capacity or demand.
8. Ran a *real authenticated NVIDIA chat-to-SQL SSE* request, scoped to
   `empire_graph`, asking to count `ontology_edges` with
   `relation='BUYER_DEMANDS_LANE'`. Independently executed SQL on the source
   fixture gave **2**. NVIDIA responded HTTP 200 and sent only an SSE
   `step` event, then produced **no SQL and no result** within 95.3 seconds.
   The test called NVIDIA's `/api/chat/cancel` and received HTTP 200.
   Immutable private audit:
   `runtime/nvidia_ontology_eval/nvidia_first_nlp_sql_result_20261116.json`:
   `status=NOT_VERIFIED`, `expected_count=2`,
   `database_count=null`, `sql_matches_expected_table_and_relation=false`,
   `timed_out=true`, `cancel_status_if_incomplete=200`.
   **NVIDIA natural-language answering is not demonstrated.**

## Most likely remaining limitation, not a proven singular root cause

The deployment is functioning at the container, model gateway, admin session,
catalog and deterministic SQL connector layers. The local `openai/qwen2.5-coder:1.5b`
chat model responded to simple unstructured tasks in about 5–8 seconds, but
NVIDIA's larger Pydantic/structured-output and agent workflow did not finish
under concurrent CPU load (host load average ~8–9 observed). Separate local
Ollama and llama.cpp structured-output probes also timed out after 85s and
45s respectively. Vendor code falls back to generic terms after structured
output errors. These observations implicate latency / inference capability
and structured-output compatibility, but do not isolate a singular cause.
No GPU availability, full model correctness or tool-call reliability was verified.

## Exact outstanding gates

- Independently validate a sufficiently capable, permitted, load-bounded
  structured-output model against NVIDIA's Pydantic schemas and actual SQL
  tool-use path before changing the approved model route. Preserve the local
  no-billing gate; no paid API calls or infrastructure spend are authorised.
- Run and require one successfully **completed** native semantic pass, compare
  resulting semantic table/foreign-key links against canonical EmpireOS model,
  and disallow unsupported sales or buyer-verification claims.
- Run at least six first-party NLP-to-SQL benchmark questions (demand edge count,
  capacity, null vs zero, product-market join, verified capacity) and require
  executable SQL with exact DB results. A correct generated prose answer
  without executed SQL **does not count**.
- Native NVIDIA MCP/OAuth server and agent control are not activated; keep the
  boundary separate from other EmpireOS agents until verified.
- No customer data, real tenant binding, outbound sales, spending, production
  deployment or recognised revenue were asserted or initiated.

## Recovery and continuity

Use the single EmpireOS integration. Do not start another ontology platform,
alter production PostgreSQL, bypass the NVIDIA app's authorization, or reset
the synthetic database. Reuse private source, canonical definitions and
existing guarded Docker setup.

Read-only probes and execution receipts are under `scripts/*nvidia*20261116.py`
and `runtime/nvidia_ontology_eval`. The latter is gitignored and must not
be uploaded with secrets. Native scheduled semantic compilation was
deliberately set to **disabled** during this verification and should remain
disabled until a validated model can complete a pass.

Status taxonomy:
- Implemented: isolated NVIDIA runtime, local gateway, authenticated semantic,
  four canonical descriptions.
- Tested: health, session, embeddings and simple chat canaries, actual NVIDIA
  NLP request.
- Verified: Docker deployment, source isolation, four descriptions, actual
  failed NLP acceptance result.
- Not verified: native semantic completion, accurate text-to-SQL, MCP, any
  commercial results.
