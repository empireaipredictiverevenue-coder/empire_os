# EmpireOS Brokerage Deep Research — usable UK/US operator
Date: 21 October 2026. Source branch: review/brokerage-us-uk-deep-research-owner-20261021.
Owner scope: inherited prior isolated Vane answering-engine/OpenManus planning prototypes, EmpireOS Search Fabric and loopback llama.cpp, existing Research/Editorial + Sales owners. **This is a source-observing editorial research operator, not an autonomous publisher, data reseller or buyer-acquisition sender.**

## What runs (actual host test)
From this worktree:

```bash
cd /home/ubuntu/empire_worktrees/brokerage_us_uk_deep_research_owner_20261021
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.run_brokerage_deep_research_20261021 \
  --read-only --country both --format markdown
```

The same command accepts `--country US` or `--country GB`, or `--format json` to produce review-able machine data. **No flag** enables outbound, writes to EmpireDB, verifies customer intent, approves terms or enables payments.

Two additional **optional** diagnostics:
- `--probe-public-search` uses the pre-existing Search Fabric for two public queries per country with `use_cache=False`, returning candidate URLs only. It does **not** automatically fetch discovered URLs or count snippets as evidence; a failed provider is explicitly DEGRADED/UNKNOWN, not zero market demand.
- `--local-model-challenge` invokes the existing loopback `LlamaCppProvider` for sceptical research questions over a *minimal source term matrix*, no raw page prompt or shell/browser. Output is untrusted editorial suggestions and **cannot** authorise any factual claim. Current Qwen 1.5b quality is inadequate for autonomous source interpretation. The real 21 Oct model test timed out and returned JSON `{"error":"llama_cpp_request_failed:TimeoutError"}`; this previously appeared as questions but is now correctly classified `HELD_LOCAL_MODEL_PROVIDER_REPORTED_ERROR`. The resulting failing evidence became a passing regression. Loopback health 200 does not prove acceptable inference quality.

## Verified real first-party evidence
US: the existing Chicago/Lincoln Park original agency sample SHA-256 is `cb278240bae7c412afd46ca8a26c6b350f1995a613a71300b55f06feeb94068a`. Live GET and heading inspection of all **three** previously curated practice websites succeeded. Source: Park Dental Specialists, Lincoln Park Cosmetic Dental Associates, Advanced Dental Care.

GB: manually curated and independently checked **three** original sources: Competition and Markets Authority's private dental market study at gov.uk, Highfield Dental's Birmingham implant-services page and Six Ways Dental's Birmingham practice page. All HTTP 200 / original HTML headings inspected in the live run on 21 October. No US clinical terms or local ranks are transferred into the GB report.

Each original first-party source is recorded with exact URL, content SHA-256, observed headings and presence of a small vocabulary of literal terms. **Keyword occurrence is not clinical availability, comparative advantage, local rank, patient demand or attribution.** Site navigation can repeat keywords; original Research reviewer must read context. The operator emits an explicit matrix, evidence fingerprint, original-page source types, missing evidence checklist and buyer-first commercial sequence.

## Test scope / fail-closed behaviour
36 focused pytest cases + 5 subtests passed on this branch at last check. Covered:
- Prior independent Vane-inspired bounded profile / OpenManus-style step receipt tests; search budget ≤8, pages ≤12, no automation authority.
- US/GB independent source sets, block unknown URL/private IP access, forbid arbitrary pages/redirects and cap payload sizes, deduplicate pages, preserve original source hashes.
- Search provider degraded, stale, cached or synthetic discoveries never become approved primary evidence; no-results never means no buyer.
- Mixed official market context vs self-described dental service pages.
- Missing source holds complete-market claims. Unsupported Qwen suggestion about poor search rankings rejected. Even benign model questions require authenticated editorial sign-off. Real timeout JSON is treated as failed provider, not questions.
- No CRM writes, outbound activation, licensed data distribution, buyer interest, proposals or funds.

## Honest open gates
1. **Fresh discovery remains degraded** on the existing zero-key providers. A live Bing HTML search returned `PROVIDER_DEGRADED`; a bounded Search Fabric reliable fallback returned `CIRCUIT_OPEN`. This bot still returns real vetted original-source evidence but cannot reliably discover arbitrary new sites unattended. Do not describe it as a fully autonomous general-purpose Perplexity replacement.
2. **Original agency Research task identity drift:** all five previous canonical tasks are present in DONE stage. Exact original identity differs from current regenerated plan only at `intelligence_request.agency_source_evidence_review.snapshot_fingerprint`. The signed editorial queue held at zero prepared requests/zero sign-offs. Don't rewrite historical immutable receipts or forge editorial keys; Research owner must version a current-snapshot preflight task and authentic signed decision.
3. **Content rights not cleared** for client distribution or raw publisher data resale. Original US sample still explicitly "Editorial release pending"; the UK sources are newly observed and also unapproved.
4. **No general-purpose protected fetcher or agent shell/browser control**: only exact approved publisher URLs are allowed; no OpenManus unrestricted execution; no user social/private account scraping.
5. Existing private light-branded Workspace 1:1 template is independent. Rapport/value/verified buyer problem come before a proposal/price. This operator deliberately does not send email and should not create a separate CRM.

## Runtime and owner continuation
The runtime is source-only and reproducible from an isolated worktree. The canonical shared checkout is used by other agents (agent/data-cloud-wave4, ~197 unrelated dirty changes when reviewed); it was left unchanged. Source promotion to the existing search/research department requires its normal guarded integration and release. A review packet is already saved mode 0600 under `/home/ubuntu/.local/share/empire-brokerage-editorial/lincoln-park-us-original-sources-review-20261021.json`, and this branch has exact source/editorial owner review notes. No production agent timer was activated for the new code.

**Next useful engineering requirement (not accomplished by a green unit test):** a reliable bounded fresh-search adapter for real US and UK queries, with validated original source intake; accurate model-claim groundedness against actual source passages; current snapshot versioning through the original Research queue; reviewer signing/authority. Do not claim all tasks are finished before those gates.
