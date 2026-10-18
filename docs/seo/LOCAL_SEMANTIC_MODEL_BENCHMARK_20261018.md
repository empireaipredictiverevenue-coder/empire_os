# Empire AI — Isolated Local Embeddings, Real Metadata and Curated Retrieval Benchmark

**18 October 2026 | Branch:** `feature/seo-zero-cost-reader-20261018`
**Mode:** isolated feature / read-only research. **Production:** unchanged. **Paid API requests:** none.

## What is actually operational

- A real CPU ONNX embedding model ran on the EmpireOS machine.
- FastEmbed **0.8.0**, isolated **Python 3.11 venv** at
  `/home/ubuntu/.cache/empire-semantic-research-20261018/venv`.
- Selected `BAAI/bge-small-en-v1.5` (384 dimensions, MIT model license,
  FastEmbed Apache-2.0). Model is cached locally under
  `/home/ubuntu/.cache/empire-semantic-research-20261018/model-cache`.
- SHA-256 of the actual resolved ONNX model artifact:
  `51f1bd0addd6e859e42c` (prefix; verify complete digest with the code).
  Model provenance ID includes its complete sha256.
- **One-time initial download** came from FastEmbed's configured official
  model distribution. Thereafter local worker forces `HF_HUB_OFFLINE=1`,
  `local_files_only=True`. No model auto-fetch on future runs.
- Runs as a bounded subprocess using the isolated virtualenv interpreter and
  fixed worker script. The subprocess does not import the EmpireOS package
  and receives no inherited environment credentials. It uses CPU threads=2,
  bounded input and a 90-second timeout, without a daemon/timer.
- Importing the feature in the ordinary production Python3.14 environment
  requires NO FastEmbed installation. The optional worker is only launched
  with explicit CLI flags.

## Real first-party metadata run with actual local vectors

Command from feature worktree root:

```bash
ROOT=/home/ubuntu/.cache/empire-semantic-research-20261018
/srv/empire_os/.venv/bin/python -m scripts.review_live_first_party_semantic \
  --start-date 2026-10-03 --end-date 2026-10-15 \
  --local-embed-cache "$ROOT/model-cache" \
  --local-embed-python "$ROOT/venv/bin/python"
```

Observed status: `LOCAL_MODEL`. The four evidenced commercial pages (roofing,
solar, HVAC and predictive revenue) all mapped to potential metadata coverage
using **hybrid_semantic_lexical** retrieval. Recorded internal retrieval
scores: roofing .872487, solar .844325, HVAC .803428, predictive revenue .898806.
These are neither indexed rank nor SEO quality/revenue forecasts.

Existing GSC read API returned 9 query/page observations, 23 impressions in
those returned rows, ZERO matching the four priority commercial pages.
All nine query/page observations remained unmapped. The four page-title
keyword seeds are **unmeasured**, not evidence of organic search demand.
No website edits, no production database writes, no paid requests.

## Curated topic benchmark (exploratory, not independent validation)

Command:

```bash
/srv/empire_os/.venv/bin/python -m scripts.benchmark_local_semantic \
  --local-embed-cache "$ROOT/model-cache" \
  --local-embed-python "$ROOT/venv/bin/python"
```

Reference documents: **4 actual owned public commercial page titles**.
Test queries: **20 developer-authored commercial paraphrases** across four
products, with editorially assigned expected product labels. The query labels
are NOT observed audience searches or independently annotated.

| Retrieval | Top-1 correct | Mean reciprocal rank |
| --- | ---: | ---: |
| Pure lexical TF-IDF | 12/20 (60%) | .7417 |
| Hybrid FastEmbed/TF-IDF | 19/20 (95%) | .975 |
| Difference | +35 percentage points | +.2333 |

Remaining mismatch: **"Heat pump installers looking for customers"** ranked
solar above HVAC. Do not automatically publish or contact buyers from this
classification. The small dataset is insufficient to establish generality.

**Exploratory abstention test:** eight developer-authored unrelated queries
(e.g. cooking, weather, tennis, banking) were all below **.42**, while all
20 in-scope commercial queries were above it. This threshold was selected
after examining the same development data, so performance is **NOT**
out-of-sample, calibrated or production-ready. The preview API supports an
optional explicit `min_score` for abstention; the existing default remains
unchanged. Re-test threshold on newly labelled queries before considering
automatic relevance gates.

## Feature files
- `empire_os/search_intelligence/local_embedding_runtime.py`: cached model
  artifact SHA, bounded inputs, offline local inference and isolated worker
  binding; vector receipts, keyword/page embedding enrichment.
- `scripts/_standalone_embed_worker.py`: standalone FastEmbed worker, with
  offline-only model loading and sanitised process environment.
- `scripts/benchmark_local_semantic.py`: reproducible source-bound,
  editorially-labelled four-sector retrieval comparison.
- `scripts/review_live_first_party_semantic.py`: adds optional
  `--local-embed-cache` and `--local-embed-python` flags; without these it
  retains the original lexical-only mode.
- `empire_os/search_intelligence/semantic_api.py`: adds optional `min_score`
  to caller-supplied preview input; neither infers search demand nor runs
  inference inside the live production API.
- Tests: `tests/search_intelligence/test_local_embedding_runtime.py` and
  existing semantic API/live GSC compatibility suites.

## Open implementation gaps (in order)
1. Build an independently labelled evaluation set with more actual, permitted
   real user-query examples, harder ambiguous queries, product negatives and
   UK/US geographic disambiguation. Measure held-out recall, precision,
   abstention, and calibration before any automatic classification authority.
2. Define explicit model ownership/refresh, source integrity and version
   verification. Pin dependency lock/hashes for a future reproducible deployment
   only after reviewed by existing inference/search owners.
3. Coordinate merge into canonical `agent/data-cloud-wave4` with Search
   Intelligence owner; existing `service.py` is a shared integration point.
   Do not overwrite other agent edits or restart existing production services.
4. Keep existing public site/indexability, GSC and buyer/payer work ahead of
   further model infrastructure. No verified target-page keyword demand or
   accepted commercial transaction is proven by this benchmark.

## Original technical references
- https://qdrant.github.io/fastembed/Getting%20Started/
- https://qdrant.github.io/fastembed/examples/Supported_Models/
- https://github.com/qdrant/fastembed/blob/main/pyproject.toml

No changes to checkout, EmpireDB, CRM, DNS, newsletters, GSC credentials,
production systemd timers, outbound email, website assets or ASTRA branches.
