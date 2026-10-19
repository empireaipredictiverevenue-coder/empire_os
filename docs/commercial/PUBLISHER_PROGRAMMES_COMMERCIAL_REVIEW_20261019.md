# Empire AI — public publisher programme evidence, commercial review
**19 October 2026 · first-party website observations; no outreach, acceptance or revenue implied**

## Proven research source — not binding buyer terms

- **BH Network** ([official](https://bh-network.com/)): publicly markets inbound calls/leads across US roofing, solar, HVAC, legal and related services, states nationwide reach, weekly payout and a publisher application path that links to [webuycalls.com](https://webuycalls.com/). These are publisher-facing public **claims**, not a confirmed buy-box, accepted per-call payout, available routing or actual payment capacity. Existing outbound history included prior delivery failure/delay at `team@webuycalls.com`. HOLD re-contact until actual prior recipient/delivery reconciliation and suppression check. Do not repeat a failed send or create a synthetic verified-buyer record.
- **Global Wiz** ([official programme](https://joinglobalwiz.com/affiliates)): publicly describes a reviewed home-services Pay Per Call affiliate offering for owned websites, SEO and content traffic. UK-based affiliates may apply, but campaign demand, US ZIP targeting, transfer criteria, rate and publisher approval are **not** guaranteed or verified for Empire AI. Best research route for the current organic US roofing/solar/HVAC corridor: first request a specific open programme and approved source specification.
- **CentFix** ([official Canadian affiliate programme](https://centfix.ca/affiliates)): publicly describes 8–14% tiers of collected-project revenue, a hold/deduplication policy and coverage in ON, BC, AB and QC. This is not a per-lead or per-call accepted payout, nor does it establish Empire AI can participate. HOLD outside current UK/US territories.

## Source-linked owner implementation

The `docs/commercial/BUYER_PUBLISHER_PROGRAM_EVIDENCE_20261019.json` source file holds the three independently attributable first-party programme observations. The strict reader, `empire_os/buyer_publisher_program_evidence.py`, validates:
- Exact domain and programme classification, including Canadian territorial exclusion.
- First-party HTTPS source and restricted delegated application URL.
- Buyer/capacity/terms/application/contact fields all **false**.
- 30-day expiry to force refreshed programme evidence.
- No buyer identity, CRM record, contact data, auto-send or financial authority.

The existing `empire_os/buyer_recovery_scout_consumer.py` adds exact-domain programme notes to the current Scout research **when present**. It also retains a separate `publisher_programme_research` section containing all three source-reviewed programmes if the rotating Scout snapshot no longer contains them. This is part of the **existing** Buyer Recovery Desk packet, not a new source poller, agent, prospect database or timer.

Production runtime receipt:
- Original Recovery Desk: 25 unchanged packet slots.
- Rotating Scout snapshot: 3 research tasks at verification.
- Persistent public programme research: 3 source-reviewed programme entries, **0** approved buyers.
- Output stays private mode 0600; `commercial_authority=NONE`; no DB writes, funds or outbound.
- The catalogue is a point-in-time observation. Public website assertions can change or be inaccurate; do not advertise these as independently verified buying capacity.

## Outreach and commercial conversion strategy

**Priority 1 — Global Wiz publisher programme review** (once prior-contact/suppression checks clear):
Ask whether there is a currently open **US roofing / solar / HVAC** pay-per-call campaign. Describe the **owned SEO / organic US-facing properties honestly**, only traffic actually verified; never claim an active campaign, paid ads, buyer route, calls or expected volume without source evidence. Ask for their written publisher acceptance, permitted traffic sources, qualified event (including call duration / buyer-leg connection), ZIP/territory coverage, live caps, payout/unit/currency, disqualifications, recording consent, routing, tracking source sub-IDs, disputes and settlement.

**Priority 2 — BH Network** only after resolving historical `webuycalls.com` delivery failure and identifying a valid supported company application route. Their site advertises weekly payouts but that is not a mutually accepted payout, nor a reliable proof of a payable call.

**Priority 3 — CentFix** defer until a separately approved Canadian corridor exists. Its public revenue-share economics are not US/UK pay-per-call economics.

**Operating rule:** each source-verified company remains `RESEARCH_ONLY` until actual human reply and first-party confirmation of campaigns/terms; then process through existing Buyer Network due diligence, suppression, founder approval and canonical send/receipt pathways. No standalone LinkedIn, Reddit or email automation added.

## Reproduction and rollback

Production verification command:
```bash
cd /srv/empire_os
PYTHONPATH=$PWD ./.venv/bin/python -B scripts/build_buyer_recovery_action_desk.py --write --repo-root /srv/empire_os
```
Read private output at `runtime/buyer_network_intelligence/buyer_recovery_action_desk_latest.json`, under `scout_network_research_review.publisher_programme_research`.

The two source-pinned releases were installed with:
- `scripts/deploy_buyer_publisher_program_evidence_20261019.py`
- `scripts/deploy_publisher_programme_rotation_20261019.py`

Reversal (reverse order, hash-verified) must occur before another agent owns these source files. No timers need disabling because none were installed.
