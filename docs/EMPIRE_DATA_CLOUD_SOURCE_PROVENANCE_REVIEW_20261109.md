# Empire Data Cloud — original customer search provenance fix

**9 November 2026.** Bounded add-on to the existing original customer API review in PR #157. This branch is based on the PR's exact reviewed head `5ad4779bc`, not on the large, diverged founder-session feature branch. It is a **source review**, not a deployed service or a duplicate product. Customer routes, payment, provider access and database permissions remain unchanged.

## Previously unsafe contract

- The request-side supplier rights gate originally saw query/limit but not the authenticated tenant or supplier identity. A provider switch could execute outside the customer's authorized source.
- The result-side rights gate originally saw payload only. A licence for one tenant or supplier could mistakenly govern another.
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

**Operational truth:** founder `GET /v1/data/usage` was previously verified live; customer search and site-audit POSTs are still NOT mounted (404). Only an original owner with independently verified supplier redistribution permissions, source-specific entitlement, DBA rights for meter reservation and guarded release acceptance may turn on customer search. A passing synthetic callback is not licence evidence.
