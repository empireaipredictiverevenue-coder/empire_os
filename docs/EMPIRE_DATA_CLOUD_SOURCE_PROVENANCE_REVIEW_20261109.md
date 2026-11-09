# Empire Data Cloud — original customer search provenance fix

**9 November 2026.** Bounded add-on to the existing original customer API review in PR #157. This branch is based on the PR's exact reviewed head `5ad4779bc`, not on the large, diverged founder-session feature branch. It is a **source review**, not a deployed service or a duplicate product. Customer routes, payment, provider access and database permissions remain unchanged.

## Previously unsafe contract

- The request-side source-use gate originally saw query/limit but not the authenticated tenant or configured collector identity. A collector switch could execute outside the customer's intended source-use policy.
- The result-side source-use gate originally saw payload only. A policy for one tenant or collected source could mistakenly govern another.
- Search response assembly stamped current retrieval time without retaining actual source observation time, allowing cached evidence to masquerade as fresh.
- Raw provider URLs could be HTTP, credential-bearing or internal, and degraded provider responses could be mistaken for genuine zero-hit results.

## Minimal correction in the existing API

The server-side `search_source_id` is fixed before any reservation; missing/invalid identity fails closed, and the existing gateway factory still provides no customer search adapter. Request preflight receives `(tenant_id,source_id,query,limit)`; post-provider rights checks receive `(tenant_id,source_id,payload)`. Source identity is enforced on the returned payload, with bounded 24-hour, timezone-aware observation provenance, operational search-state validation and public HTTPS-only result links. The returned result clearly distinguishes `observed_at` (source) from `retrieved_at` (response). Stale caches, source swapping, untrusted URLs and outages are not offered as customer data.

Original explicit research-only/NO_RESALE flags retain precedence over any permissive test callback. This work does not infer or supply actual commercial source rights, cost invoices, confirmed user sales, or a first-party site consent grant. `licensed_search_output` remains FALSE and `search_adapter` remains NONE in the existing owner gateway factory.

## Proof and release boundaries

- Isolated original feature worktree: **358 targeted tests PASS**, 2 expected third-party warnings.
- Clean PR #157-based review worktree: **80 targeted tests PASS**, 1 third-party warning. These include provider/tenant mismatch, stale cached source, unhealthy provider, unsafe link, no rights/no provider reservation and existing founder usage flows.
- `SOURCE_PROVENANCE.json` retains the original source archive hash and pins this exact changed `durable_api.py` SHA.
- **NO** changes to production routes, live EmpireDB schema, protected keys, provider spending, billing, restart, outreach, or deployment.

**Operational truth:** founder `GET /v1/data/usage` was previously verified live; customer search and site-audit POSTs are still NOT mounted (404). No external supplier agreement is required to operate our own collector. Customer search release requires the existing authenticated-tenant and source-use controls, appropriate compliance with actual target-site terms/privacy obligations (not an assumed supplier contract), the original metering and gateway owner checks, and real integration tests. A passing synthetic callback is not live deployment evidence.

## Source cost integrity closure — 9 November 2026

One additional defect was discovered and repaired in the same original API. Previously, a provider's own JSON field `provider_cost_receipt.verified=true` and claimed cost could be promoted directly to an `actual_usd_micros` ledger entry. That is **not independent evidence** of a provider invoice or settled cost. An external provider, upstream aggregator or compromised adapter could mark its own amounts verified.

The original `run_operation` now sends the **authenticated tenant, operation, and gateway-selected source identity** into an optional separately supplied `cost_receipt_verifier`. The verifier must independently reconcile against an owner-controlled invoice/call ledger and return its own actual amount/reference tuple; only that tuple reaches the existing metering settle call. A provider's claimed number is never copied as trusted actual. With no receipt, cost remains **unknown (NULL), not $0**. With an unverified, malformed or un-reconcilable receipt, the request is settled as a held provider error and does not return customer data; no billing is enabled. Tests cover false `verified:true`, mismatch, negative/malformed receipts, independent resolver outage and exact trusted amount/reference continuity.

For source archive accuracy, the original candidate source archive SHA stays fixed and unchanged, but `only_import_rewrites` is now explicitly **false** because hardening genuinely changed the converted module. The candidate provenance test was updated to enforce this truthful state and exact converted file digest.

There is **no universal supplier-contract blocker** for this first-party collector. Cost reconciliation is required only if an adapter reports externally charged costs; the existing no-receipt path correctly records unknown external cost as NULL and does not prevent an internal no-paid-provider operation. Actual customer routes still require owner-controlled metering/gateway admission and valid, source-specific use policy; no assertion is made that a hypothetical supplier contract or invoice is needed.

## Founder correction — first-party self-collection, not supplier dependency

**Corrected 9 November 2026:** EmpireOS already owns Search Fabric and direct public-search collectors. Data Cloud is a first-party acquisition/intelligence API; it does **not** require a Decodo, Smartproxy, scraping-data vendor or resale supplier contract as a prerequisite. The `search_source_id` identifies our configured collector and underlying evidence lineage. The existing gateway-factory default of no customer search adapter is an owner-controlled release setting, not proof that a supplier must be procured. The legacy `licensed_search_output` internal configuration name means operator review of proposed customer output; it must not be interpreted as a mandatory vendor contract. Specific external-site access and output use still must respect actual terms, robots, privacy, and other applicable obligations, evaluated based on the actual source and intended use.

**Evidence distinction:** internal Search Fabric is already implemented; this PR fixes tenant/source provenance and actual-cost accounting. It does not establish a completed customer deployment. Live customer search POST remains unmounted, and the existing dedicated meter role lacks `reserve`/`settle` grants, so production write-capable customer transactions cannot currently run. No third-party licence search should be used as a generic deployment gate.


## Real first-party Search Fabric bridge — 9 November 2026

The ORIGINAL gateway_candidate_entrypoint.py has been extended with an optional, explicit first-party collector connection, not a separate service or supplier. When the existing gateway owner selects enable_first_party_search=True and supplies the existing trusted tenant/source-use callbacks, the factory wraps the established empire_os.search_fabric.public_fallback.search_public_web direct public fetch (HTTP GET, never the cached or optionally paid Decodo search_reliable route) and the existing empire_os.search_fabric.search._quality_filter. No new search/ranking engine is introduced; default remains disabled and the existing founder GET usage behavior is unchanged.

The wrapper requires positive provider-availability evidence, validates known upstream engine identities, runs the original relevance filter, returns bounded results, and records fresh observed_at distinct from response retrieved_at. The original Data Cloud formatter additionally exposes the actual upstream engine alongside EmpireOS collector identity. Missing/mismatched source policies, unavailable providers and failed quality assessment produce no customer data and no automatic provider spend or service rollout.

**Observed real backend proof:** via existing EmpireOS-owned search_public_web and existing _quality_filter in a read-only isolated invocation, the search 'python programming language' returned **3** filtered results; upstream recorded bing_html, collector identity empire_search_fabric_public, and fresh evidence timestamp. This proved the **collector-to-original-customer-formatter path**, not a live authenticated customer transaction. All new HTTP-path tests use a synthetic metering store and an injected fetcher; no production SQL write or gateway change.

**No external supplier agreement required:** the software is our first-party collection stack, though individual upstream pages and downstream uses still have source-specific rules. The actual customer POST is still not mounted in production. The original owner must wire the approved source-use callbacks and already-existing metering/gateway route before claiming customer access.
