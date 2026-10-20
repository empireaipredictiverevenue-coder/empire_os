# Empire AI — Meta Muse-style market test protocol (v1)

**20 October 2026 | Owner:** Meta Market Validation Agent
**State:** ISOLATED RESEARCH | NO LIVE SOCIAL COLLECTOR | NO PRODUCTION DEPLOYMENT | NO AD SPEND

## What we are replicating — and what we are not
Greg Isenberg's four levels (signals -> clean/trusted list -> own the room -> vertical software) and demonstration of one niche + one city + clear admission/quality rules. We reproduce the business *validation method*, not Meta's Muse runtime, private social collection or automatic cold contacting.

Source research: `https://youtu.be/tpZOU1ugODQ`. Published outline: `https://startup.whatfinger.com/2026/10/19/meta-muse-will-create-1000-millionaires/`. Actual EmpireOS first-party YouTube adapter returned public title/creator; transcript and full video frames were **not** ingested by the first-party adapter. External published outline and third-party transcript reviewed separately.

## Single-owner scope
- Meta Market Validation Agent: this worktree only; evidence-first experiment plans, narrow opportunity hypotheses, research tasks, report.
- Community Intent owner: existing `community_intent.py` for Reddit/LinkedIn. No edits here.
- Buyer Scout / Commercial: sole authority on real purchasing entities, terms, geos, appointment acceptance.
- Data Brokerage: sole authority on dataset licence and sale; social source rights must be proven separately.
- Predictive Revenue: sole authority on forecast calibration. **Never train on hypothetical transaction outcomes.**
- ASTRA / SEO / Social: approve landing page, creative, first-party analytics and live traffic before any publish.

## Candidate lanes, hypotheses ONLY
1. US HVAC — Phoenix, Arizona, ZIP 85001: source and qualification viability; ZIP not claimed to be covered by a buyer.
2. US Roofing — Tampa, Florida, ZIP 33602: same. ZIP provisional until a payer independently verifies it.
The market is chosen only after evidence from the actual intended niche, city, and approved ZIP.

## Reproducible 14-day lean validation sequence
**Day 0: guardrails and niche selection.** Verify permitted source types, source licensing, privacy treatment, regulated contractor requirements, geographic eligibility; identify three buyer pain points and three seller pains. A random Facebook post is neither consent nor a sale.

**Days 1–2: mine allowed signals.** Agent organises manually reviewed observations, consented partner feeds or approved API research. Each source retains platform, URL, access method, observation time, permitted-use evidence and independent source ID. Seek two separate aggregate demand sources per test market. Exclude personal names, contacts, raw group posts, private communities and scraped profiles. No unsupported Facebook Groups API.

**Days 3–4: clean and match.** Deduplicate the evidence, reject stale URLs and cross-geo mismatches, map product/service type, local requirements, time window and trust criteria. Flag unsatisfied demand vs plausible providers. Agent cannot convert a business's existence to its willingness.

**Days 5–6: verify supply and payer.** Independently confirm at least three businesses wish to participate, local capacity, appointment acceptance policy, legal/compliance conditions, exact ZIPs, payout amount and payment timing. Obtain signed/recorded authoritative contracts separately. Any provider or payer claim without verification is HOLD.

**Days 7–8: prepare owned capture.** Draft landing page/FB Page/Instagram business content with clear identity, offering, consent notices, compliant privacy language and first-party campaign tagging. No existing production site mutation, posting, or campaign run without founder's separate release approval. This stage is conceptually "own the room," not copying other groups' users.

**Days 9–12: live opt-in pilot ONLY if approved.** Start with zero-paid-spend owned organic content, review any true inbound requests using documented qualification criteria, and match to separately opted-in/contracted providers. No unsolicited DMs or call automation. Track impression/session -> opted-in enquiry -> qualified request -> accepted appointment -> completed service -> settled payment. Zero results may be correct.

**Days 13–14: evaluate.** Compare channel and niche on independently evidenced quality, opt-in rate, response time, rejection reasons, disputes, collected revenue, service fulfilment and time cost. Decide stop, improve, test another market or request permission to scale. No automatic budget increase.

## Intended validation thresholds — NOT CURRENT RESULTS
| Stage | Test | Pre-set target | Automatic decision |
|---|---|---|---|
| Source quality | Distinct permitted aggregated demand sources | >=2 | fewer => HOLD |
| Supply readiness | Verified willing providers with actual service capacity | >=3 | fewer => HOLD |
| Buyer capacity | One identified payer with signed coverage, accepted appointment definition and commercial rates | >=1 | missing => HOLD |
| Opt-in demand | Genuine compliant first-party consumer enquiries | >=10 | zero => no commercial success |
| Delivered value | Appointments genuinely accepted by a payer | >=3 | no claim without canonical records |
| Payment proof | Independently reconciled settled transactions | >=1 | no proven revenue without payout records |
| Economic feasibility | Contribution margin positive after traffic, labour, refund and fulfilment costs | >0 after verified inputs | else pivot or stop |

These are early validation thresholds for founder review, not proof of product-market fit or expected conversion. A test can fail usefully if evidence is poor or providers have no capacity.

## Source / privacy constraints
Meta retired the Facebook Groups API in April 2024. Research in groups must stay permissioned/manual, not automated extraction or private member harvesting. Instagram business insights and selected business discovery require app-specific permissions and professional accounts; do not bypass API scopes. Meta Marketplace is not a general unrestricted scraping feed.

Treat UK GDPR / EU GDPR when applicable, US state consumer privacy and telemarketing restrictions, and sector rules as separate counsel review gates. No personal data monetisation from social posts and no resale without licence.

## Tech contracts
**Input:** bounded packet in `empire.meta_social_opportunity_review.v1` schema from an authorised, inspected source; may include `synthetic=true` for tests, in which case no market evidence is counted.

**Agent:** `empire_os/agents/meta_market_validation_agent.py`. Responsible for L1 source review, candidate selection, research tasks and blockers. It issues 6 internal research/release-gated tasks per lane.

**CLI:** `PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.run_meta_market_validation_agent`.
Optional `--observations-file /path/to/a/pre_reviewed_packet.json`; optional `--report-only`. Results written inside the isolated branch's `runtime/meta_market_research_agent/` only; there are NO bus, DB, CRM, marketing or payment integrations.

**Output:** `latest.json`, `research_tasks.json`, with explicit `mode: OBSERVE` and every high-risk capability false. Source evidence in the report describes only supplied packets, never live collection. No API keys printed or used.

## Approval before moving beyond this build
- Approved Meta professional business/page connection, account rights and documented API permissions.
- Buyer Scout confirms payer qualification, ZIP coverage, appointment definitions and written terms.
- Privacy/source-rights/legal sign-off; direct opt-in capture flow.
- Founder approves exact public pages, organic campaign scope, tracking consent, outbound and any spend.
- Revenue/predictive owners accept authenticated canonical transaction events before outcome calibration.

## Distinct outcome of this branch
Build agent + source validator + confidence-limited opportunity matching + safe experiment backlog, smoke tests and evidence-gated readiness. **Do not claim live leads, appointments or payments from this prototype.**
