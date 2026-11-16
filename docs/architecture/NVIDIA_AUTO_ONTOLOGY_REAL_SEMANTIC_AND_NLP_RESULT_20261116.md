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


## 2026-11-16 23:43–23:49 UTC: verified model-capacity and data-plane isolation

Follow-up execution on the existing `agent/data-cloud-wave4` owner branch.
No NVIDIA containers were restarted, source data copied to external services,
model settings changed or provider spend initiated.

**Model candidate benchmark (failed, immutable private receipt).**
The preinstalled `qwen2.5-coder:7b` Ollama Q4_K_M model was tested with a
strict JSON Schema equivalent to NVIDIA's `RawTableTermsResult` shape,
requiring one term and six explicit assignments for synthetic
`ontology_edges` columns. The model did not return a response before a
175-second bounded timeout: `ReadTimeout`, `structured_pass=false`,
`duration_s=175.16`. Receipt:
`runtime/nvidia_ontology_eval/qwen7b_model_capability_probe_20261116.json`
(0600). The original 1.5B model route was **not replaced**.

The host has eight visible CPU cores, no accelerator GPU (only Matrox
server display controller), and was under variable concurrent CPU load.
Installed larger Qwen models (14B/30B) were inventoried but deliberately
not deployed or benchmarked: 7B already exceeds the performance gate.
This is evidence of insufficient **measured local inference performance**,
not proof that all available architectures or providers will fail.

**Actual data-plane benchmark (passed, immutable private receipt).**
`scripts/accept_nvidia_live_synthetic_sql_20261116.py` loaded the pinned,
genuine NVIDIA SQLite connector with its own read-only mode enabled
(`PRAGMA query_only=ON`), targeting the *existing* synthetic runtime
SQLite fixture `runtime/nvidia_ontology_eval/empire_graph.sqlite`.
It independently required the expected four tables, four FKs,
absence of raw synthetic private identities, and authenticated live
NVIDIA catalog with the four exact approved term descriptions.

Six SQL question checks matched expected counts:

| Question | Expected | Actual | Result |
| --- | ---: | ---: | --- |
| Demand edge count | 2 | 2 | PASS |
| Capacity edge count | 1 | 1 | PASS |
| Unknown demand is NULL | 1 | 1 | PASS |
| Known demand quantity is zero | 1 | 1 | PASS |
| Explicit product–market demand joins | 2 | 2 | PASS |
| Positive capacity on matching demand | 1 | 1 | PASS |

Receipt: `runtime/nvidia_ontology_eval/nvidia_live_synthetic_sql_six_case_receipt_20261116.json`
(0600), `verdict=PASS`, `passed_count=6`, `not_natural_language=true`,
`canonical_semantic_terms_verified=4`, `production_data_modified=false`.
Companion test
`tests/test_nvidia_runtime_acceptance_receipts_20261116.py` prevents
the connector result from being misreported as NLP success, and
preserves both prior failed NLP and current failed model benchmark gates.

**Troubleshooting finding:** vendor reranking utility is referenced in
semantic compilation for bridge-table selection, but there is no
`rerank_hits` call in NVIDIA's `retrieval/` or
`server/chat/` text-to-SQL path. Reranker configuration is therefore
**not** the demonstrated reason for the observed NLP timeout; do not
add an unrelated reranker or rewrite the Search Fabric layer.

**Release decision (evidence-based):**

- `NVIDIA_PRIVATE_DOCKER_RUNTIME`: VERIFIED.
- `NVIDIA_AUTHENTICATED_CATALOG_AND_CANONICAL_TERMS`: VERIFIED.
- `NVIDIA_LIVE_SYNTHETIC_SQL_CONNECTOR`: VERIFIED, six cases pass.
- `NVIDIA_STRUCTURED_MODEL_REPLACEMENT`: REJECTED for 7B CPU candidate.
- `NVIDIA_NLP_SQL_AND_AUTONOMOUS_AGENT`: HELD. Last actual NLP attempt
  timed out after 95.3 seconds with no SQL or final answer; cancellation
  verified HTTP 200. Do **not** assert it is live.
- `NVIDIA_SCHEDULED_SEMANTIC_COMPILATION`: DISABLED after previous
  unproductive run; no fresh run authorized by this benchmark.
- `PRODUCTION_CUSTOMERS, REVENUE, TENANTS, MCP`: NOT ACTIVATED.

The next technical boundary is *fast, reliable structured-output and
tool-call inference* with explicit resource/cost authority. The live
retrieval/connector layers require no rebuild. Before allowing model
switch or GPU/hosted inference purchase, prove a candidate's response
against NVIDIA's actual schema, then run a complete six-question
**natural-language-to-executed-SQL** benchmark, not just SQL connector
queries. Preserve rollback and founder release control.

## 2026-11-16: Existing NVIDIA-via-OpenRouter credential verified (no new key)

- Confirmed user-accessible private credential file `/etc/empire_os/llm_secrets/openrouter.env` contains a non-empty `OPENROUTER_API_KEY`; value was never displayed. The additional OmniRoute provider environment files exist but are permission-restricted to this non-root connected session. A **separate direct NVIDIA API key was not verified**; do not equate OpenRouter with build.nvidia.com credentials.
- Existing `empire_os/hermes_control.py` references the route `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`, so a provider connection already existed in EmpireOS. Do not create another route or key merely for discovery.
- Retrieved the live OpenRouter model catalog (HTTP 200); `nvidia/nemotron-3.5-super-vl:free` was listed with prompt and completion prices `0`, and structured output, JSON schema and tools advertised. Model catalog entries and quotas may change; recheck before all external calls.
- Executed **one real, synthetic-only, free-model canary** through that existing credential with fixed model id and provider fallback disabled. HTTP 200, returned requested free model, JSON-schema response exactly matched a minimal synthetic contract, 157 tokens, 1.31 seconds. No customer or business data were sent, and no paid model fallback was requested.
- Ran **one harder synthetic-only canary** using the pinned vendor's actual Pydantic `RawTableTermsResult` schema. The model replied in 4.1 seconds, but Pydantic returned `ValidationError`: `complete_structured_pass=false`. Receipt kept privately under `runtime/nvidia_ontology_eval/hosted_free_nemotron_native_schema_20261116.json` (0600). **The existing hosted route is therefore NOT YET APPROVED as a replacement for NVIDIA's current local model.**
- Committed canary source `scripts/probe_existing_openrouter_nvidia_native_schema_20261116.py` without any credential material. Model tests are synthetic and manual only; not scheduled.
- No Docker container, gateway, production model route, database, paid plan, billing, source customer records, or deployment configuration was changed by these credential checks.
- Preserve the requirement to pass the exact NVIDIA structured schema plus six actual natural-language-to-executed-SQL benchmark cases before activating external inference in the running NVIDIA evaluation. The verified deterministic 6/6 SQL connector result does **not** substitute for NLP success.

**Verdict:** Existing credential verified and reusable for a guarded free-model experiment. Direct NVIDIA key remains unverified. Simple JSON works; full vendor schema fails. Keep isolated deployment unchanged until a candidate passes.
