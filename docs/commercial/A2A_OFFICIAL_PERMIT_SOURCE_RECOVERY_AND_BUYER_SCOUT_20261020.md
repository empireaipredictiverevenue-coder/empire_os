# Empire A2A — Official US permit source discovery and Buyer Scout integration

Date: 20 October 2026
Branch: feature/a2a-commercial-signal-mining-20261020
Production authority: OBSERVE / NONE

## Finding / source restoration

The live general search route is still DEGRADED: DuckDuckGo 202, Mojeek 403,
Bing relevance rejects. No paid search provider configured or activated.

An independently located official government source DOES respond from EmpireOS:
  https://maps.littlerock.gov/server/rest/services/Permits/MapServer/0

City of Little Rock, AR Open Permits (ArcGIS). A small bounded query for
mechanical permits, with original permit object IDs and public contractor
business names, succeeds with HTTP200 JSON.

Official geographic source discovery is NOT a verified buyer or homeowner
lead, and a mechanical permit does not necessarily mean an HVAC replacement.
No customer-facing redistribution/license rights have been verified.

Tampa official City of Tampa ArcGIS:
  https://arcgis.tampagov.net/arcgis/rest/services/Planning/PermitsAll/FeatureServer/0

Returned HTTP307 to a specific City of Tampa page for connections outside
the United States. This block must NOT be bypassed with proxy/browser.
The Hillsborough County permit server independently timed out twice.
Those source routes are HELD, not evidence of no demand.

## Actual implementation

- empire_os/a2a_official_mechanical_permit_research_v1.py
  - fixed public official Little Rock REST endpoint
  - one HTTPS JSON GET; no redirects/retries, bound 40 records, cap 300k bytes,
    45-day lookback (allowed 7-60 days), 3+13s request timeout
  - no property address, coordinates, owner contact, individuals, emails,
    phone numbers or project description fetched or exported
  - conservative business-name classification; dedup company names across
    permit events and keep public permit object IDs + source SHA receipt
  - source / response timestamps and date-of-latest-issue recorded
  - stale source permits separately reported from successful API retrieval
  - source is an unsigned government API response, not an A2A signed owner
    commercial approval, licence verification, or current buyer proof
- scripts/run_a2a_official_permit_research_20261020.py
  - explicit read-only original source access; atomic 0600 local report
- ops/systemd/user/empire-a2a-official-permit-research.service/.timer
  - isolated user-level once-daily public data refresh
  - at 06:45 UTC +/- 10 minute random delay; no paid credentials,
    no other production service modified
- empire_os/a2a_official_permit_owner_review_v1.py
  - stable, deduplicated company research evidence bound to the
    EXISTING Little Rock HVAC Buyer Scout research ticket
  - requires separate legal company, local scope, commercial buying intent
    and canonical CRM duplicate/suppression validation
  - zero task dispatch, outbound messages, CRM creation or buyer promotion
- scripts/run_a2a_commercial_intelligence_cycle_v2_20261020.py
  - existing hourly research worker now reads the official permit
    evidence and writes local:
    runtime/a2a_commercial_signal_mining/
        official_permit_buyer_scout_review_v1.json
- empire_os/a2a_source_route_resilience_v1.py
  - maps official permit source states into source-route status beside
    existing first-party websites and degraded general-purpose search
  - a stale permit does NOT become a current buyer demand signal.

## Verified live outcome 20 October 2026

One HTTP200 official source read examined 40 open-mechanical permit records,
the upstream response confirmed there are more results (truncated).
From these 40 record events:
- 7 distinct conservatively identified public contractor business names
  prepared for Buyer Scout evidence review
- newest permit issue date: 25 September 2026
- source considered stale for current (last 14 days) project-demand claims
- real verified lead buyers: 0
- real verified homeowner leads: 0
- outreach approved: false
- company service territory and buyer capacity independently verified: false
- actual job materials, supplier quotes or payment settlements: none

This is REAL official-source collection. It does NOT fix nationwide general
search or prove the seven companies are purchasing leads.

## Next owner steps

1. Buyer Scout existing owner: read the local review report, independently
   corroborate business identity/licensing/site/actual service territory,
   existing CRM relationships, buyer lead-purchase interest, authority and
   budget. Do not contact without Sales owner release.
2. Search Fabric owner: add one officially licensed and accessible general
   company-discovery search API and account-held provider health evidence.
3. Data Brokerage owner: verify permit data usage/redistribution rights before
   any customer-facing sale. Observed public records remain internal research.
4. Predictive Intelligence owner: consume observed vs stale source readiness,
   not permit count as demand/conversion probability.
5. Deployment owner: reviewed mainline integration. Current user systemd jobs
   run from a clean isolated feature worktree, NOT a merged main release.

## Operator commands

cd /home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.run_a2a_official_permit_research_20261020 \
  --read-only-public-api \
  --approval FOUNDER_APPROVED_OFFICIAL_PUBLIC_PERMIT_RESEARCH_READONLY_20261020

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.run_a2a_commercial_intelligence_cycle_v2_20261020 --write-local

XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
  systemctl --user show empire-a2a-official-permit-research.service \
  -p Result -p ExecMainStatus

Rollback only the new once-daily official-source refresh:
XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
  systemctl --user disable --now empire-a2a-official-permit-research.timer

Do not delete the feature worktree while its timers are running.
