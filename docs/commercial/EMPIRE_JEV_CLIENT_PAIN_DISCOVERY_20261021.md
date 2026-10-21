# EmpireOS / Jev — Potential-client pain discovery

**Owner: existing Research, Intent Brain, Buyer Scout and commercial CRM teams.**
**Status: developed and tested in feature worktree, not deployed to production.**
No new agent, AI provider, account database, outbound or paid search.

## What was added

- `empire_os/jev_client_pain_discovery.py`: inspect source-backed, public
  posts/observations, identify *concrete* business problem expressions,
  distinguish broad topic mentions, apply the existing Intent Brain and Jev
  adjudication, and map hypotheses into existing Empire product offer families.
- `scripts/review_jev_client_pains_20261021.py`: one-shot audit merging the
  original read-only community history and unresolved **social intent only**
  from the canonical Signal Inbox via `observation_from_signal`.
  Permit/court records, resolved identities and non-social source types are
  not repackaged as customer needs.
- `scripts/run_community_intent_cycle.py`: feature-branch integration into
  the **existing** 15-minute community collector. After observations have
  already been collected, execute Jev adjudication locally with zero extra
  retrieval or model calls. Add only aggregate counters to the ordinary
  `latest.json` and persist a mode 0600, gitignored evidence-reference
  review queue for the existing source-intelligence owner.
- Checks cover duplicate source references, spoofed identity proofs,
  job adverts, seller posts, no-solicitation requests, stale observations,
  cross-domain source mismatch, low-intent topic chatter, and bounded batches.

## Strict commercial interpretation

A first-person problem in public content is a **pain hypothesis**, not an
authenticated company, live budget, buying intent, marketing consent or a
prospect that can be contacted. Generic advice, seller pitches and job adverts
cannot be promoted by Jev. A direct request can at most become
`REVIEW_IDENTITY`; an owner discussing a problem without seeking a provider
can at most become `REVIEW_PAIN_HYPOTHESIS`; opt-outs are never contact leads.
The existing downstream Buyer Scout, original source rights, relationship
registry, tenant CRM and suppression controls remain mandatory.

The historical 32,899-prospect source is not loaded. Its present source
rights, identities, owner affiliations, record freshness and count still
require independently verified, restricted EmpireDB receipts.

## Live observation evidence, 21 October 2026

- Existing community snapshot: 13 observations, 6 lead-gen topics,
  6 automation topics, 3 conversion topics, 3 search visibility topics,
  1 revenue topic. Mentions overlap and are not proven customer issues.
- Combined audit: 13 community records and 35 canonical social-intent records
  examined; repeated URLs collapsed. 1 identity-review observation, other
  observations retained as unverified monitor signals. **No** independently
  verified client problems, qualified buyers or contactable prospects.
- A separate five-source, hand-reviewed public discussion rehearsal produced
  hypotheses for inconsistent lead flow, dental appointment fill-rate, and
  uncertain marketing returns. This is *not* proof of current purchasing demand.
  The hand-reviewed source input remains mode 0600 in gitignored runtime,
  not merged into canonical sources or CRM.

## Source expansion owned by original collectors, not this feature

Prioritise legitimate first-person business statements and explicit public
procurement requests in established UK/US niche sources (roofing, solar,
HVAC, dentistry, law firms, agencies, other service SMBs). Use only
rights-compliant public sources and approved retrieval. Capture original
source, publication date, claimed role, problem expression, buyer request,
objections, and when applicable **author opt-out**; do not infer a first-party
company identity from a username. Source queries to rotate only after
the existing source owner confirms access, group rules, licensing and freshness.

Future enrichment: independently verified company website and contact
history, niche/geography, economic cost of problem, vendor options, available
buyer capacity, then founder-approved offer construction. Later calibration
should use accepted proposals, real conversions, and verified payments rather
than model confidence or volume counters.

## How to reproduce (development, no deployment)

```bash
cd /home/ubuntu/empire_worktrees/jev_commercial_signal_portfolio_20261021
/srv/empire_os/.venv/bin/python -B -m pytest -q tests/test_jev_client_pain_discovery_20261021.py tests/test_community_intent_learning.py
# The reviewed audit was executed with:
# python -B -m scripts.review_jev_client_pains_20261021 --read-only --write-private
```

The immutable aggregate report is at
`docs/commercial/JEV_CLIENT_PAIN_DISCOVERY_AGGREGATE_V2_20261021.json`,
and the locally held private queue is
`runtime/jev_client_pain_discovery/private_latest.json`.
A subsequent new run should use a separately named audit receipt rather than
silently overwriting the existing report.

**Not done:** production merge, scheduling activation, model-prompt inference
of raw private content, independent first-party verification, outreach,
CRM writes, external monetisation or payment handling.
