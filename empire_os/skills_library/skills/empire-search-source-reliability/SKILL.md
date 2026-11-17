---
name: empire-search-source-reliability
description: Use this EmpireOS skill whenever Buyer Scout, Search Fabric, buyer discovery, SERP retrieval, provider circuits, search backoffs or zero fresh prospect domains fail or degrade. Diagnose original source evidence; prepare better industry-specific searches and controlled recovery actions without bypassing provider restrictions, creating another search engine, approving buyers or sending outreach.
license: Internal EmpireOS authored instructions; ownership review required before redistribution.
---

# Search reliability and source recovery

Recover **genuine useful search evidence**, not high request counts. This skill guides the existing EmpireOS Search Fabric, Buyer Scout and SkillForge. It is **not** another engine, scraper, agent, runtime, scheduler or provider account.

## Use these original components

- `empire_os.search_fabric.search` and `public_fallback`: search engine order, existing lexical-v2 relevance, provider cooldowns and source-rights constraints
- `empire_os.buyer_public_research_seed`: known seeds, low-yield deferral and original per-market query budgets
- `empire_os.buyer_scout_review_readiness`: original real buyer and identity admission gates
- `empire-lead-research` and `empire-identity-resolution`: company sources, dedupe, identity and original CRM suppression
- Current immutable evidence receipts under `/srv/empire_os/runtime/buyer_acquisition` and the existing shared provider-health record

## Procedure

1. **Read live source truth before deciding.** Run the bundled source audit in the existing EmpireOS Python environment:
   `python3 -B empire_os/skills_library/skills/empire-search-source-reliability/scripts/diagnose.py --root /srv/empire_os --intent service_customer --niche roofing --market 'Dallas Texas'`.
   This is offline read-only; it never calls a provider or changes persistent state. Verify the receipt's age and source schema. If missing, stale, malformed or unreadable, report UNKNOWN rather than provider health or fake zero demand.
2. **Separate the failure types.** Distinguish (a) active Scout two-hour low-yield defer, (b) actual per-provider HTTP 202/403/429/503 circuit, (c) search provider returning an access shell or unrelated results, (d) strict quality-gate rejection, (e) no new domains after canonical dedupe, and (f) buyer identity/product fit. These are not interchangeable. Never reset, truncate or bypass a cooldown to improve a count.
3. **Choose an authorised source ladder.** First reuse current official, first-party and *already entitled* business-registry evidence for the requested geography and company type; these may be stale and must be labelled as such. Then use an existing licensed Search Fabric provider, if its rights, credentials, costs and cooldown permit. Do not activate Brave while the existing source-rights hold remains. Never use public SearXNG instances as a workaround for rate limits; a self-hosted SearXNG instance is a future *component evaluation only*, not a new runtime or guaranteed supply. Common Crawl CDX is historical URL discovery, never current company existence, commercial intent or contact permission.
4. **Improve the query, not the approval standard.** Choose `service_customer`, `lead_buyer`, `publisher_partner`, or `company_data_buyer`; generate two or three concise, varied, unquoted market-specific queries with `--intent`, `--market`, and `--niche`. Keep the existing `lexical_v2` and first-party source classification. Prefer direct company websites. A listing on a directory, a sales blog or a publisher's marketing page does not verify purchase agreements, decision-maker identity or consent.
5. **Only perform a live probe through the ORIGINAL Search Fabric after all original gates and rights are satisfied.** The audit script does **not** execute network probes. A Scout owner may separately make one bounded existing-source query after the original defer and provider cooldown expire; do not schedule a new loop, expand query volume, use proxies to evade blocks, make bulk downloads or store restricted provider result bodies.
6. **Evidence and evaluation.** Report `0 fresh domains` only when a real query was executed; otherwise report `DEFERRED` or `UNAVAILABLE`. Cite original source receipts, retrieved date, provider class and quality filter status. Deduplicate by canonical company domain/identity; route potential service customers to their *real* product without demanding they publicly buy calls. Preserve all person, territory, accepted terms, rights and existing sender/CRM suppression gates.
7. **Declare a real recovery only with observable source results.** Verify the original scheduled Scout generates fresh, quality-passing source domains from rights-cleared providers, then check sampled first-party company identities and product fit against the existing buyer register. A search result is not a paid buyer or first sale. Keep data rights and all founder approval gates.

## SearXNG original pre-admission bridge (verified 10 November 2026)

When an **existing locally running** SearXNG JSON endpoint is authorised for
bounded research, reuse the original EmpireOS reader and site/identity gates
rather than treating a SearXNG result as a company or buyer. The optional
bridge is scripts/reconcile_searxng.py. Example:

python3 -B empire_os/skills_library/skills/empire-search-source-reliability/scripts/reconcile_searxng.py --searxng-local http://127.0.0.1:18888 --query 'roofing contractors Dallas Texas' --intent service_customer --max-results 5

The bridge accepts ONLY that localhost endpoint. It enforces the existing
Search Fabric lexical filter, original relationship-registry/Scout dedup,
first-party robots checks and bounded original site_probe with public_only=True.
Direct lead-buying evidence is assessed through the existing Buyer Scout
evidence assessor; service customers are NOT evaluated as lead inventory
buyers. Redirected domains, directories, missing business identity and
robots/access failures are held. **All** rows remain unapproved research
observations: complete CRM entity dedup, official business identity, buyer
contracts, contact permissions and commercial source rights must still pass
their original owners. Results cannot write to Scout or CRM.

Do not infer that this command starts SearXNG or enables a production
provider. The initial localhost trial starts/stops the pinned research
sandbox separately; no permanent service or timer was approved. The source
repository's AGPL obligations and provider/source-rights require legal-owner
review before a live customer-facing metasearch deployment.

## Evidence contract

Report only dated, attributed first-party source or rights-cleared provider observations with source receipts, query scope, market, provenance and original provider/status metadata. Label absent, stale, failed or unverified results as UNKNOWN or HELD, never as verified zero demand. A returned domain is not a verified company, buyer, consented enquiry, accepted transaction or realised revenue. No credential disclosure, external calls, payment, outbound, production write or authority is implied by this skill.

## Output contract

Return a concise operational JSON/report: source freshness, Scout backoff, per-provider eligibility (not assumed health), query variants, next allowed action, evidence gaps, legal/source-rights state and separately **observed fresh provider domains**, **verified companies**, **qualified buyers**, **outbound sent** and **revenue**. Never silently convert unknown into false or zero.

Default to `OBSERVE`, `execution_authority=none`, `database_writes=false`, `outbound_sent=false`, `paid_calls=false`. This skill gives advice only; adding it to SkillForge does not approve it for automatic agent loading. Any trust promotion must use the original digest-pinned registry, and any production action must pass the original owner approval process.

## Sources and evaluation

See `references/source-ladder.md` for official documentation and source limitations. Use the existing SkillForge review and a bounded synthetic/real-receipt diagnostic benchmark; never judge the skill by how many irrelevant domains it finds.
