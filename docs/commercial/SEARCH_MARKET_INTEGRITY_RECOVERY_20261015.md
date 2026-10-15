# Search Fabric market integrity and buyer-territory recovery

15 October 2026 | Sovereign first-party OBSERVE | Zero additional spend

## Live diagnostic, not an invented search success

The already installed UK/USA/Australia/Canada buyer-acquisition scout completed a successful 16:37–16:41 UTC natural run and admitted the official programme seeds. Its web search still returned **zero fresh query domains**, though site-based research reached Australian Solar Quotes and LiveLeads Canada.

Read-only examination of Bing's response to `solar affiliate program Australia` found 10 organic blocks from *French solar/e-commerce pages*, with no qualifying programme/affiliate/Australia match. The relevance gate correctly rejected all 10. DuckDuckGo returned HTTP 202, Mojeek 403 in the existing search diagnostics. A separate single market-specific Bing query, using Australia canonical locale and `mkt=en-AU`, returned `PROVIDER_DEGRADED` with no verified organic results. **Country routing is improved; public Search Fabric availability is NOT yet recovered.** Do not weaken the semantic gate to manufacture buyer counts or bypass blocked search engines.

## Tested code-only changes

1. Search Fabric resolves explicit countries Australia, Canada, United Kingdom/UK, and United States/USA, using the existing EmpireOS registered market geography rather than relying on the hosting IP. Bing requests use canonical country, language and market only where the registry is unambiguous. Canada-wide queries retain an unknown language (English/French market split). Conflicting country/city queries fail closed.
2. NYC permit territory evidence now requires complete location phrases (`NYC`, `New York`) or a full borough name with nearby `NY`. The previous substring check could falsely match `Queens` inside `Queensland` and `York` inside `Yorkshire`. Overseas company records no longer inherit a spurious New York corridor from those words.
3. The original query count, search engines, rate limits, circuit breaker, cache TTL, country directory, buyer-scout timer, source custody, fail-closed proof categories, and third-party purchasing restrictions remain unchanged. No new proxy, paid provider, scraping workaround, timer or database.

## Verified alternative when public SERPs are blocked

Reuse the existing public-research programme seed cohort, first-party site evidence probes, buyer verification queue and COO/BD qualification. This yields **research candidates only**, not accepted lead buyers. Require first-party company verification, prior contact/suppression checks, postcode/ZIP and niche buy box, accepting human buyer, terms, agreed payout and event settlement before admitting any commercial capacity or touching customer data. Do not infer source acceptance from a public affiliate landing page.

## Deployment gate

Code-only release changes just `empire_os/search_fabric/search.py`, `empire_os/buyer_acquisition_scout.py`, dedicated regression tests and this note. No service restart. Verify both modules are untouched by other agents and service state is idle before releasing; retest the exact resulting production tree. Normal timer will pick up the changed code at the next natural invocation. Any prior runtime artefacts with misleading NYC evidence should be treated as historical; do not retroactively rewrite other agents' canonical sources.
