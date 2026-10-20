# Empire AI — Adaptive Sales Director Evidence Control
Date: 20 October 2026
Branch: `feature/video-commercial-framework-20261019`
Isolated worktree: `/home/ubuntu/empire_worktrees/video_commercial_framework_20261019`

## What changed

The commercial workbench now has a deterministic **observe → compare → explain → choose existing owner → hold/recheck** layer.

- `empire_os/commercial_sales_director_adaptive_review.py` — pure, repeatable adaptive state transitions; previous safe review plus current original evidence; evidence semantic hash; optional owner-supplied original-source receipt manifest; stateful deduplication when the existing orchestrator preserves previous output.
- `scripts/review_adaptive_sales_director_20261020.py` — manual read-only CLI reusing the existing Conversation OS original-proof readers and accepting an optional previous output; NO state writer.
- `tests/test_commercial_sales_director_adaptive_review.py` — synthetic transitions, safe owner routing, fingerprint validation, tamper resistance, unknown-source rejection, aggregate-to-case trust boundaries and privacy checks.
- `tests/test_commercial_conversation_casebook_cli.py` — command-line replay and owner-source-receipt change tests, and unchanged original owner consumer tests.

The previous Sales Director original-proof CLI now also exports `build_original_proof_runtime()` for reuse. This prevents a second proof-reading implementation.

## Response policy and adaptive state machine

| Scenario | Output transition | Automatic response |
| --- | --- | --- |
| First observed original-proof hold | `INITIAL_EVIDENCE_REVIEW` | Explain blockers once; output existing owners' review suggestions |
| No meaningful difference from previous report | `UNCHANGED_HOLD_NO_DUPLICATE_WORK` | Suppress repeated attention and duplicate work |
| Original owner source receipt changes, but no meaningful proof changes | `OWNER_SOURCE_CHANGED_NO_PROOF_UPGRADE` | Quiet re-evaluation only, no outreach or invented verified progress |
| Case counts, source blockers, original Conversation OS control/reply counts or action mix change | `MATERIAL_EVIDENCE_STATE_CHANGED` | Re-evaluate existing owner review suggestions, still no case-level reply authentication |

No LLM guesswork, fuzzy prospect matching, new autonomous owner, mail send, CRM mutation, agent job dispatch, buyer activation or external API call.

The human-readable `plain_language_reason` tells the operator *why* the system chose that action. The explicit `review_actions_not_dispatched` from the original proof becomes `existing_owner_review_suggestions` and `operator_attention_due`.

## Authenticity and safety are independent of the state machine

An aggregate claim of even 50 authenticated inbound replies **cannot verify a specific case**. Only independently admitted, original per-thread provider messages, tenant/contact binding, current suppression and commercial qualification can change that. Existing Conversation OS and Sales Director own those checks. The current contract deliberately always returns commercial execution authority `none`.

Source receipt hashes (when provided by the original owner) are change detectors, **not** evidence of message authenticity. Source names and SHA256 digests must satisfy a strict allowlist and never expose message bodies, recipients or raw thread IDs.

## Integration contract with the existing orchestrator

The engine is purely functional:
```python
adaptive_original_proof_review(
    current=original_proof_report,
    previous=previous_adaptive_review_or_none,
    source_receipts=source_owner_fingerprints_or_none,
    now=aware_utc_clock,
)
```

The existing orchestrator must provide/persist the previous privacy-safe review under its own approved storage policy and call the engine when actual source events change or on its pre-existing cycle. **This isolated branch does not add a daemon, timer, database table or production checkpoint writer.**

CLI first review:
```bash
cd /home/ubuntu/empire_worktrees/video_commercial_framework_20261019
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_adaptive_sales_director_20261020 --read-only
```

Re-evaluation with an owner-held previous report:
```bash
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_adaptive_sales_director_20261020 --read-only \
  --previous-review-file /path/to/existing/approved/previous-review.json
```

Optionally accept an externally supplied allowlisted digest manifest using `--owner-source-receipts-file`; both flags accept `-` for stdin (not simultaneously).

## Current source reality

The previous original-proof integration saw 52 historical exact-thread review cases, of which 43 required fresh commercial-source evidence and 9 had suppression or context holds. Original Conversation OS reported zero canonical inbound messages, zero authenticated individual reply joins, 5 of 11 verified internal controls, and a mailbox observer with no complete inbound message. **Nothing in this adaptive upgrade changes those original evidence states.**

## Verification and deployment

Run `pytest` for adaptive tests, original-proof regression, conversion casebook CLI, existing Conversation OS and CRM tests, and commercial-source consumer tests. Synthetic end-to-end tests verify initial versus unchanged review, forged-source rejection and no private data in reports. The new code has no writes, sends, orders, owner reassignment or customer contact rights.

**Not deployed.** Release requires existing orchestrator ownership approval for persistence, scheduled use, change-triggers and integration, and separate authorization for anything that could contact a customer.
