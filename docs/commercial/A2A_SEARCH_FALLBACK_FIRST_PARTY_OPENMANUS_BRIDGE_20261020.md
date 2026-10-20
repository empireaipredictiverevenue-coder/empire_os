# Empire AI — Fresh B2B research recovery, first-party lane and OpenManus handoff

Date: 20 October 2026
Branch: feature/a2a-commercial-signal-mining-20261020
Owner: existing Empire A2A commercial signal miner

## Incident reproduced, not guessed

Live EmpireOS Search Fabric diagnostic for the search:
  roofing contractors Tampa Florida

Returned ZERO usable organic domains, search_state PROVIDER_DEGRADED.
DuckDuckGo HTML / DuckDuckGo Lite responded HTTP 202. Mojeek was HTTP 403.
Bing HTML/RSS results were rejected by existing lexical quality controls.
Public Overpass API returned HTTP 502 overloaded; it is not a reliable
high-frequency commercial data provider.

There is an OpenManus source snapshot at:
  /var/tmp/empire_odysseus_intake_20261010/openmanus

It is FoundationAgents/OpenManus source previously inspected at commit
3309bf4 (MIT). There was NO independently verified live production OpenManus
browser worker, process, dedicated daemon, service, trusted identity,
authenticated API endpoint or account credentials. Reviewed source is not a
deployed executor. This build does not install its unrestricted shell/browser.

## Deployed real first-party source fallback

Nine specific, publicly accessible company homepages discovered from a
one-time research pass are declared in:
  config/a2a_candidates/approved_first_party_business_sites_v1.json

- 3 public Tampa roofing websites
- 3 public Little Rock / Central Arkansas HVAC websites
- 3 public NYC construction company websites

External company website read code:
  empire_os/a2a_first_party_site_recovery_v1.py

- only exact approved HTTPS root homepages, not arbitrary URL inputs
- public DNS preflight, no redirects, no login or credentials
- robots.txt permission checked BEFORE each homepage read
- one robots check and one homepage request at most per site, no retries
- only 9 sites max, max 400,000 response bytes per homepage, 100,000 per robots
- short timeouts, no private group scraping, bypass or anti-bot workarounds
- body SHA-256 plus true/false classification for INDUSTRY and REGION
- no raw page text, people, emails, phones, personal profiles or buyer
  contact information stored, and no actual buying needs assumed
- website self-description is NOT independently verified buyer identity

Operator one-shot CLI:
  PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
    -m scripts.run_a2a_first_party_source_recovery_20261020 \
    --live-readonly \
    --approval FOUNDER_APPROVED_PUBLIC_BUSINESS_SOURCE_READ_20261020 \
    --max-sites 9

Installed user-level systemd source files:
  ops/systemd/user/empire-a2a-first-party-source-research.service
  ops/systemd/user/empire-a2a-first-party-source-research.timer

Enabled daily read-only source refresh, at approximately 06:30 UTC plus up
to 10 min randomisation. Service tested via systemd: Result=success,
ExecMainStatus=0. No production main code merge or restart.

The pre-existing hourly A2A intelligence worker consumes ONLY its cached
locally persisted JSON via strict validation and does no external crawling.
The daily lane is fixed first-party websites, NOT a competing broad source
collector, Facebook agent, Buyer Scout worker, or search engine scraper.

Local outputs:
 runtime/a2a_commercial_signal_mining/first_party_source_recovery_v1.json
 runtime/a2a_commercial_signal_mining/first_party_source_readback_v1.json
 runtime/a2a_commercial_signal_mining/openmanus_research_jobs_v1.json

## Actual read-only retrieval outcome

From real first-party reads on 20 October:
- Tampa: 3/3 success HTTP 200, robots allowed, SHA source receipts.
- Little Rock / Central AR: 3/3 success, robots allowed, SHA receipts.
- NYC: 1/3 success; one robots policy unknown -> held; one 400k page cap -> held.
- Overall: 7/9 sites with HTTP 200 and captured SHA.
- Industry and region terms in the sites' OWN publicly presented text: 7.
- Independently verified actual lead buyers, their budget, interest in buying
  leads, and confirmed service territory: ZERO.

No websites were contacted, no ads launched, no messages sent, no finance
transactions performed. All site reads were read-only.

## OpenManus-compatible ownership route

Code:
  empire_os/a2a_openmanus_scoped_research_bridge_v1.py

The isolated research worker now outputs 3 owner-specific, bounded OpenManus
job packets. These include exact target sector, city, known owner-ticket IDs,
suggested queries and actual public first-party URL+body SHA references.

Permitted job phases:
  PLAN -> APPROVED DISCOVERY -> FIRST PARTY REVIEW ->
  CANONICAL COMPANY / GEO CROSSCHECK -> SIGNED OWNER RECEIPT

Tool classes allow only first-party public site reads, approved official
registry lookups and permitted public RSS through the existing source owner.
Max 3 newly approved public pages and max 5 public domains per job.
No unrestricted shell, credential use, private group or login scraping,
unsolicited messaging, CRM writes, purchases, or model-invented leads.

OpenManus jobs PREPARED: 3. Actually dispatched/executed: ZERO.
Production OpenManus executor remains unverified.
Owner must connect actual authenticated executor API and approve tools.
Neither the agent plan nor a web source snippet becomes verified demand.

## Next real deployment gates

1. Existing Search Fabric owner restore official/licensed fresh search API
   or correct keyless provider problems. Browser automation does NOT solve
   source-provider anti-bot/quality failures.
2. Existing Community Intent and Buyer Scout owners accept the scoped A2A
   source jobs and verify original evidence, canonical company identity,
   service territory, actual buying intent, budget, duplicate/CRM status.
3. A2A identity owner connects OpenManus with signed executor identity,
   sandbox, tool controls, durable replay protection, and owner receipts.
4. Campaign and Finance owners separately approve outward contact, legal
   data distribution, spend, payments, and financial learning.

## Verify or rollback

Inspect systemd:
 XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
 systemctl --user list-timers --all | grep empire-a2a

Logs:
 journalctl --user -u empire-a2a-first-party-source-research.service -n 20

Disable only the new daily first-party source refresh:
 XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
 systemctl --user disable --now empire-a2a-first-party-source-research.timer

Both active user timers reference the isolated worktree: do not delete it or
mistake their success for a production branch merge. Deploying an entirely
maintained production release is still a separate owner-reviewed stage.
