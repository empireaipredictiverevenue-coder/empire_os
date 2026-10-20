# Empire AI — Live source stack: Scrapling, Agent Reach, Browser Use and OpenHands
Date: 20 October 2026
Owner: A2A Commercial Signal Miner isolated source-research branch
Worktree: /home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020

## Founder objective

Real-time practical company / buying-signal research from a plain-English
commercial target. Scale source discovery using the appropriate existing
agent, rather than repeated scraping workers or fictitious buyer counts.

## Implemented and verified

The fixed approved first-party collector runs online daily on EmpireOS.
It is not a general live search engine. It makes a maximum of 9 approved
company homepage requests after checking robots.txt and public DNS, never
follows redirects and never reads login/private groups.

A separate isolated, non-root Python environment was created:
  /home/ubuntu/.local/share/empire_a2a_scrapling_parser_venv
Package installed and parser checked:
  scrapling==0.4.15
  pytest==9.1.1 (test-only, installed in same isolated environment)

The canonical main production venv (/srv/empire_os/.venv) was NOT changed.
No Scrapling anti-bot/stealth browser, shell, login or crawling fetcher is used.

- empire_os/a2a_scrapling_offline_extraction_v1.py imports ONLY
  scrapling.parser.Selector, after the existing, robots-approved web fetch.
- It produces source-bound SHA256, bounded metadata/heading/structured data
  presence indicators, with NO raw page text, emails or private contacts.
- empire_os/a2a_first_party_site_recovery_v1.py passes fetched bytes to
  the bounded offline parser, holds failure and detects mismatched SHA.
- scripts/run_a2a_first_party_source_recovery_20261020.py enables the parser.
- The daily systemd source service now points explicitly to the separate
  Scrapling venv, with unchanged source allowlist and run limits.
- empire_os/a2a_first_party_recovery_readback_v1.py enforces source digest,
  evidence state and no-buyer promotion on hourly readback.
- empire_os/a2a_first_party_buyer_scout_handoff_v1.py carries the
  source parser indication into the existing Buyer's Scout review-only packets.

A real 9-site test from EmpireOS previously fetched 7 public company
homepages, including 3 Tampa roofing, 3 Little Rock/Arkansas HVAC and
1 NYC construction site. Scrapling successfully parsed 7 of 7.
One NYC site had an uncertain robots result; another exceeded 400k page cap.
These were held. No bypasses or retries were used.

## Agent Reach

Existing install:
  /opt/empire/agent-reach
Existing source sensor:
  /srv/empire_os/empire_os/agent_reach_sensor.py

Installed and ready in doctor's status output, but its per-channel
health is NOT an actual source retrieval or legal source permission.
A presence-only, no-credential snapshot is recorded via:
  PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
    -m scripts.observe_agent_reach_a2a_public_channels_20261020

Observed doctor states on 20 Oct:
  rss: ok
  web: ok (Jina Reader)
  youtube: warn
  github: warn
  facebook: off
  instagram: off
  reddit: off
  linkedin: off

The existing Community Intent owner already collects approved public RSS.
Do not launch duplicate Reddit crawlers, reuse browser login cookies, or
treat Agent Reach doctor as proof of collected niche/city buyer evidence.
Social account-backed access requires owner permission and native APIs.

## Source degradation routing

The existing Search Fabric has keyless provider failures (HTTP 202 from
DuckDuckGo, 403 from Mojeek, Bing quality rejects). Current public buyer
seed status: NO_FRESH_DOMAIN_RESULTS_PROVIDER_HEALTH_UNVERIFIED.

New:
  empire_os/a2a_source_route_resilience_v1.py
  runtime/a2a_commercial_signal_mining/source_route_resilience_v1.json

The hourly A2A miner emits market-by-market source coverage, observed
Scrapling extraction counts, online first-party fallback availability,
Agent Reach channel doctor status, and degraded general search state.
Provider statuses MUST not be converted into live results or buying intent.

No novel engine or browser automation may evade anti-bot restrictions,
CAPTCHAs, technical login protection or site terms. For scalable
discovery the existing Search Fabric owner should configure a permitted
official/licensed provider and a source provenance ledger. A fresh query
must produce original URLs, issue times and reproducible source receipts.

## Open source stack recommendations

1. Scrapling: approved already-retrieved HTML -> structured source evidence.
   Active, isolated and online collector hooked up.
2. Agent Reach: public RSS and permitted web-reading channels, only where
   the owning source department authorises individual sources and dedupes
   them against existing Community Intent cycles.
3. Browser Use (browser-use/browser-use): optional *sandboxed* interactive
   browser for owner-approved websites which legitimately need JavaScript
   or workflows. NOT installed/activated on EmpireOS. No login/cookie
   stealing, stealth or bypass, no social platform bulk messages.
4. OpenHands (OpenHands/software-agent-sdk): isolated development agent for
   code repair, tests, provider adapter maintenance, and PRs—not scraping
   or direct production deployments. EmpireOS has an OpenHands workspace
   request contract, but no verified active standalone OpenHands executor.
5. Crawl4AI (unclecode/crawl4ai): possible future self-hosted, authentication-
   protected LLM-ready document crawler for PERMITTED high-volume page
   extraction, if CSS-level Scrapling fails the need. It overlaps Scrapling,
   so do not install a duplicate crawler without a measured gap.
6. SearXNG: optional federated discovery index for own search strategy,
   NOT a guaranteed solution to blocked public engines; must respect
   rate limits/source terms, and use provider health validation.

## Real release state

A2A research branch and the daily/hourly user services are running from
the isolated worktree, not merged into /srv/empire_os. No changes made to
the live Buyer Scout/Community Intent source executors or canonical CRM.
The new source evidence is available for owner review; it is not 7 buyers
or 7 paid leads.

Next owner acceptance:
- Buyer Scout ingests signed A2A source packets for real company identity,
  city/territory, consent, buying need, budget and duplicate checks.
- Search Fabric owner restores a source-backed fresh provider query;
  official API or licensed data source rather than keyless anti-bot bypass.
- Browser Use and OpenHands, if needed, each require an isolated
  non-production workspace, restricted tools, audit records and owner release.

## Verify

cd /home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.run_a2a_commercial_intelligence_cycle_v2_20261020 --write-local

# Check the last isolated daily service's success
XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
 systemctl --user show empire-a2a-first-party-source-research.service \
 -p Result -p ExecMainStatus

# Stop only the new daily service when necessary
XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
 systemctl --user disable --now empire-a2a-first-party-source-research.timer

The hourly A2A miner uses the original /srv/empire_os/.venv and strictly
read-only cached source reports, without social login or direct web calls.
