# Empire AI — Founder-prompted B2B lead and buyer intelligence

20 October 2026 | Owner: empire.a2a.commercial_signal_miner.v1
Branch: feature/a2a-commercial-signal-mining-20261020

## What the founder requested

Target actual B2B lead buyers, data purchasers and commercial problem holders
with tight niche + geography + buyer-role + product-specific searches. Follow
Greg Isenberg's principle: use an agent to find and organise genuine, source-
supported opportunities before investing in channel scale or vertical software.
Do NOT equate a user profile or general forum post with a saleable prospect.

## Implemented

- empire_os/a2a_prompt_targeted_buyer_research_v1.py
  - deterministic, restricted prompt compiler with an explicit B2B niche and city
  - resolves roofing, HVAC, solar, legal, plumbing, construction, B2B, agencies
  - infers desired business product as calls/appointments, data intelligence or
    revenue software, and preserves buyer-role hypotheses and exclusions
  - ambiguous multi-niche or unknown city requests are held for clarification
  - matches the *existing* Community Intent owner's permitted source atlas
  - only allows existing public Reddit RSS research sources in automatic research
    options; does not enable private Facebook Groups, LinkedIn scraping or DMs
  - reads the owner's existing public post observations transiently, classifies
    request-versus-pitch using empire_os.icp_intent_relevance, and only stores
    a public post URL and a *not-verified* classification for an owner to inspect
  - never saves usernames, post text, inferred personal identifiers or a
    fabricated buyer/appointment/payment
  - a Reddit platform success result is not represented as a successful retrieval
    for a specific subreddit on the last cycle; the distinction is explicit

- empire_os/a2a_founder_targeting_cycle_v1.py
  - generates ASTRA-compatible textual research instructions, focus fields,
    qualification requirements, exclusions and output contract per profile
  - ASTRA prompts are *prepared but not dispatched or run through an LLM*;
    this lets an existing agent owner integrate them later after permissions

- config/a2a_candidates/founder_targeting_prompts_v1.json
  - contains three founder-directed research profiles, not individual leads
  - roofing lead/call/appointment buyers in Tampa, FL
  - HVAC appointment/lead buyers in Little Rock, AR
  - construction permit/project intelligence purchasers in New York City

- scripts/prompt_a2a_buyer_research_20261020.py
  - command-line entry for a specific natural-language founder target request
  - --write-preview saves a restricted read-only report
  - --save-hourly explicitly adds a validated prompt to the recurring local
    research targets (up to ten profiles), with duplicate suppression
  - neither operation sends a single message, creates ads or updates CRM

- scripts/run_a2a_commercial_intelligence_cycle_v2_20261020.py
  - hourly A2A research service now reads the targeting config and builds
    founder_prompted_targeting_v1.json alongside its existing source reports
  - does not start a second Reddit collector or cross agent ownership boundaries

## Initial run against actual owner snapshots

At the inspected time:
- Tampa roofing: 3 relevant *pre-existing public Reddit research venues*,
  zero niche-matched public posts in the latest top-observation sample, zero
  verified buyers, zero geographically verified purchase demand
- Little Rock HVAC: 1 relevant pre-existing Reddit research venue; zero
  niche-matched latest public post signals or verified local buyers
- NYC construction data: no niche-matched public Reddit research venues;
  required next action: owner's permitted construction-specific sources /
  original local project/permit product rights review
- Global pain-solution briefs sometimes include Reddit discussion references,
  but those are NOT city- or vertical-specific buying evidence.
- Existing latest social observations are predominantly broad B2B community
  discussions. LinkedIn's public source feed may be degraded; this new worker
  doesn't bypass source protections or collect restricted profiles.

## Example interactive target prompt

From the isolated worktree:

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.prompt_a2a_buyer_research_20261020 \
  --prompt "Find roofing companies and lead buyers for exclusive inbound calls in Tampa, Florida; exclude agencies and unverified resellers" \
  --label "Tampa roofing lead buyers" \
  --write-preview

To persist that approved target for the existing hourly research cycle, also
pass --save-hourly. Only local research configuration changes. It requires
a single clear vertical, city, buyer/product type and B2B commercial audience;
the parser will not guess ambiguous targets. Existing identical targets are
deduplicated.

## AI prompting design and limits

The current user-language parser is deterministic, not an actual call to GPT-6
or an autonomous model provider. It generates a research instruction packet
for ASTRA / approved reasoning agents, including requested scope, actual
source evidence, counterparty business verification, buyer capacity, locality,
consent, and required canonical dedupe. This avoids hidden inference and spend.

The next owner integration may use an LLM to *suggest a candidate target*, but
its structured result must be validated against the same schema, permissions,
source and dataset limits. No prompt injection from an untrusted social post
should change the agent's system authority or message people.

## Commercial activation sequence

1. Existing Community Intent source owner reviews the suggested public
   source-research assignment and expands licensed, permitted sources only
   with approval. Public site terms and collection policy still apply.
2. Existing Buyer Scout owner verifies real company identity, geography,
   current buying use case, decision authority and duplicate suppression
   in canonical customer records. An author name is NOT independently verified
   company identity.
3. Data Brokerage owner validates fulfilment, data use and field licensing.
4. Owned Campaigns owner drafts source-supported original messaging, opt-in
   landing pages and compliant channels for the exact buyer cohort.
5. Founder approves external publication, audience and spend scope.
6. Finance OS owner reconciles actual paid transactions before teaching
   Predictive Revenue that any of the research was profitable.

## Exclusions

- No Meta or Instagram account connected in the user-owned EmpireOS server.
- No actual autonomous messages, bot-to-human calls, cold outreach,
  supplier matching or real payments.
- No invented buyer counts, appointments, payouts or source permissions.
- No paid ad custom audiences based on unconsented scraped identities.
- Source-source freshness does not prove geographic buying intent.

## Status

The worker is active via the dedicated hourly user-level systemd timer already
installed, and the targeting output is now part of its local cycle. No main
production checkout merge or gateway restart happened in this implementation.
