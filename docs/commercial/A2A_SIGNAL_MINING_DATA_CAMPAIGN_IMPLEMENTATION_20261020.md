# Empire AI A2A — Commercial Signal Mining and Data Campaigns
20 October 2026 | owner `empire.a2a.commercial_signal_miner.v1`

## Founder objective
Apply the useful parts of Greg Isenberg's Meta Muse operating model to our OWN
A2A research stack: mine permissioned B2B and market signals, find buying pains,
qualify data-market fit, produce deeply segmented own-channel campaigns, then
coordinate existing buyer, data-brokerage, commerce and finance owners. Do real
research; do not manufacture buyer identity, demand, licence or revenue.

## Repo / boundaries
- Branch `feature/a2a-commercial-signal-mining-20261020`
- Worktree `/home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020`
- No edits to `/srv/empire_os` or to the owners' existing modules.
- Only this isolated research branch contains new code.
- Existing agents remain owners of Buyer Scout, Community Intent, Data Brokerage,
  Predictive Revenue, Meta Social, Campaigns and Finance OS.

## Actual inputs read in first run
Existing EmpireOS read-only snapshots (no new web or Meta queries):
- `/srv/empire_os/runtime/community_intent/latest.json`
- `/srv/empire_os/runtime/market_sweeps/revenue_gps_latest.json`

Observed during this review (20 October 2026; dynamic snapshots may change):
- Community intent source retrieval: Reddit OK; LinkedIn public recovery DEGRADED.
- Pain-solution briefs: lead_generation 7 mentions/1 high-intent (unverified),
  sales_conversion 2/1, search_visibility 1/1, revenue_growth 1/1,
  automation_ops 3/0.
- Revenue GPS market research: NYC general_contractor priority 80;
  roofing and HVAC Little Rock, AR each priority 5; other enterprise
  research markets priority 2.5. **Research scores are NOT purchase probabilities.**
- Source self-reports specifically do NOT prove buyer intent, campaign eligibility,
  licences, entitlement, payments or money opportunities.

## Implemented
1. `empire_os/a2a_commercial_signal_miner.py`: validates source versions,
   timestamps and observe-only authority; refuses stale and privilege-elevating
   snapshots; deduplicates market candidates; ranks business opportunity research
   only; produces internal campaign briefs.
2. `empire_os/a2a_data_campaign_experiments.py`: laser-specific business-role,
   geography and buyer-use-case segments, exclusions, two creative angles,
   research questions, conversion metrics and rights approval checkpoints.
3. `empire_os/a2a_data_opportunity_workflow.py`: 8 stages per opportunity:
   data rights -> independent buyer qualification -> product deliverability ->
   first-party campaign drafting -> founder release -> commercial terms ->
   Finance OS payment proposal -> canonical finance reconciliation.
   These are *plans*, not live interagent dispatches.
4. `scripts/review_a2a_commercial_signal_mining_20261020.py`: offline job.
   `--write-local` writes reports in this worktree only, mode 0600.
5. `config/a2a_candidates/empire_commercial_signal_miner.agent.json`:
   candidate discovery card with 7 research and commerce planning capabilities.
   It is NOT a cryptographically recognised external A2A registration and does
   not create production agent privileges.

## First execution and outputs
The first read-only run against the existing source snapshots produced:
- 15 prioritised research hypotheses (5 community pain segments + 10 B2B data markets).
- 10 unlaunched broad research campaign briefs.
- 5 specialised data campaign experiment drafts.
- 40 proposed review-gated handoff steps (five markets * eight steps).
- 0 verified new buyers, 0 verified new money opportunities, 0 messages,
  0 live Meta/Instagram queries, 0 ad spend, 0 payment links and 0 payments.

The project has NOT promoted CRM records and has NOT modified commercial
buyer/publisher records.

## Test manually and reproduce
From worktree:
```bash
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_a2a_commercial_signal_miner_20261020.py \
  tests/test_a2a_data_campaign_workflow_20261020.py

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_a2a_commercial_signal_mining_20261020 \
  --write-local
```

Reports under `runtime/a2a_commercial_signal_mining`:
- `latest.json`: source state and ranked research candidates
- `campaign_briefs.json`: broad niches and qualifying questions
- `data_campaign_experiments.json`: 5 specialised target briefs
- `a2a_handoff_plans.json`: buyer, rights, campaign, finance action gates
- `agent_card.json`: internal local discovery card

These files are local to the isolated worktree. They are not served over an API.

## 1st pilot: NYC commercial construction intelligence
- Research market: New York City general-contractor and project-intelligence
  operators, using Revenue GPS research priority only (80/100 review heuristic).
- Buyers to independently validate: commercial estimators, development/business
  development directors, construction intelligence leads, project procurement teams.
- Data product concept: `nyc_permit_project_verification`.
- Proposed angle: source-linked construction project verification that supports
  commercial decisions. Do NOT claim project availability or permit data rights yet.
- Exclusions: consumers, firms outside product territory, unlicensed permit
  data reuse, non-purchasing professional roles.
- Test: verify dataset field rights and source access; independently confirm
  actual business use and willingness to pay; request source-permitted sample;
  founder review of first-party content or approved introductions; log legitimate
  business enquiries. STOP if rights, ability to deliver or buyer evidence fails.

## 2nd and 3rd pilots: Little Rock roofing/HVAC
- Existing market research scores are very low (5/100 research heuristic).
- Prefer evidence gathering over outbound. Only continue if source rights,
  service coverage, consent and independently verified customer demand improve.
- Proposed offers are original aggregate territory/demand-gap assessments,
  not consumer contact lists or automatically generated leads.

## A2A registration and execution gates
The local manifest means other developers can review the proposed agent ID,
role and capability contract in this branch. It is NOT a trusted Ed25519
registration; the existing `a2a_identity` and `a2a_runtime` owners govern
signed identity and nonce protection. The commercial-intent owner must approve
any production handoff. No new public A2A endpoint is deployed.

Before real autonomous tasks:
1. Review source rights and target privacy, particularly Meta platform rules.
2. Get typed event contract acceptance from Buyer Scout, Data Brokerage,
   Campaigns/ASTRA, Finance OS and A2A identity owners. Do not edit their files.
3. Provision approved identities/scopes, authenticated A2A handoffs, replay defense.
4. Authorise a read-only scheduled research tick only after source-owner consent
   and production review.
5. Connect approved Meta professional/Page access for authorised content and
   inbound conversations; no prohibited group scraping or mass unsolicited DMs.
6. Approve actual campaign creative, account, tracking permissions and any spend.
7. For payment links: use an explicitly contracted/licensed payment service or
   the existing governed BSC/USDT rail where appropriate. Never expose real
   bank/card credentials to LLM agents. Finance owner alone issues and verifies.
8. Reconcile canonical settlements and real conversion labels before forecast
   training or claims of realised revenue.

## Non-goals and truths
- This branch does NOT use an unapproved Meta Muse account.
- It does NOT claim 15 qualified buyers or actual payable leads.
- It does NOT activate any bank account, create virtual cards, host a payable
  checkout link or transact cryptocurrency.
- Marketing drafts stay internal and are not posted, emailed or messaged.
- Source screenshots, group membership and scraped social profiles are NOT
  standalone authorisation to extract, market or resell personal data.

## Recommended next build sequence
Priority 1: data source provenance and licence sign-off for the NYC permit product.
Priority 2: existing Buyer Scout owner verifies demand among suitable businesses
and records genuine terms without duplicate outreach.
Priority 3: source-consented first-party campaign pilot using approved landing pages.
Priority 4: authenticated A2A owner handshake; Finance OS owner implements
provider-hosted payment links in sandbox and reconciliation.
Priority 5: evaluate true unit economics before scaling further.
