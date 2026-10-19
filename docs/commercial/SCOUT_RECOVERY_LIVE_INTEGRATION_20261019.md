# Empire AI — Live Scout → Buyer Recovery Desk integration

**19 October 2026. Existing EmpireDB / production on 62.210.95.205.**

## Live release truth

The existing Buyer Recovery Desk now has two source-matched, additive
read-only extensions on production:

1. `empire_os/buyer_recovery_scout_consumer.py` checks the existing
   private Scout/Buyer Network review for exact original-source hashes,
   unique company domains, source URL evidence and all zero-authority flags.
   `empire_os/buyer_recovery_action_desk.py` preserves the original
   deferred-enrichment packets and adds `scout_network_research_review`.
2. The existing `scripts/build_buyer_recovery_action_desk.py` now uses
   `scripts/materialize_scout_network_review_20261019.py` to refresh
   the optional, mode-0600 Scout sidecar **on its existing research cycle**,
   before preparing the original Desk private packet. The helper uses
   `empire_os/acquisition_candidate_quality.py` and
   `empire_os/acquisition_network_handoff.py`, both scoped to OBSERVE
   research and exact-source review.

Both releases used source-pinned backups and no systemd or database change.
No extra scheduler, agent, payment, checkout, marketing send, CRM buyer
promotion or first-party contact authority has been enabled.

## Verified end-to-end runtime receipt

Normal production command:

```bash
cd /srv/empire_os
PYTHONPATH=$PWD ./.venv/bin/python -B scripts/build_buyer_recovery_action_desk.py --write --repo-root /srv/empire_os
```

Production result on 19 October 2026:
- `scout_source_refresh=SOURCE_LINKED_SCOUT_REVIEW_REFRESHED`
- `scout_research_review_status=SOURCE_LINKED_RESEARCH_ONLY`
- 25 existing Recovery Desk packets retained.
- 11 additional Scout source-linked research tasks (snapshot-specific).
- 10 first-party business site URLs for verification, one source held.
- `outbound_sent=false`, `db_write=false`, `commercial_authority=NONE`.
- Final private Desk output permissions **0600**.
- The existing 30-minute Scout timer remains active, no new timer.
- 12 original production Recovery Desk tests and 81 scoped feature/Scout tests passed.

## Source staleness behavior

If Scout, original social registry, Buyer Network discovery, or founder
qualification changes during the guarded read, the optional refresh reports
`SCOUT_REVIEW_REFRESH_HELD`. The core Recovery Desk packet is still created.
Its Scout section is either stale with zero promoted tasks, or explicitly
`SOURCE_UNTRUSTED_HOLD`. Neither changes buyer authority.

**These are not 11 verified buyers, an approved send list, contracted
payouts, booked revenue or confirmed source use permissions.**

## Rollback / owner boundaries

Reversible source releases retained under:
- `/home/ubuntu/empire_release_backups/buyer_recovery_scout_consumer_20261019v1`
- `/home/ubuntu/empire_release_backups/scout_review_autorefresh_20261019v1`

Rollback in reverse order from the isolated worktree:

```bash
cd /home/ubuntu/empire_worktrees/acquisition_source_truth_20261019
/srv/empire_os/.venv/bin/python -B scripts/deploy_scout_review_autorefresh_20261019.py --rollback-own-changes
/srv/empire_os/.venv/bin/python -B scripts/deploy_buyer_recovery_scout_consumer_20261019.py --rollback-own-changes
```

Only the pinned installed file hashes can be rolled back. Abort if any
other agent has since changed those files.

## Commercial next proof

Buyer Network still needs independently verified payer capacity,
approved accepted lead/call unit and payout, matching UK/USA territory,
real decision-maker/contact permission and suppression checks. All remain
under the existing Buyer Network/CRM authority, not automatically advanced.
