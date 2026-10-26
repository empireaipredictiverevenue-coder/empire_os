# Empire AI — independent reverse engineering of Marcus Campbell's public keyword methodology

**Date:** 25 October 2026. **Mode:** READ_ONLY RESEARCH. **Owner:** existing EmpireOS Keyword Universe / Search Intelligence / Predictive Revenue. No independent SEO engine, database, agent or publisher.

## Public evidence and accuracy

- **Official 18-tool directory:** https://www.keywordsniffer.com/ — Marcus publicly describes functions and example screens, not internal code. The publisher says volumes, CPC, traffic, backlinks and rankings are provider estimates. Tool-displayed AI decisions, affiliate prices and payouts are opinions or estimates, not audited income.
- **Original trigger/glossary/competitor methods:** https://affiliatemarketingdude.com/marcus-campbells-trigger-word-secrets/
- **Trigger-word categories, six keyword methods:** https://affiliatemarketingdude.com/dashboards/trigger.php
- **Other public AI Profit Scoop utilities:** https://affiliatemarketingdude.com/test-marcus-ai-tools/
- **Seven one-page offer page types and the intent-to-CTA framework (21 October 2026):** https://affiliatemarketingdude.com/author/marcus/

This is **original engineering based on public functional descriptions**. Do not copy proprietary code, interface artwork, pricing datasets, member-only research, login-only keyword dictionaries, secret APIs or bypass access restrictions. Never treat promotional profit claims as forecasts.

## 18 public tools mapped into one existing EmpireOS system

| Marcus tool | Public function | EmpireOS reuse or gap |
|---|---|---|
| Keyword Machine | Seed → keyword variants, metrics | **Implemented original unscored idea adapter** → `keyword_universe` |
| Idea Machine | Audience → commercial problem and offers | Existing `pain_solution_engine`, `gtm_offer_strategy` — offer terms review still needed |
| Glossary Method | Specialist vocabulary → niche ideas | **Implemented founder-provided glossary expansion** |
| Seed Word Finder | Trigger roots and exact phrases | **Implemented bounded generic trigger generation** |
| Page One Checker | Live competitors, strengths, SERP gaps | Existing `search_intelligence.serp` + `competitor_gap`; actual snapshot required |
| Keyword Gap Finder | Competing query coverage | `competitor_gap` + `semantic_coverage` |
| Bulk List Checker | Batch keyword metrics | Existing `keyword_universe`; licensed provider metrics not connected by this change |
| Domain Lookup | Ranking, link strength, history | Existing backlinks, rank history and site data; validate provenance |
| Bulk Domain Checker | Domain comparisons at scale | Existing crawler/competitor inventory, no new mass fetcher |
| Trend Checker | Demand timing | Existing GSC daily series / market evidence; actual history required |
| Traffic History | Organic changes over time | Rank history + owned GSC, not other sites' true analytics |
| Ad Spy | Advertiser messages and keywords | Research adapter later; no paid deployment or invented PPC metrics |
| YouTube Checker | Search demand and competing videos | Existing YouTube buyer-intent intelligence |
| Amazon Keywords | Retail purchase intent | Hold pending lawful marketplace access and product fit |
| Local Lead Finder | Underserved local companies | Existing local intelligence and buyer scout with identity/contact controls |
| Page Health Check | One-page SEO audit | Existing `technical_audit` + `metadata` |
| Tech Lookup | Site technologies and integrations | Native crawler/tech fingerprint evidence gap |
| Mention Finder | Brand coverage and conversations | Existing visibility, citations and PR/earned-media analysis |

**Other publicly listed utilities:** Keyword Extractor, Keyword Strategy, Keyword Report Viewer, KW Cleaner, NicheVision, SEO Audit, Emotion Logic, Title Match, Deep Sales Analyzer, Image Content Generator, PDF converters, transcript and Markdown tools. Their public listing is evidence of advertised existence, **not** independently verified working functionality. Do not clone every tool: reuse SEO, copy, research and document services already present.

## Six keyword strategies — reverse-engineered as general principles

**1 — Basic method:** Begin with a genuine customer issue, find accurate query wording and check actual results before producing content.

**2 — Glossary method:** Collect industry terminology from allowed authoritative sources; propose long-tail questions (e.g. TPO roof repair vs replacement); validate actual volume later.

**3 — Competitor research:** Inspect observed smaller niche sites, what pages rank, and where our content would solve an unmet question. The published 20–30 difficulty heuristic is provider-specific, not proof of easy organic rankings.

**4 — Trigger-word method:** Seed cost, calculator, estimate, checklist, repair, alternative, near-me, reviews, etc. Generate, normalize and deduplicate. Do **not** label rule-derived combinations as Google's genuine searched queries.

**5 — Big Site Method:** Inspect a large, genuinely observed domain keyword portfolio and filter its ranking terms by problem/trigger language. Do not claim the site's keywords, position, or value without a licensed or original source.

**6 — Keyword Jogger:** Find relevant existing affiliate sites through permitted public search queries (e.g. clearly disclosed affiliate pages), then review their observed keyword content and gaps. No unsolicited contact, scraping evasion or claims that an affiliate marker proves payout.

**Separate complementary strategies:** Audience/market flipping starts with buyer jobs and lawful real commercial offers; seasonal timing uses genuinely dated SERP/GSC observations to schedule helpful organic resources. Neither is a source of guaranteed payout or traffic.

## Seven page types — use only as intent-appropriate options

1. **Resource/lead capture:** helpful checklist or guide, optional informed consent.
2. **Educational bridge:** explains what is happening, risk and alternatives, no fake case study.
3. **Core sales page:** approved product terms, transparent qualification, no live checkout until separately enabled.
4. **Choice and entry:** routes differing users to the appropriate existing service rather than forcing one offer.
5. **Qualification/booking:** only genuine scheduling/contact processes; use existing `/commercial` founder enquiry.
6. **Checkout expansion:** only after genuine order and explicit owner-approved payment gates; **hold by default**.
7. **Confirmation/next steps:** verify original submission or settlement before reporting success.

The 21 October publisher article treats page choice as a function of traffic intent: a user asking 'why' needs help; a user searching 'cost' is closer to evaluation; an existing purchaser needs honest next steps. This guides content **planning**, not auto publishing.

## Implementation completed in isolated worktree

- `empire_os/public_intent_offer_method_bridge.py`: independently written, bounded generic triggers + founder-provided glossary, normalized and deduplicated up to 60 ideas. Uses the original `keyword_universe.build_keyword_universe` and `build_asset_backlog`, validates a **real existing Search Product**. Each idea has provenance, missing observed metrics and a draft-only asset mapping.
- `scripts/review_public_intent_offer_method_20261025.py`: one read-only CLI accepting market, seed, ICP, buyer problem and optional glossary. Does no HTTP call.
- `tests/test_public_intent_offer_method_bridge_20261025.py`: proves duplicate protection, invalid input rejection, no invented volume/CPC/rankings, no publishing, no revenue claims.
- **Example:** 'commercial roof repair' + TPO/PVC/roof coating terms produced **27 derived research ideas**, not observed search-volume keywords. They are unscored until real SERP/GSC/provider inputs arrive.

Use:

```bash
cd /home/ubuntu/empire_worktrees/marcus_public_method_bridge_20261025
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_public_intent_offer_method_20261025 \
  --market us-commercial-roofing \
  --seed "commercial roof repair" \
  --icp commercial-roofing-operator \
  --buyer-problem "Repair versus replacement decision" \
  --glossary "TPO roofing,PVC roofing,roof coating"
```

## Recommended build/revenue order

1. **Implemented:** one original trigger/glossary → canonical Keyword Universe → existing draft page backlog bridge. OBSERVE, no external model or SEO spend.
2. **Next:** connect existing timestamped SERP and first-party GSC observations to selected ideas, preserving exact URLs, country, date and data units; no invented scores.
3. Verify whether the buyer really wants the result; connect only to reviewed offers and terms. A broad 'calculator' keyword is not itself a buyer.
4. Prepare **one task-solving page** and one human-reviewed CTA on the **existing** Empire AI site, with website-owner approval before release and no duplicate lead form/CRM.
5. Measure organic impressions/clicks separately from consented enquiries, qualified buyers, signed agreements and independently realised profit. Expand only when data supports it.

**Exclusions:** no duplicate PostgreSQL, shadow worker, root daemon, scraper circumvention, new affiliate accounts, self-serve checkout, automatic emails, paid traffic or release authority.

**Not accomplished here:** live keyword volume, CPC, difficulty, offer payouts, production publishing, real organic traffic or customer revenue. The source site itself does not guarantee accuracy or outcomes.

## Canonical SERP evidence attachment (additional tested integration)

- `empire_os/public_intent_serp_evidence_bridge.py` accepts an **existing** `SerpSnapshot` from EmpireOS Search Fabric only when its exact keyword occurs in the original derived idea set, the observation has a recent offset-aware timestamp, and engine, quality gate and cache provenance are present.
- Calls the **existing** `analyse_competitor_gap` function, so observed rank positions, competing domains and actual current coverage come from the canonical Search Intelligence code, not duplicated ranking logic.
- Missing/unavailable snapshots remain `HOLD_NO_SERP_EVIDENCE`; even available snapshots **never infer** volume, CPC, KD, conversions, affiliate payout, or profit.
- The test suite uses explicitly **synthetic SERP fixtures**, not actual recorded Google rankings. No live SERP fetch has been run by this first build. The connector accepts authentic existing observations in a later authorised run.

## Direct public NicheVision feature inspection

The separately listed `https://www.aiprofitscoop.com/tools/nichevision.php` currently exposes a **Content Strategy Generator** public interface: it accepts pasted URLs/keywords or CSV/TSV, produces processed title/AI insights, niche categories, manual offer inputs, article title deduplication, writing instructions, content-overview/blog ideas, Pinterest/social titles, a keyword wheel, and a niche-report PDF. This is a direct public UI observation; server algorithms and output quality were **not** independently tested. Much of its job is already handled conceptually by EmpireOS Keyword Universe, SEO quality, editorial review and YouTube content workflows. The missing step is coordinated review, **not a new standalone writing generator**.

By contrast, the `keyword-strategy.php` public URL redirects to a member login, and several other listed tool URLs show general marketing pages rather than an accessible tool. Treat their function descriptions as **marketing evidence only**. Do not crawl or attempt to bypass the membership barrier.
