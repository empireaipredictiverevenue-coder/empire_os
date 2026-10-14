# ASTRA / JEV GTM V2 — Wave 7 Shared Vane/OpenManus Evidence-Gap Research

Date: 2026-10-14
Starting JEV commit: `7c6a2837`
Isolated worktree: `/home/ubuntu/empire_worktrees/jev_gtm_v2_20261014`
Mode: OBSERVE, zero paid model/API spend, no production activation, no CRM changes, no new agents/services/timers/databases, no outbound or payment authority.

## Goal

Finish the bounded, first-party **JEV Evidence Gap Research** integration using the existing independently authored Empire research prototypes informed by Vane and OpenManus. Reuse the exact same shared core for the YouTube and media programme rather than creating another research framework.

## Source and licence audit

Existing isolated intake examined:
- Vane (`ItzCrazyKns/Vane`) source snapshot `348feca3e378`, MIT.
- OpenManus (`FoundationAgents/OpenManus`) snapshot `3309bf4e416f`, MIT.
- The related Odysseus source (`odysseus-dev/odysseus`) is AGPL-3.0-or-later and remains external and **unmerged**.
- Independent EmpireOS research prototype: `/var/tmp/empire_odysseus_intake_20261010/empire-isolated-fork`. The intake explicitly states it adapted concepts and copied **no upstream Vane/OpenManus/Odysseus source**.

Transferred independently authored Empire modules, not upstream runtimes:
- `empire_os/research/deep_research_intake.py` — bounded research execution and source IDs.
- `empire_os/research/research_profiles.py` — speed/balanced/quality research plans inspired by Vane's mode/source selection and OpenManus's explicit stages.
- `empire_os/research/empire_search_adapter.py` — hooks to *existing* first-party Search Fabric and allowlisted primary-page inspector.
- `empire_os/research/__init__.py`.
- Original isolated module test suites `tests/research/test_deep_research_intake.py`, `test_research_profiles.py`, `test_empire_search_adapter.py` reused directly.

No new third-party packages, licensed binary, shell/browser agent, external model, worker, server, scheduler or graph DB installed.

## New first-party JEV integration

`empire_os/jev_gtm_research_bridge.py` provides:
- `plan_jev_evidence_gap`: takes the exact versioned JEV GTM V2 decision fingerprint and blocker codes and a narrow *approved public* niche/market. Produces deterministic bounded queries, policy hash and scoped evidence-gap plan.
- Canonical-only blockers (suppression readback, tenant/company identity, contact suppression) remain distinct from publicly researchable gaps (dated signal missing, contradictions). Public search can never clear authority blockers.
- Fixed research lanes: official, web, company. Maximum profile depth quality: 8 queries, 12 pages, 3 rounds; default speed: 2 queries, 4 pages, 1 round.
- `run_jev_evidence_gap`: explicitly injected governed search and inspector callbacks. No default network access. Reuses the shared research engine, preserves inspection URLs/content fingerprints and rejects unsafe links, malformed sources, forged original-page digests and exceeded budgets.
- Draft source-cited claims remain **unverified**. The commercial step is always blocked. Review packet deliberately excludes raw page snippets, model-generated claim text, source bodies, email addresses, contact details and arbitrary model tool execution.
- `attach_jev_research_review`: recomputes the original decision binding and returns a separate no-authority annotation. The original JEV action, signals, review queue, suppression status and economic/revenue result remain unchanged.

`scripts/probe_jev_evidence_research_v2.py`:
- `--fixture-smoke` runs the complete offline research/attachment path on fictional inputs without any network, DB, email or payment.
- `--decision-json --public-niche --public-market` creates a **plan only**, labelled `OFFLINE_UNAUTHENTICATED_PLAN_ONLY`; arbitrary local JSON cannot be treated as certified canonical data.
- Live HTTP research is not implicitly activated by this CLI.

Founder status `/v1/founder-jev/status` and standalone `/founder/jev` page include versioned research integration/readiness fields. No endpoint exposing live research execution is added. The existing Founder Console page and existing agents' production service remain untouched.

## Verification

- Original independently written research core: 13 tests and 5 subtests passed.
- New JEV bridge/operator tests: synthetic end-to-end cited research, malformed/SSRF URL rejection, bounded queries, missing sources, invalid privacy contexts, fake commercial authority, decision fingerprint mismatch, provider consistency, zero-spend/offline CLI and unchanged founder decision.
- Real Search Fabric *zero-key public smoke* on fictional UK roofing market input, with isolated `EMPIRE_SEARCH_HEALTH_PATH` and two bounded queries: `INSUFFICIENT_PRIMARY_EVIDENCE`, 0 original pages inspected, 0 sourced observations, 0 outbound sends. This is a **source coverage blocker**, not a proof that no opportunity exists.
- The same smoke confirms no commercial promotion, buyer intent, send authority or database action. Do not claim that real source facts were verified.
- Frontend TypeScript check: `apps/search-command-centre/node_modules/.bin/tsc --noEmit --incremental false -p tsconfig.json` exited 0 with reused installed dependencies.
- Full JEV/CRM/Conversation suite including new research: **539 passed, 1 existing Starlette/AnyIO dependency warning, 5 subtests passed**. No test failures.
- Python source compilation and git diff checks: verified before final commit.

## Actual completion and remaining activation gates

**Complete as isolated engineering:** shared core reuse, bounded JEV planning, controlled source inspection/citations, scoped review attachment, offline operator probe, founder status and dashboard wiring, regression fixtures.

**Not production complete:** actual live research usefulness (public source recovery currently returned no inspectable sources), independently authenticated source claims, live signed provider replies, provider attestation, tenant-bound customer identities, commercial model calibration, live founder review authentication/reader configuration, production branch merge/deployment, and separately approved migration 051.

No application of migrations 040/051, privileged DB access, production pushes, incoming-mail ingestion, outbound campaigns or funds occurred.

Next promotion work must improve first-party Search Fabric coverage and official-source retrieval first, then verify real source-cited observations and representative actual customer outcomes before labeling research as a buyer signal or putting it in the autonomous commercial decision chain.
