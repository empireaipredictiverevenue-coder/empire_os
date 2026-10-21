# Empire AI — Empire Research and Empire Agent internal product v1

**21 October 2026 · 2 usable internal products; not public or tenant SaaS released**
Source worktree: `/home/ubuntu/empire_worktrees/brokerage_us_uk_deep_research_owner_20261021`
Current owning branch: `review/brokerage-us-uk-deep-research-owner-20261021`

## Product 1 — Empire Research
Purpose: proprietary evidence-backed research workstation inspired by the capabilities demonstrated by the Vane prototype. Supports original-source comparison, provenance, limited quote anchors, source/rights warnings, UK + US and six vertical selectors. Original Vane source is not copied here.

**Working CLI:**
```bash
cd /home/ubuntu/empire_worktrees/brokerage_us_uk_deep_research_owner_20261021
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.use_empire_research_products_20261021 \
  --read-only --product empire_research \
  --country both --niche dental --depth quality --save-private
```

Speed, balanced and quality are **real original-source inspection budgets**: 1, 2 and 3 curated original pages per country respectively, subject to fewer pages when a site fails. Speed/balanced are explicitly partial, NOT full market verification. Quality uses all three independently curated per country. All depths are review-only.

## Product 2 — Empire Agent
Purpose: an internally usable, deterministic multi-step source research workflow inspired by OpenManus step receipts, without OpenManus unrestricted browser/shell, identity, external messaging, or money tools. Existing proprietary research runtime is the actual executor.

**Working CLI:**
```bash
cd /home/ubuntu/empire_worktrees/brokerage_us_uk_deep_research_owner_20261021
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.use_empire_research_products_20261021 \
  --read-only --product empire_agent \
  --country both --niche dental --depth quality --save-private
```

Six actual workflow steps: scope → discover original reviewed sources → inspect originals → evidence crosscheck → authenticated independent editorial review **AWAITING OWNER** → customer delivery/outbound **BLOCKED**. Done-for-review means research execution finished, not verified customer-ready copy.

**List product features:**
```bash
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 -m scripts.use_empire_research_products_20261021 --read-only --catalog
```

## Private Founder Console API candidate
New API factory `empire_os/founder_research_products_api.py` is registered in the existing `founder_dashboard_service.py` **only in this isolated branch**. It provides:
- GET `/v1/founder-research-products/catalog` — product catalog, all configured niches/modes
- POST `/v1/founder-research-products/preview` with bounded JSON `{ "product": "empire_research", "country": "US", "niche": "dental", "depth": "quality" }`
- POST `/v1/founder-research-products/preview` with bounded JSON `{ "product": "empire_agent", "country": "GB", "niche": "dental", "depth": "quality", "fresh_discovery": false }`
- Web candidate `/founder/research` with the same existing private Founder Console app; server-side Access session bridge only.

Service is intended for the existing **loopback-only Founder Console** and now fails closed unless a verifiable Cloudflare Access JWT with the exact Founder subject, issuer and audience is supplied. Identity deployment/configuration and a real authorised session remain independently unverified. It must NEVER be exposed directly to the public internet or white-label tenants, and there is NO live production web route until its original owner approves a guarded release. No separate shadow account service, CRM, DB or agent shell was created. See `EMPIRE_RESEARCH_FOUNDER_GUARDED_RELEASE_REVIEW_20261021.md` for exact gates, budgets, test receipts, owner approval requirements and rollback.

## Verified running product receipts

- Empire Research: 6 real original dental publisher/CMA pages inspected (US 3/3, GB 3/3), status `ORIGINAL_MARKET_SOURCES_OBSERVED_REVIEW_PENDING`, private saved receipt mode `0600`.
- Empire Agent: same real six-source research inspection with six individually status-coded workflow receipts, `WORK_COMPLETED_FOR_EDITORIAL_REVIEW`, private saved receipt mode `0600`.
- Owner-only directory: `/home/ubuntu/.local/share/empire-research-products`, directory mode `0700`, files `0600`, hash-derived filenames, exclusive creation (no overwrite).
- Test suite: `98 passed, 5 subtests, 1 unrelated Starlette/anyio deprecation warning` plus existing Founder Dashboard service route tests `4 passed` at review time. Live CLI runs succeeded.

## Limits to commercial release

1. Vane / OpenManus *inspired* products are standalone original EmpireOS Python capabilities, **not an installed upstream Vane frontend or OpenManus generic executor**. Real unbounded autonomous planning, general tool execution, dynamic browsing, browser actions, etc. are NOT enabled.
2. Source discovery beyond the curated originals remains provider-degraded/circuit-open in existing Search Fabric; repair authorised provider configuration before claiming general web coverage.
3. Editorial queue still has five historical DONE receipts with current source-snapshot mismatch. Do not alter original receipts or bypass reviewer identity/signature, source licence, data-rights or content checks.
4. Dental is working original-source reference. Roofing, solar, HVAC, legal, property have own UK/US source-intake plans but ZERO admitted original sector-specific research here; no cross-niche evidence borrowing.
5. Before white label: founder-approved deployment into existing private service, trusted tenant membership/authn/authz on every endpoint, verified per-tenant source custody and encrypted state, rate/budget limiting, concurrency and job controls, audit/observability, terms and licensed datasets, customer QA, send/finance checks.
6. No customer email, published client report, accepted order, invoice, checkout activation, financial transfer or recognised revenue was produced.

## Next owner action

Existing Research/Founder Console owner to inspect this exact isolated candidate and its tests, verify user identity path and service loopback configuration, then stage a guarded preview deployment with rollback. Preserve all commercial and editorial gates. SSH/terminal use is already functional. The new authenticated browser workstation is an **isolated build candidate only** until the existing Founder Console identity owner proves real session authority and authorises a guarded deployment; not a released SaaS product.
