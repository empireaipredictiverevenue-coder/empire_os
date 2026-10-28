# EmpireOS Predictive Microsite Factory + SlopMonster V1
**Date:** 26 October 2026
**Owner:** Website/SEO implementation owner for deployment; Marketing Growth + ASTRA for candidate briefs
**Implementation branch:** `agent/predictive-microsite-slopmonster-20261026`
**State:** Private draft-only build, not released or published.

## Verified implementation
- Vendored **unaltered** MIT licensed `ItsssssJack/SlopMonster` Python scorer at upstream SHA `3fc9787d9337b57c599a80afbefbbb3be5a8eb0b`, with upstream attribution and licence under `empire_os/third_party/slopmonster/`.
- `empire_os/predictive_microsite_factory.py`: consumes original `keyword_universe.review_keyword_record` and `geo_registry.acquisition_markets` (does not replace them). Requires known geo anchor and per-fact source references, preserves missing scores. For US ZIP / UK postcode code shape only, market association must be separately verified by source. Generates branded, responsive, accessible draft HTML and SlopMonster scoring; does **not** accept false buyer/revenue claims as facts or send enquiries.
- Duplicate-content guard checks editorial overlap across a proposal batch, omitting literal geography in comparisons. A guard is a heuristic, not search-engine clearance.
- `scripts/review_predictive_microsite_factory_20261026.py`: command-line read-only inputs, private HTML/manifest/brief output only. No network/API, publishing, ORM, email, third-party model calls or scheduled process. Max 25 proposals per batch.
- `scripts/review_slopmonster_site_copy_20261026.py`: audits rendered static HTML/Markdown from existing sites in **read-only** mode, with style score and basic HTML checks. Limit 200 documents; zero writes to originals. Audits are best-effort source-based, **not** browser-render or conversion tests.
- `tests/test_predictive_microsite_factory_20261026.py`: end-to-end preview and audit acceptance tests including malformed geography, unsourced facts, redacted HTML injection, anti-doorway duplicate check and full preservation of original files.
- `tests/fixtures/predictive_microsite_factory_sample_20261026.json`: Chicago roofing + Manchester heating **sample inputs**, deliberately missing observed keyword volume, so status is HOLD_EVIDENCE.

## Existing systems reused
- EmpireDB stays canonical. V1 creates no tables.
- `empire_os/keyword_universe.py`: research intent and score contract; null demand remains `available: false`.
- `empire_os/geo_registry.py`: original 115 US/UK geographic market anchors. These are not ZIP/postcode coverage facts.
- Existing `owned_campaign_*` governance, first-party attribution and website release remain sole route for any future publication. Neither is modified by this branch.
- The existing ASTRA marketing and website owners must integrate proposed briefs. No new ASTRA instance, scheduler or publishing daemon.

## How to run in the isolated worktree
```bash
WT=/home/ubuntu/empire_worktrees/predictive_microsite_factory_slopmonster_20261026
cd "$WT"
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /srv/empire_os/.venv/bin/python -B \
  -m pytest -q -p no:cacheprovider tests/test_predictive_microsite_factory_20261026.py \
  tests/test_keyword_universe.py tests/test_semantic_keyword_search.py \
  tests/test_advertising_landing_feedback.py

PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /srv/empire_os/.venv/bin/python -B \
  scripts/review_predictive_microsite_factory_20261026.py \
  --input tests/fixtures/predictive_microsite_factory_sample_20261026.json \
  --output-dir /home/ubuntu/empire_releases/predictive_microsite_factory_slopmonster_v1_20261026_stage
```

Auditing existing public output files only:
```bash
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  scripts/review_slopmonster_site_copy_20261026.py \
  /srv/empire_os/apps/empire-public-site/out/index.html \
  /srv/empire_os/apps/empire-public-site/out/commercial.html
```

## Sample evidence review
Two sample previews produced locally; both **HOLD_EVIDENCE** because actual measured keyword demand is unknown. They are illustrative research pages, not public microsites, buyer-matched offers or published ZIP campaigns. Their local facts include pointers to existing code, and **require real source review** before reuse as public claims.

Six existing static pages audited: home 4/5, commercial 3/5, roofing 5/5, solar 4/5, HVAC 3/5, predictive-revenue 4/5. This shows common writing patterns only. It does not measure actual conversion, demand or trust, and valid facts such as genuine numbers may trigger the proof heuristic.

## 28 October 2026 — General UK/US original government source coverage

- The original factory source-link validator now accepts authentic `*.gov.uk` domains for GB geographic anchors and `*.gov` for US anchors outside the original narrow pilot. Government-host suffixes are checked with proper DNS label boundaries, the already validated original market country, HTTPS, no credentials, no alternate port, no tracking query or fragment. The original pilot's source allowlist stays as before; its owner workflow is untouched.
- The existing `GB-MAN` sample was reviewed with three current government/council source links and four practical property research steps, through the **original** preview script. Its outcome is deliberately **`HOLD_EVIDENCE`**, zero publishable pages and unverified demand. Private research source and owner-only preview reside under `/home/ubuntu/empire_releases/predictive_microsite_uk_source_research_20261028/`.
- Wider original source/copy/ranking/outcome + keyword test selection: **169 passed** (one pre-existing AnyIO deprecation warning). Source-host validation does **not** independently verify factual claims, permit publication, or assume commercial demand. Original SEO/website execution ownership unchanged.
- [Exact source policy and verified UK private research brief](PREDICTIVE_MICROSITE_GOV_SOURCE_POLICY_UK_RESEARCH_20261028.md).

## 28 October 2026 — Executive-grade source/intent/portfolio decision layer

The original existing V4 ranked research queue now emits a non-publishing `executive_screen` for each candidate and a market-diverse `executive_portfolio` shortlist limited to **three different markets**. It separates author-supplied source/link/check dates and actual reader utility from **observed first-party GSC intent**, targeting guidance, calibrated model forecasts and unverified commercial economics. It has deterministic next-best evidence actions and owner labels, without inventing search volume, visits, lead conversions, payout, CAC or ROI.

The actual original two demo candidates were both blocked by weak source-backed usefulness, even though they tied at 15 numeric priority points; the Manchester official-source research (three direct official URLs, four research actions) qualified **for research attention only**, with next action to obtain exact first-party query evidence. The source hasn't independently established true claim accuracy, organic demand or buyer revenue. No launch, new service or paid spend. One private decision readback: `/home/ubuntu/empire_releases/predictive_microsite_uk_source_research_20261028/executive_source_quality_review_v1_20261028.json`.

The existing V4 ranking script was also run unchanged end-to-end against the current private source-backed Manchester research: `MEASURE_FIRST_PARTY_INTENT`, one research-only shortlist item, **zero publishable**, verified approved factory pages zero, model calibration zero, and expected revenue null. **189 selected regressions passed.** No duplicate runtime or original website release.

Full strategy, operating states and readback: [Executive Research & Investment Discipline](PREDICTIVE_MICROSITE_EXECUTIVE_RESEARCH_DECISION_20261028.md). The site's original release/SEO/brand owner work remains outside this branch.

## Remaining implementation for the current site + SEO owner
1. Review the original provenance and upstream licence; rerun unit tests.
2. Supply real search intent, measured demand, current dated SERP/source inputs and geographic ZIP/postcode associations with evidence. Do not guess counts.
3. Adapt the draft manifest into existing ASTRA marketing review queue, not a new agent. The output brief is prepared but **not submitted** to ASTRA automatically.
4. Add browser screenshot comparison for mobile/desktop, design accessibility review, readability, layout responsiveness and Core Web Vitals; the current checker does not visually inspect pages.
5. Add an authorised copy-writing model adapter for actual revision; the current SlopMonster integration **scores and supplies copy/design briefs** but intentionally does not auto-call Claude, Codex or Laya. Show before-and-after diff and source fact lock.
6. Unify the site/page-specific identities, first-party event instrumentation and actual economic feedback with the existing canonical customer/CRM records. Do not interpret a page view as a buyer or a payment.
7. The site and SEO owners decide which high-quality, source-distinct proposals merit reviewed publication. No geo-keyword doorway pages, fictitious local branches or thin multi-domain content.
8. Ensure target landing pages have real privacy/consent copy and a genuine operator behind any contact/booking CTA before enabling it. Keep outbound and payments untouched until independently authorised.

## Governance
Original site's `apps/empire-public-site`, search/SEO owner modules, production website files, CRM, EmpireDB, payment and outbound gates were **not edited**. No new database, live timer, paid campaign or deployed website. This branch can be cherry-picked/reviewed by the responsible owner without conflicts on their actively edited files.
