# Empire AI — Semantic Keyword Retrieval / Topic Graph (18 October 2026)

**Status:** isolated feature, not deployed. **Budget:** £0. **Production:** untouched.

## Why this is additive
- Reuses `empire_os/keyword_universe.py` records, schema, provenance,
  intent/funnel/industry/territory mapping; no second keyword database.
- Reuses DataForSEO local export reader in the same isolated branch, but never
  converts sandbox dummy ranks into observed demand or commercial metrics.
- No new crawler, queue, agent, service, timer, Vector DB, or package download.
- Unlike Google's live SERP systems, this is an internal ranking/research tool.
  Internal retrieval scores are not Google positions, search volumes or revenue.

## New code
- `empire_os/semantic_keyword_search.py`
  * Evidence-bound keyword search using corpus TF-IDF as £0 offline fallback.
  * If a caller supplies **matching-model** query and document embeddings
    with provenance receipts, blend cosine vector similarity (0.65) with
    lexical TF-IDF (0.35). Strictly label hybrid vs lexical for each result.
  * Filter by actual existing `product_key`, `territory_key`,
    `intent_class` metadata; never fabricate commercial intent.
  * Group same-product/territory/intent/funnel keyword records by dense
    similarity where available, otherwise lexical overlap, using complete-link
    thresholding to reduce chained unrelated topics.
  * Expose possible overlap across manually declared cluster keys for
    editorial human review; no programmatic content rewriting.
  * Return original `evidence_refs`, embedding reference, and explicit unknown
    search volume/revenue. Publishing and indexation always false.
- `scripts/review_semantic_keywords.py`: local JSON CLI for searching
  authorised Keyword Universe exports or producing draft topic groups.
- `tests/test_semantic_keyword_search.py`: synthetic similarity and
  intent/territory safeguards plus CLI integration.

## Read-only usage
From feature worktree root:

```sh
/srv/empire_os/.venv/bin/python -m scripts.review_semantic_keywords \
  /path/to/keyword_universe_rows.json --query "solar installation cost" \
  --product-key solar --territory-key GB --top-k 10

/srv/empire_os/.venv/bin/python -m scripts.review_semantic_keywords \
  /path/to/keyword_universe_rows.json --topics --min-similarity .72
```

Input `{"keywords":[...]}` is a JSON object containing validated existing
Keyword Universe rows, each with `keyword`, `cluster_key`, `intent_class`,
`product_key`, `icp_key`, `funnel_stage`, `cta_key` and real `evidence_refs`.
Optionally include `embedding`, `embedding_model` and `embedding_evidence_ref`
on each row and `query_embedding`, `embedding_model` and
`query_embedding_evidence_ref` at the object root for a hybrid search.

**Important:** Machine-generated embeddings are *not installed or enabled* by
this commit. There is no installed sentence-transformer inference library.
Without supplied vectors the system performs **lexical** retrieval, not true
semantic understanding, and explicitly reports `LEXICAL_ONLY`.
Synthetic vector tests do not prove semantic quality on real queries.
Dense vectors from different models or incompatible dimensions are never mixed.

## Acceptance / next implementation priorities
1. Obtain a known local embedding inference model after checking owner of
   existing search/model resources. No installation without owner/production
   review and no unapproved egress. Keep one shared embedding service.
2. Load evidence-backed GSC queries and original sector-specific page titles
   into the existing Keyword Universe mapping, maintaining source/query-date
   provenance. Do not treat Search Console anonymised query gaps as zero demand.
3. Compare human-labelled UK solar and US roofing queries to benchmark
   semantic recall, relevance, false-positive rate and cross-market leakage.
4. Add pages and intent relations into existing Search Intelligence
   cannibalisation/internal-links modules; don't create duplicate pages
   or mass-publish automated doorway content.
5. Only after real retrieval evaluation, integrate previews with the existing
   commercial dashboard and ROI calculator, without verified revenue claims.

Google's official search guidance prioritises helpful original content and
explicitly says exact keyword variants are not always required:
https://developers.google.com/search/docs/fundamentals/seo-starter-guide
https://developers.google.com/search/docs/fundamentals/creating-helpful-content

No production changes, new timers, paid calls, DNS work or outgoing email.


## Added: evidence-bounded semantic page coverage review

`empire_os/search_intelligence/semantic_coverage.py` maps an *existing* Keyword
Universe record against only authorised, evidenced website-page metadata
(title/target query/topic), with matching product/territory/search intent/funnel.
It can use same-model keyword/page embeddings with evidence, or lexical fallback.
The score is an internal relevance heuristic, **not Google's ranking, a crawl
of actual page body, or proof that the page is indexed**.

- A matched page receives `POTENTIAL_METADATA_COVERAGE`.
- A missing match with incomplete inventory is `UNKNOWN_INCOMPLETE_PAGE_INVENTORY`.
- An asserted-complete *local* inventory may produce `REVIEW_LOCAL_METADATA_GAP`,
  not a definitive recommendation to create a new page.
- When two distinct pages match one topic, calls the **existing**
  `search_intelligence.cannibalisation.detect_cannibalisation` for review.
- Requires explicit site-domain scope; optional tenant scope refuses mismatches.
  Rows without provenance are excluded; no changes to published pages.

CLI:

```sh
/srv/empire_os/.venv/bin/python -m scripts.review_semantic_keywords \
  /path/to/keyword_universe_rows.json \
  --pages /path/to/evidenced_page_inventory.json \
  --owned-domain empire-ai.co.uk
```

Page JSON: `{"pages": [{"canonical_url": "https://empire-ai.co.uk/industries/roofing", "title": "...", "target_query": "...", "topic": "...", "product_key": "roofing", "territory_key": "US-CHI", "search_intent": "commercial", "funnel_stage": "conversion", "evidence_refs": ["crawl:receipt"]}]}`.
Site domain and metadata must reflect actual authorised first-party observations;
this example is schematic and not a claim about the live page's fields.

**No real GSC/page corpus was ingested in this feature review.** Every test used
synthetic input. That remains the next operational integration step.


## Existing Search Intelligence API integration (feature only)

The feature branch also adds `empire_os/search_intelligence/semantic_api.py`
and mounts it in the EXISTING `empire_os/search_intelligence/service.py`
FastAPI application. Nothing was activated in the running production service.
These are caller-supplied **unverified** previews, not canonical EmpireDB reads;
there is no provider transport or write authority.

- `POST /v1/search/semantic/keywords-preview`
  Input `{"keyword_rows":[...],"query":"roofing quote chicago", "product_key":"roofing"}`.
  Optional evidence-stamped, matching-model vectors turn lexical TF-IDF search
  into honest hybrid retrieval. All results report their actual method.
- `POST /v1/search/semantic/topics-preview`
  Input `{"keyword_rows":[...],"min_similarity":0.72}`.
  Uses existing industry/territory/intent/funnel boundaries.
- `POST /v1/search/semantic/page-coverage-preview`
  Input `{"keyword_rows":[...],"page_rows":[...],"owned_domain":"empire-ai.co.uk"}`.
  Uses existing cannibalisation detection for possible targeting overlap.

All return `source_claim=caller_supplied_unverified`, `mode=OBSERVE`,
`execution_authority=none`, `publishing_enabled=false`,
`outbound_enabled=false`, `paid_api_calls=false` and `revenue_verified=false`.
No endpoint fetches websites, reads unrelated tenants, sends email or stores data.
Requests are bounded to 500 rows (plus embedding-dimension limits).
Mis-scoped domains, invalid evidence and mismatched embeddings fail closed.

**Review gate before merge:** because `service.py` is also owned by other
Search Intelligence agents, coordinate with its owner and rebase minimal
router inclusion rather than overwriting unrelated API work. Keep the
running loopback service, Cloudflare forwarding and any public gateway
unchanged until separately verified and authorised.

## 18 October follow-on: isolated real embedding inference verified
The previously absent local model is now **available in an isolated research
venv**, not installed into the production EmpireOS Python environment. It is
not a production embedding API or a new service. The optional one-shot local
worker ran BGE-small-en-v1.5 offline using the explicitly pinned cached model
and no inherited credential environment. Real first-party keyword/page data
was re-reviewed with hybrid semantic similarity. A small **developer-authored**
20-query evaluation returned 19/20 top-1 topic selections, versus 12/20 for
lexical TF-IDF; 8 deliberately unrelated probes were below an exploratory
.42 cutoff, which is **not** independently calibrated or deployment-approved.
The remaining observed confusion is heat-pump installers vs solar installers.
See `docs/seo/LOCAL_SEMANTIC_MODEL_BENCHMARK_20261018.md` for the exact
reproduction commands, evidence restrictions, model hash and next gaps.
