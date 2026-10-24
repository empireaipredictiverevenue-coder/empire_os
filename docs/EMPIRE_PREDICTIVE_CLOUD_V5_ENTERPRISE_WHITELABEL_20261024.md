# Empire AI Predictive Cloud V5 — white-label and partner API research handoff

**Date:** 24 October 2026
**Branch:** `feature/prime-universal-evidence-fusion-20261024`
**State:** original EmpireOS / EmpireDB / Smart CRM research only; **not deployed or activated**.

## User-provided V5 architecture preserved

V5 envisions an enterprise multi-tenant, resellable Predictive Revenue/Profit Engine with branding, custom domains, APIs (REST, gRPC, GraphQL), global CDN, Kubernetes autoscaling and Redis Cloud features. Its attachment references (`Attachment.png`) did not include actual attached infrastructure diagrams, domain verification receipts, cloud accounts, measured latency or simulation records. This handoff does **not** claim those exist.

### Audit of existing code and decisions

- Existing `empire_os/whitelabel.py` maintains a legacy separate SQLite-backed white-label registry. It is **not authoritative** for modern CRM tenant identity or billing. This build does not write to it.
- Existing `empire_os/revenue_crm_signed_auth.py` can verify issuer, audience, signed EdDSA token, current tenant membership and **`crm:read` only**. That is permitted only for a synthetic preview in this research branch; CRM read access must **not** become public partner-admin, dispatch, money movement or domain activation authority.
- Existing canonical tenant authority is original **EmpireDB PostgreSQL**, with the original Smart CRM continuing as the sole CRM. V5 research uses composite tenant IDs and FORCE RLS; no new CockroachDB, schema-per-tenant, Supabase, Kubernetes, Vault or cloud subscription is created. Schema-per-tenant should be considered only after an independent tenancy/operations review; a tenant-specific schema alone doesn't automatically provide isolation.
- Existing V4 Redis shadow is unconnected. Cache key prefixes and rate-limit counters cannot substitute for independently authenticated tenant authority, canonical EmpireDB audit, or production-grade rate limits.

## New actual scoped V5 build

1. `empire_os/predictive_cloud_v5_whitelabel_shadow.py`: strict synthetic-only branding/tenant configuration candidate, opaque logo digest, colour and supported plan validation; ASCII DNS hostname rejection including IPs, wildcards, reserved Empire domain and malformed hosts; caller-provided Cloudflare/DNS/TLS flags always remain **untrusted**, even when reported true; host cannot independently select tenant.
2. Existing original `empire_os/predictive_cloud_status.py`: safe, read-only `v5_white_label_shadow` status field alongside V4 Redis status. `WHITE_LABEL_V5_NOT_ACTIVATED`, no subscriptions, live tenant routing, API keys, billing or execution authority are claimed.
3. `migrations/empiredb/063_v5_whitelabel_candidate_registry_held.sql`: transactional, **held** metadata-only brand and unique custom-hostname candidate tables, with `PENDING_REVIEW`, `UNVERIFIED` and `HELD` database constraints. Tables use FORCE RLS with owner-only NOLOGIN migrator policies, no runtime table grants. Existing canonical EmpireDB CRM membership and real verified custom-domain ownership are **not** inserted/attested by this candidate schema. It is intentionally unable to transition to ACTIVE.
4. `scripts/rehearse_predictive_cloud_v5_pg_registry_20261024.sh`: real PostgreSQL 18 ephemeral fixture. Refuses port 5432 and non-`/tmp/pg_virtualenv.*` server data directory, tests wrong DB, duplicate migration, cross-tenant duplicate hostname claim, malformed hostname, reserved domain, nonexistent tenant, unauthorized SELECT/INSERT and attempted owner/activation state promotion; temporary DB dropped at exit.
5. `empire_os/predictive_cloud_v5_held_api.py`: **unmounted** GET status, disabled POST `/v5/router/dispatch`, disabled POST `/v5/admin/tenants`, WebSocket `/v5/metrics/stream` refuses before accept. This is an owner-release test barrier, **not an authenticated production API**. No public routes are mounted in `empire_os/hub.py`.
6. `tests/test_predictive_cloud_v5_whitelabel_shadow.py` and `tests/test_predictive_cloud_v5_held_api_and_pg.py`: signature/tenant/header mismatch tests, host conflict, forged status, prohibited API paths, unknown recipient, RLS/SQL registry, and source status tests. No real hostnames, customers, billing or payments created.

## Required implementation/release gates (original owners)

- **Identity/CRM/EmpireDB:** owner-signed tenant membership, explicit partner-role scopes separate from `crm:read`, audit and revocation; authoritative tenant+domain mapping, transaction-safe uniqueness and FORCE RLS; approved DB backup, migration, rollback and least-privilege roles. Do not use `X-Tenant-ID` or Host as independent proof.
- **Cloudflare/DNS/Edge:** verify actual account and SSL for SaaS entitlement, owned base domain, authoritative domain ownership, active certificate and correct CNAME/edge routing from authenticated sources; handle reclaims and tenant reassignment safely. V5 does not own `custom.empireai.io` merely because the architecture names it. Require independent DNS/TLS status and timing benchmarks; under 1 ms is not established.
- **Predictive Cloud V4 Redis:** acquire approved Redis Cloud plan, TLS/ACL and verified network topology from existing Scaleway; benchmark p50/p95/p99, region lag, stale reads and shard pressure before claiming 500k IOPS or zero latency. Redis eventual consistency/Streams cannot settle money or confer irreversible permissions.
- **API Security:** separately signed OAuth2/JWT partner tokens and scopes; per-tenant/client rate limiting with Redis availability fallback and abuse protection; request schemas; idempotency; structured errors; audit; WebSocket tenant authorization, backpressure and non-leaking telemetry. The current API prototypes are intentionally disabled.
- **Brand/SaaS Ops:** vetted asset rights, safe SVG/image rendering, content security policy, per-tenant CSS palette and email sending-domain verification. No automated email or sender-domain change yet.
- **Financial/Legal/Enterprise:** canonical EmpireDB immutable orders/settlements and genuine realised profit, pricing/contract approval, lawful data storage/retention and regional privacy controls; owner-controlled payment activation and human approval for binding contract, funds and production tenant provisioning.

The user mentioned having simulation data in an earlier turn; **no CSV/JSON/Excel simulation records are included in the current V5 architecture paste**. Ingestion, forecasts and margin reports cannot be represented as measured results until actual data is supplied and validated.

### Verified fixture scope and limits

- The research fixture uses fictional tenants, JWT keys, hosts and domain state. All test writes are to an automatically destroyed PostgreSQL cluster; original production cluster 5432 is untouched.
- Simulation values and inferred white-label ROI, enterprise valuation, zero downtime and cloud benchmark claims are not verified.
- Research branch only; no GitHub merge to live production; no active Cloudflare custom hostname, Redis Cloud, credential vault, funds, outreach or real notification.

**One original EmpireOS. One original Predictive Cloud V5. One canonical EmpireDB PostgreSQL. One Smart CRM.**
