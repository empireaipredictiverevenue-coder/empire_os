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

## Scoped founder first-party search release assembly — 9 November 2026

The existing original gateway route assembler now supports an **opt-in search_pilot** scope: only GET /v1/data/usage and POST /v1/data/search. POST /v1/data/site-audits remains UNMOUNTED in this limited release. The code reuses the original signed founder Data Cloud verifier, original customer API and existing EmpireDB metering interface; no new router/service, role, migration or supplier dependency was created.

Original usage-only and full three-route behavior remains unchanged. Search pilot requires the existing usage-pilot acceptance and two additional directly relevant facts: **source_egress_and_rights_reviewed** (actual first-party public collection source-use review, not a supplier contract) and **production_meter_write_functions_verified** (dedicated login can call existing reserve and settle functions). It does not require another unrelated site-audit rollout or off-host physical recovery exercise. Boolean evidence from isolated tests is TEST-ONLY, not actual operational approval. Actual read-only production inspection on 9 Nov confirms dedicated meter login has authenticated usage read permissions but not reserve/settle EXECUTE; search pilot is therefore not eligible for live activation today. No privileges were altered.

A new end-to-end isolated signed-session test exercises the real existing gateway assembler and original Data Cloud search API with a valid synthetic signed founder session, authenticated tenant, controlled first-party collector output, synthetic quota reservations and settlement, proof of no-store/nosniff headers, rejection of no session, and revocation of founder access. Tests also verify that missing actual write-function grants or source-use evidence prevents mounting ANY route, and that usage-only and search_pilot cannot accidentally be enabled together.

This is **tested/committed software**, not a claim of production installation. The current production GET usage endpoint remains protected, while search/site-audit POST endpoints remain unmounted. No extra backup work, paid provider, external supplier or production mutation was performed.

## Current production meter readback, without any write — 9 November 2026

Independent read-only EmpireDB verification against the ORIGINAL schema, no migrations:

- Existing dedicated login empire_data_cloud_meter_login: EXECUTE authenticate = TRUE; usage_snapshot = TRUE; reserve = FALSE; settle = FALSE.
- Existing Data Cloud tenants: 1 total, 1 active and not held, **0 active search-entitled**. Site audit remains 0 active entitled.
- Existing Data Cloud keys: 1 active (key contents and tenant identity not queried or printed).
- Existing public gateway: GET /v1/data/usage responds 401 to unauthenticated requests; POST /v1/data/search and POST /v1/data/site-audits remain 404 (not mounted).

This identifies the **smallest actual original-owner activation delta** for a *founder-only first-party search pilot*: (a) review the existing meter reserve/settle stored-function ACLs under the dedicated login, (b) explicitly enable the search operation on the appropriate existing active tenant, and (c) use the existing gateway owner's search_pilot=True route selection and first-party source policy callbacks with a verified rollback. No table migration, new data vendor, new service or off-host recovery project is necessary for this restricted pilot. These actions are NOT executed by this review branch; there has been no production entitlement expansion. Do not label test-fixture booleans as actual DBA or owner approvals.

Search pilot only mounts usage + search; site audits remain 404 until separately designed and accepted. All real revenue, billing, customer output and supplier spend remain unproven and are NOT asserted by this release candidate.


## Original PG18 cost settlement mismatch closed — 9 November 2026

A direct read-only inspection of the **ACTUAL deployed** empire_data_cloud_api.settle SQL exposed a critical integration defect: it deliberately sets tenants.held=true when p_reported_cost_micros / p_evidence_ref are NULL, even if state='provider_error'. Prior API code reported unknown cost as NULL for every first-party HTTP search and passed NULL for every provider_error. Therefore granting search entitlement and mounting the route before this fix would have held the founder's tenant after the first successful FREE search or first failed source fetch. The existing API unit mocks did not exercise real PG18 SQL semantics.

**Minimal fix in existing original Data Cloud API, no SQL migration:** only when the original gateway factory explicitly selects our own direct-public Search Fabric adapter with no paid search API, the trusted operator supplies first_party_direct_public_no_paid_fee=True and the API settles **external paid search API fee 0** with the stable provenance reference empire_fabric_direct_public_no_paid_api_v1. This zero is NOT the full infrastructure, CPU, bandwidth, payroll, or other business cost. Both an accepted public-search result and a failed free fetch use this same provider-fee evidence. Any unexpected provider_cost_receipt in this route disables the free assumption and follows the stricter independent-reconciliation path. For third-party/unknown providers, no free claim is inferred; missing/uncertain costs remain held by the existing PG18 ledger.

**Independent source SQL verification:** a new disposable Unix-socket-only PostgreSQL 18 process compiled the original exact, unchanged 2026-11-07 review SQL, seeded only synthetic tenants/keys inside its isolated DB, and demonstrated:
- completed + 0 external paid search fee/reference => completed, tenant not held
- provider_error + 0 external paid search fee/reference => provider_error, tenant not held
- provider_error + NULL cost and NULL evidence => cost_integrity_hold, tenant held as originally designed
- No production DB connection, SQL change, role grant, migration, customer request or secret. Disposable isolated cluster stopped on exit.

This is a confirmed code/SQL contract repair in the already approved first-party product path, not an attempt to lower the existing DB cost safety policy. The original production search route remains unmounted; customer-API release/permissions remain with the original existing gateway and DBA owner.

## Codex + independent review: original protected gateway additive search — 9 November 2026

The existing authenticated Codex CLI ran against the **clean owned Data Cloud worktree** and implemented an opt-in search mode in the ORIGINAL public-gateway entrypoint (not a new service or new router). Default founder usage-only startup remains unchanged. Search opt-in requires the existing founder-approved usage release, exact first-party flag, a protected SHA256-pinned owner release receipt, source/tenant identity, successful original SEARCH_PILOT_REQUIREMENTS readback, and hashes of each executable source file. Neither the original CRM issuer nor the existing LinkedIn/browser host route is replaced. Search-enabled selection adds only original GET usage + POST search; site audit remains unmounted.

An independent read-only Codex review identified a genuine P2 source-provenance issue: validating on-disk release files alone does not guarantee that Python executes those bytes if another overlay preloaded a module in sys.modules. The original release validator was corrected to import each required EmpireOS Python module and enforce exact loaded module-file path equality with the SHA-pinned release file. A synthetic mismatched preloaded module now fails closed, with no route mount. Corrected synthetic fixture mistakes (factory invocation and shared verifier class shadowing) without modifying runtime implementation.

**Verified:** the deployed original gateway entrypoint's baseline SHA256 equals the proposal branch's pre-change baseline, protecting the existing multi-owner overlay. After integration and independent reviewer fix, **215 scoped tests PASS** with 2 known nonblocking warnings. All changes remain in the existing PR worktree; no live DB privileges, tenant entitlements, receipt, service, restart or production route have been changed. Existing live GET usage 401 without session, POST search 404, POST site audits 404 until owner-controlled activation. The genuine remaining release operations are scoped search entitlement, reserve/settle privileges, protected source pin/owner receipt, and unchanged-gateway rollback verification — not a supplier contract, new module, off-host backup exercise, or paid provider.


## Founder first-party search owner publisher and actual zero-budget admission — 9 November 2026

Codex created the guarded owner publisher in `scripts/activate_data_cloud_search_pilot_guarded_20261109.py`. Original safeguards from the previous live usage release remain reused; source/user/CRM identity and existing route activation are preflight-checked, with one new frozen versioned gateway release, a single lexically last additive systemd drop-in, exact source pins, owner-scoped receipt, exact founder-tenant conditional SQL and rollback. The script is OFF by default and requires an explicit privileged `--apply-founder-approved` invocation; no separate service or data vendor is needed. The pilot is still **not live** until the full owner verification completes and the real protected endpoint works.

Independent read-only inspection identified a concrete zero-cost-budget issue not captured by API mocks: the actual founder tenant has monthly_request_cap=3, monthly_cost_cap_micros=0 and search_cost_ceiling_micros=1. The unchanged original PostgreSQL reserve function holds a one-micro-dollar provisional reservation against the monthly cap for each search even when the settled external paid API fee is 0; reserved_cost is retained after settle. The existing table constraint requires search_cost_ceiling_micros >0, so setting it to 0 cannot work without a schema migration. The **minimal existing-schema founder pilot correction** therefore adds 'search' to allowed_operations and raises only the founder tenant's *internal metering reservation ceiling* to 3 micros (3 requests × 1 micro). This is **not** an external paid-provider purchase or permission to spend; direct public Search Fabric only, paid provider calls and billing disabled. On rollback, the tenant's original 0 reservation cap, privileges and operations are restored. No changes to other tenants, API keys or database objects.

The new independent offline verifier `tests/test_data_cloud_search_owner_publisher_20261109.py` uses the **original exact pinned PostgreSQL 18 SQL** in a disposable Unix-socket-only cluster. It runs the owner publisher's actual conditional SQL to grant only reserve+settle, update only the synthetic founder tenant's operation+internal reservation cap, reserve and settle three verified 0-paid-provider-cost searches, and then run its SQL rollback. It checks the database state returns exactly to the preimage. Additional tests cover optional original systemd EnvironmentFiles, no invented supplier requirement, exact scope and missing release approval. Local disposable testing is not proof of a production deployment.

CodeX original pass and targeted follow-up initially timed out, after making the release candidate. The verified fixes are retained in this SAME original PR branch. The reviewer must separately approve the executable owner publisher and protected release evidence before any live invocation. Do not claim production success from tests or staging. No SQL migration, unrelated backup or alternative platform needed.


## Live guarded activation #1 rollback and exact import provenance correction — 9 November 2026

First founder-only original gateway apply was run after complete protected --preflight PASS. At startup, `load_search_release` failed closed with `first_party_search_release_not_verified` because the new exact-path test would not accept an already-imported original EmpireOS module. The guarded owner publisher automatically rolled back: original public gateway and private CRM remained ACTIVE; /, /commercial, /robots.txt returned HTTP 200, unauthenticated usage returned 401, search/site-audit remained 404, DB founder tenant held=false, old search entitlement absent, original monthly_cost_cap_micros=0, meter login reserve/settle EXECUTE=false, existing usage rows=0. The additive v1 overlay and frozen directory were removed; the root-only rollback journal recorded rolled_back. **No production search launch occurred** and no lasting DB/route permission change was left.

The verified narrow fix retains byte-for-byte provenance and path trust: a preloaded module may be executed from the existing original canonical EmpireOS source or original immutable founder usage release ONLY if its exact original file SHA256 equals the separately pinned release SHA256. Unknown paths, changed bytes, redirected symlinks or world-writable sources fail closed. This does not bypass independent source-use checks or permit unreviewed imported code. Tests now cover identical preloaded original source acceptance and altered source rejection. The fresh v2 additive frozen release/overlay/state paths preserve the earlier rollback journal rather than hiding or overwriting it. No new service, DB migration, paid provider, SEO or unrelated work.
