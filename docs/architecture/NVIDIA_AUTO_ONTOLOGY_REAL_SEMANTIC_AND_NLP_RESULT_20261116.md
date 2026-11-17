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


## 2026-11-17 — Existing OpenRouter free Nemotron integration, staged backend release

Owner branch: `agent/data-cloud-wave4`. Existing private evaluation:
`empire-nvidia-ontology-eval`. This is the same project, gateway, synthetic
data source and canonical ontology — not a duplicate platform.

**Model capability verified:**
- Reused existing user-owned OpenRouter credential; no new API key or account.
- Live OpenRouter catalog lists
  `nvidia/nemotron-3.5-super-vl:free` with prompt and completion price zero
  and structured-output/tools support at time of each canary.
- Initial minimal schema: HTTP 200, valid JSON in 1.31 s.
- Native NVIDIA `RawTableTermsResult` direct Pydantic diagnosis:
  **PASS**, one term and six exact synthetic columns in **5.39 s**.
- LangChain client with NVIDIA's 8,192-token response allowance:
  **PASS** for the exact vendor Pydantic schema in 13.74 s; its
  bound tool call returned the exact requested relation in 0.98 s.
  The earlier 1,000-token variant raised
  `LengthFinishReasonError` and was not promoted.
- The existing private gateway was extended by a small optional helper
  `scripts/nvidia_free_openrouter_relay_20261117.py`, **not replaced**.
  Only exact alias `openai/nvidia/nemotron-3.5-super-vl:free`
  routes to the existing OpenRouter key on the Ubuntu host.
  The key is *never* copied to NVIDIA Docker or Git.
  Each hosted request rechecks public model price and features, rejects
  nonzero or unrecognised pricing, enforces exact free model and
  `allow_fallbacks=false`, no streaming and an 8,192-token cap.
  Existing local `nomic-embed-text` embeddings remain unchanged.
- User-owned isolated gateway systemd service was restarted under existing
  owner, with a private rollback of the previous gateway/unit available.
  Gateway health **PASS**; a real synthetic hosted request through the
  running gateway returned HTTP 200 and valid structured output in **1.9 s**.
- An additional live LangChain test through the **same existing gateway**
  (in a temporary loopback test server, without altering Docker)
  returned vendor Pydantic schema PASS in **4.74 s** and a tool call PASS in
  **1.06 s**. Receipt saved private at
  `runtime/nvidia_ontology_eval/nvidia_free_gateway_live_contract_20261117.json`.
- Unit/regression/source tests: **33 passed** (one unrelated
  Starlette deprecation warning), script syntax and new Compose config pass.

**Release staging (NOT YET APPLIED to backend):**
- `scripts/stage_nvidia_free_backend_20261117.py` updated only private
  `runtime/nvidia_ontology_eval/.env` reasoning, non-reasoning and shared
  chat model aliases, retaining dummy API keys, existing private host bridge,
  and local embeddings. Original private configuration preserved as
  `runtime/nvidia_ontology_eval/.env.before-free-nemotron-20261117`
  (0600). Running Docker containers were not recreated during staging.
- `scripts/activate_nvidia_free_backend_20261117.sh` is a scoped,
  root-authorised, founder-invoked activation:
  validates Compose isolation, loopback frontend and synthetic SQLite bind;
  performs **actual native NVIDIA LangChain Pydantic and tool-call probes
  from inside the existing backend Docker container first**; then only
  `docker compose up -d --no-deps --no-build --pull never auto-ontology`.
  Postflight checks confirm PostgreSQL, frontend and ingestion service
  container IDs unchanged, new backend environment read back and health;
  on a failure it attempts to restore the previous `.env` and backend.
  Report is saved privately on EmpireOS under
  `runtime/nvidia_ontology_eval/free_backend_activation_readback_20261117.txt`.
- Root-only Docker access is **not available** to the connected remote
  machine shell, so the founder must run the one command on EmpireOS:
  `sudo bash /srv/empire_os/scripts/activate_nvidia_free_backend_20261117.sh`.
  No logs need to be copied; the readback can be retrieved by the connected
  authorized machine tool.
- `scripts/accept_nvidia_free_nlp_six_20261117.py` prepares the actual
  authenticated NVIDIA six-question **natural-language-to-executed-SQL**
  gate. Requires result event, SQL, executed DB result and correct expected
  count for all six questions; cancels incomplete runs and writes an
  immutable private receipt. **Not executed**, pending backend activation.

**Do not promote:** The six deterministic SQL connector tests passed previously,
but full NVIDIA free-hosted NLP-SQL remains **not verified** until the
root-scoped backend switch and subsequent six actual questions succeed.
No production customer data, billing, product launch, real tenant routing,
outbound messages or paid model calls are authorised or claimed.


## 2026-11-17 00:17–00:23 UTC — live NVIDIA NLP-to-SQL acceptance VERIFIED (isolated synthetic scope)

**Actual founder-controlled activation:**
- Founder ran `sudo bash /srv/empire_os/scripts/activate_nvidia_free_backend_20261117.sh`; retrieved the immutable private report `runtime/nvidia_ontology_eval/free_backend_activation_readback_20261117.txt`.
- Report: `NVIDIA_FREE_HOSTED_COMPOSE_SECURITY_PASS`,
  `NVIDIA_CONTAINER_TO_FREE_GATEWAY_STRUCTURED_SCHEMA_PASS`,
  `NVIDIA_CONTAINER_TO_FREE_GATEWAY_TOOL_CALL_PASS`,
  `UNTOUCHED_POSTGRES_FRONTEND_INGESTION_IDS_CONFIRMED`,
  `NVIDIA_FREE_BACKEND_RUNTIME_ENV_VERIFIED`, `ACTIVATION_EXIT_CODE=0`.
- **Only** the NVIDIA evaluation `auto-ontology` backend container was recreated.
  Dedicated evaluation PostgreSQL, UI, and ingestion remained the same container IDs.
  Frontend remains bound to `127.0.0.1:33000`; backend and DB are private.
  Local `nomic-embed-text` embeddings remain active; only reasoning/chat
  aliases changed to `openai/nvidia/nemotron-3.5-super-vl:free`.
- The actual user-owned free-model gateway service stayed active on
  `172.18.0.1:19999`; local and NVIDIA application health returned HTTP
  success, `{"status":"ok","postgres":{"status":"ok"}}`.
  Existing OpenRouter host credential never entered NVIDIA's Docker environment.
  Model price zero is verified before each call with `allow_fallbacks=false`;
  free quotas and future availability remain provider-dependent.

**Real NVIDIA chat-to-SQL benchmark, not direct SQL connector tests:**
- Ran `scripts/accept_nvidia_free_nlp_six_20261117.py` via authenticated
  NVIDIA frontend, asking six different natural-language questions.
- The first receipt (private
  `runtime/nvidia_ontology_eval/nvidia_hosted_nlp_six_case_receipt_20261117.json`)
  recorded a false-negative **test parser** failure: NVIDIA had generated
  and executed valid
  `SELECT COUNT(*) AS buyer_demands_lane_count FROM main.ontology_edges
  WHERE relation = 'BUYER_DEMANDS_LANE'` returning
  `['[{"buyer_demands_lane_count":2}]']`, but the original count parser
  did not recognise the valid SQL result alias. This is a test code defect,
  not a model or DB failure. Original receipt was preserved.
- Corrected the acceptance parser to recognise a **single numeric aggregate
  column with any valid alias**, and to demand generated `COUNT(...)` SQL,
  referenced tables and the required semantic filters. Added hardening:
  no promotion of text-only answers, no ambiguous multiple rows or
  multiple columns. Added alias/null/zero/multirow regression cases.
- Re-ran the **real authenticated NVIDIA 6-question SSE workflow** from the
  running backend and captured
  `runtime/nvidia_ontology_eval/nvidia_hosted_nlp_six_case_receipt_20261117_v2.json`
  as an immutable owner-readable mode 0600 file.
- **Result: `VERIFIED`, six of six passed**, with each individual request
  returning HTTP 200, generated SQL event, executed DB result event, and a
  numeric value matching independently executed source SQL. No SQL-only
  connector shortcut was used in this second acceptance run.

| Real natural-language task | Expected | Actual | Duration | Result |
|---|---:|---:|---:|---|
| Buyer-demand edges | 2 | 2 | 12.63 s | PASS |
| Buyer capacity edges | 1 | 1 | 16.47 s | PASS |
| Unknown demand (`IS NULL`) | 1 | 1 | 17.46 s | PASS |
| Known explicit zero demand | 1 | 1 | 12.16 s | PASS |
| Product–market relationship join | 2 | 2 | 16.65 s | PASS |
| Matching positive capacity | 1 | 1 | 16.39 s | PASS |

- Added `tests/test_nvidia_free_nlp_live_receipt_20261117.py` to guard
  expected counts, actual executed-result evidence, SSE events, exact
  existing free model, synthetic-only scope and preservation of original
  failed receipt. Full scoped regression suite: **35 PASS**,
  one unrelated Starlette deprecation warning, zero failures.
- No production data, buyer identity, verified demand, actual sales or
  tenant authorisation was inferred from this **synthetic** dataset.

**Release decision and remaining explicit gates:**

- `NVIDIA_PRIVATE_DOCKER_RUNTIME`: VERIFIED.
- `NVIDIA_FREE_NEMOTRON_BACKEND`: ACTIVATED and model/config readback VERIFIED.
- `NVIDIA_CANONICAL_FOUR_TERMS`: VERIFIED after authenticated correction.
- `NVIDIA_REAL_NLP_TO_EXECUTED_SQL`: **VERIFIED 6/6 on synthetic fixture**.
- `NVIDIA_LOCAL_EMBEDDING_ROUTE`: VERIFIED; 768-dimensional outputs.
- `NVIDIA_AUTOMATIC_SEMANTIC_COMPILATION`: **DISABLED**; previous automatic
  pass did not complete. Four current terms match canonical EmpireOS source,
  but successful autonomous semantic regeneration is not demonstrated.
- `NVIDIA_MCP_AND_AUTONOMOUS_AGENTS`: NOT VERIFIED/NOT ACTIVATED.
- `CUSTOMER_DATA_PRODUCTION_TENANT_ROUTING`: NOT AUTHORISED/NOT ACTIVE.
- `REAL_BUYER_OUTREACH_PAYMENT_REVENUE`: NOT AUTHORISED/NOT VERIFIED.

This completes the original **isolated runtime + inference + NLP-SQL**
evaluation milestone, not a production release. Keep the known-good
backend, local embeddings and private model gateway in place. The next
release gate, if later approved, is genuine authenticated agent MCP integration
and tenant-isolation/rights testing, **not another engine rebuild**.
