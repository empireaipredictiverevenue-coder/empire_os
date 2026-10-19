# Empire AI — Buyer Scout Commercial Memory & No-Duplicate Research
**19 October 2026 — Lead Revenue Fabric / resilient fallback owner**

## Why this matters for revenue

The main Scout discovers firms and classifies first-party signals, but
repeat domain research, warm mail threads and publisher-versus-payer
ambiguity can waste the limited evidence budget and risk duplicate
introductions. Better buying intelligence means **demand proof, own spend,
buybox, terms and paid capacity**, not simply a nice website or a
marketing agency's "we buy traffic" claim.

The improvement is an additive research/probe companion within the
*existing owned fallback*, not a rewrite of the canonical Buyer Scout
or the CRM agent's buyer records.

## Current read-only production evidence (19 October, local source timestamps)

- `runtime/buyer_network_intelligence/founder_qualification_actions_latest.json`:
  **25** founder-reviewed B2B targets; output is OBSERVE and
  `outbound_enabled=false`.
- `runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json`:
  **259** relationship rows; Gmail snapshot `gmail_snapshot_fresh=false`.
- `runtime/buyer_acquisition/scout_latest.json`: **3** candidate
  rows, all classified **RESEARCH_EVIDENCE_ONLY** at inspection, with
  buyer budget, terms and canonical identity unverified.
- Across the 25 shortlisted domains, **10** overlap an existing contact/
  suppression relationship; **3** had positive first-party probe
  evidence in the latest Scout snapshot; **11** are in the union of
  those groups (the groups overlap). Business-aware preflight selected
  **8** of the remaining eligible reviewed companies as the next
  bounded research batch (no probes or sends from the preflight).
- Private Commercial Awareness review: 2 of the 3 current Scout firms
  matched positive existing-contact/thread history; 1 lacked direct
  buyer evidence. The buyer role is not proven by publisher recruitment
  or an economic-capacity proxy.

## Implemented

- `empire_os/buyer_scout_commercial_awareness.py`:
  standalone read-only triage against Scout + founder qualification +
  relationship registry; rejects missing/stale/malformed contracts and
  source send authority; exact domains and proven registry identity
  aliases only, never name-only or subsidiary merges.
- `scripts/review_buyer_scout_commercial_awareness_20261019.py --read-only`:
  scoped live snapshot report; no names, people, emails, message bodies,
  CRM identifiers, network requests, DB writes or outbound.
- `empire_os/buyer_scout_probe_cooldown.py`: 24-hour positive
  first-party evidence cooldown with bounded UTC history, corruption
  hold, atomic 0600 metadata cache, automatic expiry, no unprobed-company
  suppression. No independent timer.
- `scripts/run_resilient_buyer_scout_20261019.py`: updated only the
  owner-maintained **fallback** runner, not production's primary
  `empire_os/buyer_acquisition_scout.py`. Before probing a reviewed
  domain, check positive prior contacts, thread history, suppression
  and bounced-address relationships, and skip already-observed site
  evidence inside a 24-hour cooldown. If no eligible unprobed seed,
  return `COOLDOWN_NO_UNPROBED_RESEARCH_DOMAINS` safely; no automatic
  search retry, no contact, no claim of missed buyer capacity.
- Synthetic contract/security tests cover role and identity conflicts,
  duplicate rows, contact and bounce holds, stale Gmail, direct buyer
  demand/buybox steps, cooldown expiry, PII non-disclosure and safe
  snapshot rejection.

## Business intelligence rules

1. **Same company:** exact canonical website/domain first. Existing
   CRM-proven identity aliases can cause a review hold, not an
   automatic company merge; common names and brands alone are not ID.
2. **Engaged already:** respect prior outbound/inbound, do-not-pursue
   and bounced contacts. Use current CRM reply-owner workflow, not
   "cold first touch" again; a stale Gmail snapshot is not clearance.
3. **Publisher vs buyer:** an intermediary, traffic marketplace or
   affiliate network must demonstrate that it spends **its own funds**
   to purchase a specified product/corridor. Affiliate recruitment
   and intent phrases alone are not verified payment capacity.
4. **Real purchasing intent:** explicitly validate buybox, territory,
   niche, pricing/terms, financial payer, compliance, invoice/checkout
   method and test fulfilment — evidence separately verified before
   commercial activation.
5. **Research allocation:** 24-hour first-party probe cooldown;
   repeat only for a justified fresh buying or inbound signal, not
   because the half-hour cron rotated.
6. **Economic truth:** site fit score, recruiter language, heuristic
   ranks and budgets asserted in text do not equal verified purchases
   or realised revenue.

## Ownership and deployment boundary

- Primary service: `empire-buyer-acquisition-scout.service` (another
  agent's existing owner). **Do not edit it or its modules.**
- Existing bounded fallback cron was deployed earlier with pinned
  source at
  `/home/ubuntu/empire_worktrees/resilient_buyer_scout_release_ace45fb2`
  and runs at :06 and :36. The new code is a staged replacement.
  Current production cron is NOT automatically repointed by a Git commit.
- An optional owner-approved deployment must create a pinned clean
  release worktree at the new commit, verify a read-only preflight,
  replace **only the known tagged fallback cron entry**, preserve a
  rollback copy, and demonstrate the new metadata cache stays within
  owned `runtime/buyer_acquisition/resilient`. No other cron lines,
  root-owned services or active buyer workflows may change.
- Do not create new timers, add paid providers, turn on Search Fabric
  public search, edit CRM roles, import contacts, send mail, buy traffic,
  move funds, or activate buying terms.

## Read-only run command

```bash
cd /home/ubuntu/empire_worktrees/lead_revenue_fabric_unified_20261019
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_buyer_scout_commercial_awareness_20261019 --read-only
```

**Buyer scout upgrade objective:** spend each permitted research probe
to resolve a new real commercial question, recover existing conversations
before cold introductions, and demonstrate verified buyer demand through
canonical first-party evidence rather than domain counts.
