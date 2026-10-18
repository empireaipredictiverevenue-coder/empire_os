# Empire AI — Source-grounded semantic sector conflicts & second relevance benchmark
18 October 2026 · feature-only · no paid data, publication or production mutation

## Why
The preceding 20 developer-authored test queries exposed one error:
"Heat pump installers looking for customers" was ranked to **solar** rather
than **HVAC** by an otherwise promising local BGE-small hybrid search pipeline.

A genuine category confusion must not trigger SEO content creation, lead
qualification or outreach. This patch adds a *read-only sector sense check*
that explains explicit terminology and signals disagreement.

## Engineering changes

- `empire_os/search_intelligence/semantic_sector_review.py`:
  explicit multi-word sector terminology with authority/first-party references.
  Supports HVAC/heat pumps, solar/photovoltaics, commercial roofing and
  Predictive Revenue, abstains on multiple explicit verticals and on absent
  sector clues. Returns a review suggestion, not a forced product assignment.
- `empire_os/search_intelligence/semantic_api.py`:
  Existing `POST /v1/search/semantic/keywords-preview` includes
  `sector_review` beside normal retrieval results. No new API endpoint,
  model runtime, network call or service.
- `scripts/benchmark_local_semantic.py`: reports explicit-sector conflicts
  alongside original retrieval ranking and makes clear classification is advisory.
- `scripts/benchmark_semantic_source_titles.py`:
  adds a second repeatable, third-party-public-document-title probe.
- Regression tests:
  `tests/search_intelligence/test_semantic_sector_review.py`,
  `tests/search_intelligence/test_semantic_source_titles.py`, and existing
  semantic API tests.

**Evidence anchor:** U.S. Department of Energy:
https://www.energy.gov/energysaver/heat-pump-systems
and https://www.energy.gov/topics/heating-cooling.
These establish heat pumps as heating/cooling technology; they do *not*
establish a verified Empire buyer, intent, CPC, search volume or commercial
contract. Other sector glossary source links point to existing live owned pages.
Terms such as `PV` alone are deliberately not treated as unambiguous solar
intent; `solar PV` is a more specific grounded phrase.

## Benchmark 1 — 20 development paraphrases

The original 20 developer-authored query examples and four verified
first-party published page titles were re-tested with the same cached
BGE-small-en-v1.5 local model and existing TF-IDF blend.

| Retrieval | Top-1 | MRR |
|---|---:|---:|
| Lexical | 12/20, 60% | 0.7417 |
| Hybrid | 19/20, 95% | 0.975 |

The one remaining wrong top-1 (heat pump -> solar) now produces
`SEMANTIC_SECTOR_CONFLICT_REVIEW`, source-hypothesis `hvac`.
**No automatic reassignment.** The model's top-1 accuracy remains 95%;
do not claim 100% accuracy due to an advisory warning.

Unrelated-query rejection on the previously examined eight negatives remained
exploratory; the .42 relevance cutoff is post-hoc, not production-calibrated.

## Benchmark 2 — 12 external document titles

**Inputs:** 12 real public headings/titles with URLs, from U.S. Department
of Energy (solar/HVAC), National Roofing Contractors Association (roofing),
and Microsoft Learn (revenue/sales forecasting). Three per topical category.
Sources recorded individually in `scripts/benchmark_semantic_source_titles.py`.
These were selected *after* the original 20-query dev run and have not been
used to tune this model, but are **not** randomly selected buyer queries or
independently annotated. They mainly measure broad topical recall.

| Retrieval | Top-1 | MRR |
|---|---:|---:|
| Lexical | 6/12, 50% | 0.7222 |
| Hybrid | 12/12, 100% | 1.0 |

Do **not** treat these percentages as actual market performance, independent
generalisation proof or verified Google rankings.

## Existing branch reproduction

```sh
cd /home/ubuntu/empire_worktrees/seo_zero_cost_reader_20261018
ROOT=/home/ubuntu/.cache/empire-semantic-research-20261018
/srv/empire_os/.venv/bin/python -m scripts.benchmark_local_semantic \
 --local-embed-cache "$ROOT/model-cache" \
 --local-embed-python "$ROOT/venv/bin/python"

/srv/empire_os/.venv/bin/python -m scripts.benchmark_semantic_source_titles \
 --local-embed-cache "$ROOT/model-cache" \
 --local-embed-python "$ROOT/venv/bin/python"
```

## Integration gap / priority

The next milestone is an independently labelled dataset containing actual
permissioned search queries across each sector, subsegment, informational vs
transactional intent, mixed renewable-energy installations, and UK/US
geographies. Measure precision, recall, false positives and abstention. Only
then should automatic filtering be authorised.

Second: improve real HVAC page body/explanations of heat pumps where suitable,
subject to separate website-owner review—do not auto-create thin pages solely
because the term was absent from current H1/H2/meta. Google's helpful,
people-first content guidance still applies:
https://developers.google.com/search/docs/fundamentals/creating-helpful-content

**No production activation, site mutation, additional timer, paid request,
CRM write, outreach, main branch merge, or API deployment.**
