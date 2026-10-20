# Empire AI — First-Party Company Evidence for Existing Buyer Scout

20 October 2026
Worktree /home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020
Branch feature/a2a-commercial-signal-mining-20261020

## Why this exists

General-purpose Search Fabric live retrieval is provider-degraded:
DuckDuckGo HTML returned 202, Mojeek 403, Bing search results were filtered as
irrelevant; public Overpass server responded 502 overloaded. Those are provider
availability issues, not a prompt problem, and no unapproved paid provider
or anti-bot bypass has been activated.

The existing A2A owner code now has a real first-party research lane:
nine approved public company homepages, seven successful source receipts,
source read-only timer daily and source readback via hourly research timer.

This increment connects that new evidence to the EXISTING canonical Buyer
Scout owner's review contract without creating another independent buyer agent.

## Code shipped

empire_os/a2a_first_party_buyer_scout_handoff_v1.py:
- Consumes source readback, owner-specific prepared Buyer Scout tickets,
  and current mining snapshot (all read-only, validated).
- Binds each observed company WEBSITE to the existing exact industry and
  target market owner ticket.
- Uses the website content body SHA256 captured on the original read.
- Stable record ID based on target owner ticket, public company domain
  and original source digest; repeated hourly runs do not become fresh leads.
- Compares public domain to currently observed mining-domain evidence.
- Distinguishes website self-claims of industry/region from INDEPENDENTLY
  VERIFIED company identity, geographic coverage or actual purchase intent.
- Marks robots-held/oversize/non-200 pages as NOT ready for owner review.
- Never writes to the canonical Buyer Scout/CRM database and never contacts
  website people, pulls personal profiles, purchases leads or changes finance.

scripts/inspect_a2a_first_party_buyer_scout_handoff_20261020.py:
  View scoped source evidence for a responsible Buyer Scout owner:

  cd /home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020
  PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
    -m scripts.inspect_a2a_first_party_buyer_scout_handoff_20261020 \
    --market "tampa, fl" --only-reviewable

  Supported markets: tampa, fl; little rock, ar; nyc.
  No network, no source fetch, no outreach and no CRM writes.

scripts/run_a2a_commercial_intelligence_cycle_v2_20261020.py:
  Adds runtime/a2a_commercial_signal_mining/
  first_party_buyer_scout_handoff_v1.json
  to the existing hourly report set.
  Missing or mismatched source ownership fails closed to a structured hold.

Tests:
  tests/test_a2a_first_party_buyer_scout_handoff_v1_20261020.py
  Covers exact ticket binding, read-only semantics, source denials, falsified
  buyer claims, bad provenance, duplicate domains and stable idempotent IDs.

## Real initial acceptance preview

Source collection (20 Oct):
- Tampa roofing: 3 public company websites, 3 self-described industry/region
  matches with source SHA receipts.
- Little Rock HVAC: 3 sites, 3 matching descriptions with source SHA receipts.
- NYC construction: 3 attempted, 1 matched and safely captured; 1 page
  held due robots policy unavailable, another held because >400k bytes.

The A2A hourly report now prepares nine source observations:
- 7 sources are suitable as OWNER RESEARCH REVIEW INPUTS.
- 2 sources are retained only as source-collection status/holds.
- 0 newly VERIFIED local customers, 0 explicit buying requests,
  0 authenticated owner replies, 0 CRM changes or outbound communications.
  A contractor's company website DOES NOT prove it is purchasing leads.

Each source entry includes:
- first-party website URL, original source SHA, target market/trade
- existing owner ticket ID + ticket digest
- source-read status, company self-description scope match
- existing current mining-window overlap if available
- independent company identity / service territory / buyer-capacity
  verification requirements, canonical dedup and suppression review gate
- PREPARED_NOT_SUBMITTED, contact_authorized=false

## Ownership acceptance / commercial activation gates

1. Canonical Buyer Scout owner separately adopts the above local read-only
   evidence source, examines the first-party origin and recent retrieved
   body if necessary, and verifies independently that it is a real business.
2. Verify county/ZIP service area, legal operating entity, type of contractor,
   the actual decision maker and whether it purchases the leads/data we offer.
3. Respect existing CRM identities, email suppression and contact permissions;
   contact requires separate Sales owner release, not this source report.
4. Only real first-party buying requirements may be written into canonical
   Buyer Scout through its owner-authorised path with signed source receipts.
5. Authorised marketing and Finance owners independently approve campaigns,
   fulfilment and commercial agreements.

A founder-owned Page or Instagram account is NOT a prerequisite for this
public-first-party source/Buyer Scout research stage.

## Broader fresh discovery

This branch has NOT restored general Search Fabric providers or independently
verified a licensed provider key. The first-party daily lane has nine fixed,
approved company websites, not an automated fresh-business discovery index.
The existing Search Fabric owner needs to validate approved official paid/keyed
search or another lawful commercial registry to scale source discovery.

The OpenManus-inspired source planner has three prepared bounded jobs, but
no active OpenManus executor was verified. Its unconfined shell/browser
must not be activated without an agent owner, vetted tools, policy and
verified identity.

## Deployment

Only the isolated A2A worktree is used by the existing enabled user timers:
- empire-a2a-commercial-intelligence-research.timer (hourly)
- empire-a2a-first-party-source-research.timer (daily)

This change does not merge into the production main checkout or change existing
Buyer Scout / Community Intent services. The owner-side ingestion remains
pending explicit contract acceptance.

Source status is a capability improvement, not proof of 7 saleable leads.
