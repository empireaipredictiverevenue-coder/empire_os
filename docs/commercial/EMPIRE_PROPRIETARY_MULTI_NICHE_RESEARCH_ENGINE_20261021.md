# Empire AI proprietary research engine — multi-niche correction
Date: 21 October 2026. Owner branch: `review/brokerage-us-uk-deep-research-owner-20261021`.

## Critical scope clarification
**Proprietary** describes the Empire AI research/search bot and its independently implemented EmpireOS orchestration. It does **not** mean that the programme is focused solely on *property*. The product is multi-niche: dental is the first live, source-verified example, with the same research architecture intended for roofing, solar, HVAC, legal, property/development and later supported verticals.

The architecture was informed by earlier experiments reviewing open-source Vane/Perplexity-style retrieval and OpenManus-style planning; this commit **does not copy upstream Vane or OpenManus code**. Any actual third-party dependencies, model weights, APIs, trademarks and provider rights must be reviewed independently before marketing exclusive ownership or a white-label licence. The EmpireOS-specific policy, profiles, first-party source provenance, source comparison, review gates and report structures form the current proprietary implementation.

## How to run

```bash
cd /home/ubuntu/empire_worktrees/brokerage_us_uk_deep_research_owner_20261021

# Dental: existing primary-source UK + US demonstration; independently inspected.
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.run_brokerage_deep_research_20261021 \
  --read-only --country both --niche dental --format markdown

# Roofing: two-market discovery and source-rights intake plan, NOT a completed report.
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.run_brokerage_deep_research_20261021 \
  --read-only --country both --niche roofing --format markdown
```

`--niche` choices: `dental roofing solar hvac legal property`. `--country`: `US`, `GB`, `both`. Optional `--probe-public-search` attempts the original Search Fabric; only independently reviewed sources may be admitted. The actual provider was degraded in a prior live probe. Optional `--local-model-challenge` is source-question assistance **only** and has no editorial authority. A non-dental unverified intake intentionally exits code 2 to signal that the original-source evidence is missing, even when displaying a useful plan.

## Safeguards proven by regression
- Dental first: three Chicago/Lincoln Park originals + three independently selected UK Birmingham/CMA originals, source fingerprints and actual inspection, no ranking/revenue claims.
- All other niches: UK- and US-specific sector research questions, buyer problem, original-source types to check, unsupported-inference limitations and source-rights intake owner. **Zero original-source claims** until verified. No dental clinic records are transferred into another niche.
- Sector-specific Search Fabric queries are generated without mixing verticals; fresh search candidate URLs never become admitted research evidence by themselves.
- Original Search/Market Intelligence owner retains editorial and reuse-rights gates. No CRM writes, email sending, proposal, money movement or tenant action.
- Regression: 79 pytest tests + 5 subtests passed including prior existing search-fabric tests.
- Real CLI probe: dental both US/GB inspected 3/3 per country, exit 0, editorial pending; roofing both US/GB held without source catalogue, exit 2 as designed.

## Original commercial workflow
Research and source proof → editor-approved specific useful insight → natural one-to-one relationship → discover real buyer problem and decision → scope → proposal only after genuine interest → approved payment and deliverables. Do not send the illustration as customer proof while the original editorial queue's stale snapshot receipt identity and signed reviewer approval remain unresolved.

## Work still outstanding
1. Reliable fresh-source discovery via existing Search Fabric or independently verified provider, with rate limits and no invented fresh evidence.
2. Generic original-source admission per niche/country (source rights, custody, attribution, original site health, manual Research acceptance before fetch); never blindly scrape contact information.
3. Real reviewer identity/signature for the current original Research queue snapshot. Five historical DONE receipts currently differ from the regenerated plan only at snapshot fingerprint; **do not mutate history** or waive signature.
4. Governed integration into the active department owner, and source-backed client suitability review. Current work is an isolated owner branch, **not** promoted into the shared dirty checkout or scheduled as a production bot.
