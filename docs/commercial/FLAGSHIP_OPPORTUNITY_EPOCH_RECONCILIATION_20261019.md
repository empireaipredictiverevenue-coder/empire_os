# Empire AI — Opportunity Factory snapshot epoch recovery

19 October 2026 | Predictive Decision Control isolated owner branch

## Verified production evidence (read only)

The existing canonical Opportunity Loop last completed successfully at 18:39:16 UTC with 11 Radar candidates; all eight of its stage steps reported success and it was in OBSERVE mode. The independently refreshed Radar snapshot later advanced to 14 candidates. Existing Factory intake, routing and Quant snapshots remained at 11. Exact identity comparison found that all 11 original downstream records remain in Radar, with precisely three new Radar opportunity identities missing from each downstream stage and zero reverse mismatches. The downstream three stage sets agree. The source-epoch skew was within the existing permitted time window, but **cross-stage identity equality failed**.

The existing `revenue_evidence_pathways` correctly returned `cross_stage_identity_join_mismatch` and its dependent buyer evidence handoff returned `authoritative_current_pathways_not_ready`. The earlier roofing opportunity reference must therefore not be treated as freshly reconfirmed. The current state is **not** proof of missing or unqualified buyers, predictive failure, or a lost commercial deal.

## Implemented without stepping on other agents

- `empire_os/flagship_source_epoch_reconciliation.py`: bounded, read-only reconciliation of the existing Radar / intake / evidence-router / Quant source snapshots using the existing authority, freshness and identity validators. Reports aggregate counts only, never raw keys or contacts. It does not heal, rewrite, waive, or silently intersect inconsistent source populations.
- `empire_os/flagship_first_payer_owner_handoff.py`: when the original commercial owner request is held, includes the safe epoch diagnostic and points to the existing Opportunity Factory owner. A currently valid buyer handoff stays untouched.
- `scripts/diagnose_flagship_source_epoch_20261019.py`: explicit `--read-only` command; no writes or queue activity.
- `tests/test_flagship_source_epoch_reconciliation.py`: verifies added upstream entries, cross-stage mismatches, stale/future/tenant-scoped source rejection, deep contract failure, no leakage, unchanged originals, and owner routing.

## Exact recovery owner / workflow

**Owner:** Existing Opportunity Factory / canonical Opportunity Loop, not the Predictive Decision Control agent or CRM team.

After coordinating with its producer owner and current job schedule, regenerate the existing coherent downstream source stages using the current Radar baseline and current research/normalization evidence, then verify intake, router and Quant all match the Radar exact identity set. The canonical Opportunity Loop already orders Radar, research, normalization, intake, Quant, value and routing, then the planner. Because the complete loop also writes a Coder planning queue, it must not be run ad hoc from this diagnostic branch. Do not call `--force` or restart production services here.

The owner should use its existing safe workflow, confirm a successful post-refresh immutable source checkpoint, and rerun the read-only diagnostic. Require `FOUR_STAGE_SOURCE_IDENTITIES_ALIGNED` and a canonical pathway result of `EVIDENCE_PATHWAY_REVIEW_READY` before Business Development resumes the original first-party buyer evidence request. If the authenticated buyer evidence still is not available, keep the buyer work held.

## Verification command (read-only, existing owner worktree)

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.diagnose_flagship_source_epoch_20261019 --read-only
```

No forecast registered, no business terms authenticated, no payment or fulfilment verified, no pricing fabricated, no database writes or outbound. The new diagnostic provides **source reconciliation only**, not a prediction, statistical precision claim or go-live approval.

## Subsequent live verification

The original production producers subsequently converged to 14 Radar, 14 intake, 14 routing and 14 Quant records. Canonical pathway validation passed. This branch did not trigger the refresh.

The new first-party request had an unknown niche. The handoff now explicitly holds market identity and routes its verification to Market Intelligence, without guessing that it is roofing or authorising a forecast.

## Source churn discovered on subsequent inspection

The independently refreshed Radar later returned to 11 opportunities while intake, routing and Quant retained 14. The three downstream-only rows were all existing `community_pain` research hypotheses with a null niche. This is not evidence of three dropped buyers, conversion failures or lost revenue.

The current Community Intent snapshot advertised four pain briefs, none with the `opportunity_event` required by the existing Radar builder, and its latest Radar source contribution was zero. A previous Opportunity Loop had reported 14. Multiple existing workflows refresh the same Radar source without simultaneously rebuilding every downstream stage, so a passing momentary snapshot can later become inconsistent.

The read-only epoch diagnostic now reports the restricted source contribution, allowed class buckets, and number of downstream-only rows without niche. When exactly these original Community Intent entries disappear, it routes a `COMMUNITY_SOURCE_POPULATION_CHANGED` hold to the existing Opportunity Factory owner, with a dependency on its existing Community Intent source owner. It never edits original pain briefs, invents taxonomy, runs another scheduler or promotes an unknown niche into buyer matches. The canonical full four-stage join remains required before resuming buyer-specific evidence work.
