# Empire AI — Marcus-inspired keyword research × real GSC evidence

**Checked:** 26 October 2026. **Source:** EmpireOS *existing* local Search Intelligence API, `GET http://127.0.0.1:8771/v1/search/search-console/observations`. **Authenticated source:** `google_search_console`, property `sc-domain:empire-ai.co.uk`, `query,page` keys. **Window:** 4–16 October 2026, inclusive; fully historical to avoid Google Search Console's most recent partial day(s).

This is a **read-only operational evidence review**, not a claim of current ranking, total market search volume, affiliate revenue, or successful SEO publication.

## Two real research examples

| Research root | Derived candidate ideas | Original GSC query/page rows inspected | Exact query match | Honest next action |
|---|---:|---:|---:|---|
| `commercial roof repair` + `TPO roofing`, `PVC roofing`, `roof coating` | **27** | 7 | **0** | Check real target-region SERPs and relevant trade vocabulary before predicting SEO demand |
| `how do i know which accounts in my tam are actually ready to buy right now` | **15** | 7 | **1** | Review the real page and query relevance; the GSC signal is weak |

The 27 and 15 figures are **original phrase suggestions**, not keywords proven to have search volume. The same 7 observed first-party query–page rows are reused for both reviews; do not double-count them or combine page-only GSC totals.

### Actual observed TAM row

- Query: `how do i know which accounts in my tam are actually ready to buy right now`
- Observed page: `https://empire-ai.co.uk/aeo/accounting/TAM/`
- Source: owned `google_search_console` `query,page` observation, 4–16 October 2026
- **Impressions: 1** (on this owned site/page and date window), **clicks: 0**, **GSC reported average position: 8.0**.
- Evidence: `gsc-query-page-sha256:c6313d952d9f7d3e6a7e1e925b47e225785993b1a43c6aa60886f80641d3cb55`.
- **Not proven:** Google's current organic placement; total query volume; number of other searchers; buyer intent; ranking difficulty; booked calls; closed sales; customer revenue; complete query corpus.

**No-match means only** `NOT_IN_RETURNED_GSC_SAMPLE`, not zero actual searches, zero opportunity or lack of Google indexing. Search Console may omit anonymised queries and rows outside the response limit. On this window, seven records were returned by the original query/page reader.

## Implementation now joined to the original systems

- `empire_os/public_intent_offer_method_bridge.py` retains the independent generic trigger/glossary → canonical `keyword_universe` → existing draft asset backlog from the previous commit.
- `empire_os/public_intent_serp_evidence_bridge.py` joins the original SERP/competitor gap from dated accepted `SerpSnapshot` inputs, no new search engine.
- **New:** `empire_os/public_intent_gsc_evidence_bridge.py` invokes the original local GSC reader, enforces original domain, authentic source, query/page dimensions, bounded historical window, integer/CTR/position sanity checks, exact query matching and deduplication. It preserves unmatched original GSC observations separately. Search-volume/CPC/difficulty/revenue remain unknown.
- **New:** `empire_os/public_intent_evidence_triage.py` orders *research actions*, not Google result rankings. P1 = reviewed first-party query match; P2 = unverified commercial-intent wording; P3 = unverified educational wording. No numeric economic score, no assertion that P1 has more search volume.
- **Extended:** `scripts/review_public_intent_offer_method_20261025.py` accepts `--gsc-start` and `--gsc-end`; performs one allowlisted localhost GET, or none if no dates. `--full` enables original mapped keyword backlog and query evidence.

### Repeatable command (no new Google credentials)

```bash
cd /home/ubuntu/empire_worktrees/marcus_public_method_bridge_20261025

PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_public_intent_offer_method_20261025 \
  --market us-commercial-roofing \
  --seed "commercial roof repair" \
  --icp commercial-roofing-operator \
  --buyer-problem "Decide whether roof repair or replacement is justified" \
  --glossary "TPO roofing,PVC roofing,roof coating" \
  --gsc-start 2026-10-04 \
  --gsc-end 2026-10-16
```

Use a current **finalized** window for future checks, but the command will never invent a missing date/metric or create a separate Google API credential. If the original loopback reader is unavailable, the result is a HELD status, not synthetic zero metrics.

## What this means commercially

For roofing, research the SERP and exact customer problem before building more public pages. **Do not publish 27 pages because a modifier generated 27 strings.** A useful one-page repair-versus-replacement guide could be reviewed later through the existing website owner, but it needs actual content quality/rights and genuine buyer conversion paths.

For TAM, one GSC impression is a valid but very small signal. Improve or test the *existing* well-matched resource first; do not claim it is already a commercially successful entry page. Route real consented interest to the existing commercial/Smart CRM system, not a new lead database.

**Release state:** isolated feature worktree only, no production integration/deployment. No paid traffic, email, scraping, payment activation, root-owned file mutation or public SEO posting.

## Additional more-recent finalized GSC window

A second independent read-only request used **17–23 October 2026**, inclusive (three-day reporting safety buffer at the October 26 check). The original existing Search Intelligence endpoint returned **2 query–page rows** for that date window. Neither `commercial roof repair`-derived terms nor the long TAM readiness phrase exactly matched either returned row.

This does **not** cancel or invalidate the distinct 4–16 October TAM observation. Do not pool the two windows, assert that a query has stopped being searched, or infer a ranking trend from the different returned row counts. The current right next action is broader source-backed SERP research and legitimate first-party content relevance inspection, not auto publishing or declaring the keyword dead.
