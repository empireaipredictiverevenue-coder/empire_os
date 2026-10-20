# Empire AI — Crawl4AI + Browser Use + OpenHands existing owner integration
20 October 2026 | Branch feature/a2a-commercial-signal-mining-20261020

## Scope and implementation

Founder requested working, online data mining, plus relevant open-source
agents, without duplicated source collectors or invented buyer confirmations.

Implemented a *single-fetch, multi-extractor* source lane in the already
deployed, fixed-manifest daily first-party source service:

  approved HTTPS company homepage + robots.txt + cap / source SHA
              |
              +--> Scrapling 0.4.15 selector extraction, offline
              |
              +--> Crawl4AI 0.9.5 Markdown conversion, offline isolated process
              |
              +--> Source evidence (same original SHA, no raw page content)
                             |
                     hourly A2A evidence review
                             |
                 Buyer Scout review-only owner tickets

There are no additional site requests from Scrapling or Crawl4AI.
Crawl4AI's headless Playwright crawler is not launched or exposed, because
these sites are currently extractable without one.

Modules:
- empire_os/a2a_crawl4ai_offline_bridge_v1.py:
  isolated Python subprocess, fixed executable/script, 12-second timeout,
  400,000-byte input max, SHA receipt, allowlisted HTTPS homepage,
  hard fail-closed if missing or untrusted output. No model API call.
- scripts/offline_crawl4ai_parse_20261020.py:
  Crawl4AI DefaultMarkdownGenerator receives previously fetched HTML via
  stdin and converts internally. Emits bounded aggregates only (char count,
  heading count, package version and original SHA). Raw markdown, email,
  phone, person names, business copy and source text are not exported.
- empire_os/a2a_first_party_site_recovery_v1.py:
  existing Source fetcher invokes BOTH offline parser hooks only after a
  successful robots-allowed HTTP200. A parser error never authorizes
  another fetch or customer promotion.
- empire_os/a2a_first_party_recovery_readback_v1.py:
  cached evidence enforces the original HTML SHA against both extractor
  receipts; tampering fails closed; stale source over 7 days held.
- scripts/run_a2a_commercial_intelligence_cycle_v2_20261020.py:
  hourly report refresh now includes Crawl4AI totals and the new optional
  tool readiness report.
- empire_os/a2a_source_route_resilience_v1.py:
  reports per-market Crawl4AI coverage separately from Scrapling, provider
  health, and actual buyer verification.
- empire_os/a2a_optional_source_agents_v1.py:
  prepares a Browser Use task only when an approved, robots-allowed HTTP200
  site truly has inadequate static extraction. ROBOTS_POLICY_HOLD and
  CONTENT_TOO_LARGE explicitly NEVER trigger a browser workaround. Bounded
  one-page job, source-owner approval, sandbox and authenticated receipts
  required before any browser run.
  Existing OpenHandsWorkspaceRequest/build_openhands_workspace_contract is
  used to prepare a disposable-code-workspace ticket for repairing Search
  Fabric provider health. No standalone coding agent is launched and no
  production code is mutated by this contract.

## Isolated installed tooling

- Crawl4AI 0.9.5 at
  /home/ubuntu/.local/share/empire_a2a_crawl4ai_venv
- Scrapling 0.4.15 at
  /home/ubuntu/.local/share/empire_a2a_scrapling_parser_venv
- Browser Use 0.13.11 at
  /home/ubuntu/.local/share/empire_a2a_browser_use_venv
- Existing Agent Reach at /opt/empire/agent-reach
- Existing OpenHands code workspace contract in
  empire_os/openhands_workspace_adapter.py

All runtime installations are outside the main production Python environment.
Browser Use is importable in its own isolated venv, but no authenticated
agent/model provider, Playwright browser and isolated browser sandbox were
independently verified or enabled for it; executing Browser Use is NOT live.
OpenHands executor also not running. Ubuntu user cannot access the Docker
daemon socket, so privileged/sandboxed OpenHands deployment is held and must
not be worked around by running a fully privileged local code agent.

Agent Reach: public RSS/web reported OK by doctor; account-backed Reddit,
Facebook, Instagram, LinkedIn remain OFF. Doctor readiness is not a live
targeted query or source permission.

## Operational test (20 October 2026)

Existing daily systemd service was started after code changes:
  Result=success; ExecMainStatus=0

Fixed approved site manifest: 9 websites attempted; 7 HTTP200/robots-allowed.
Same 7 bodies successfully structured by Scrapling and transformed offline
by Crawl4AI. One NYC site robots unknown, one NYC page >400,000 bytes:
both held; no bypass or alternate browser attempt.
Buyer Scout reviewable public business website evidence: 7
Real independently verified buyer requests: 0
Real buyer capacity, prices/terms, accepted leads, verified purchases: 0
All outbound messages, campaigns and payments: 0

The hourly worker runs separately, reads these cached signed-shape receipts
and prepares owner review packets. It does not send or approve them.
The other source agent classes are inventoried / planned, NOT activated.

## Search source failure remains open

Search Fabric DuckDuckGo 202, Mojeek 403, Bing quality rejects; existing
public research status NO_FRESH_DOMAIN_RESULTS_PROVIDER_HEALTH_UNVERIFIED.
A private browser or stealth setting cannot be used to bypass these access
limits, and SearXNG can't guarantee it restores them. Existing Search Fabric
owner should approve and integrate a licensed official discovery API, with
health metrics, attribution and query cost, before scalable fresh company
discovery. Do not create duplicate owners or add paid credentials without
their authorization.

## Next real launch integration steps

1. Canonical Buyer Scout accepts the scoped evidence contract and verifies
   company identity, service ZIPs/territory, buying need, commercial capacity,
   canonical duplicates and permitted contact.
2. Search Fabric owner tests an authorised licensed official search API for
   new source discovery; returns provider-specific receipts. One-time approved
   first-party websites do not constitute continuous new-company prospecting.
3. Source owner approves any Browser Use JavaScript-only use case, executes in
   a separate sandbox with audited tools, no login, no social bulk messaging.
4. OpenHands coding owner launches only in an independently isolated
   workspace with reviewed changes and tests. Never point a coding agent at
   /srv/empire_os or credential-bearing paths on this shared server.
5. Complete a reviewed mainline merge and production deployment after
   owner acceptance. Current working services run from a feature worktree.

## Verify / rollback

cd /home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020

# Operate existing daily source job, no new source collector
XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
 systemctl --user start empire-a2a-first-party-source-research.service
XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
 systemctl --user show empire-a2a-first-party-source-research.service \
 -p Result -p ExecMainStatus

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 -m scripts.run_a2a_commercial_intelligence_cycle_v2_20261020 --write-local

# Source health / optional tool readiness
cat runtime/a2a_commercial_signal_mining/source_route_resilience_v1.json
cat runtime/a2a_commercial_signal_mining/optional_source_agents_readiness_v1.json

# Disable ONLY first-party daily job if needed
XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
 systemctl --user disable --now empire-a2a-first-party-source-research.timer

Do not remove the two feature worktree dependent user service units, or delete
the feature worktree, while the hourly/daily timers are enabled.
