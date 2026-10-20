# Empire AI — Sales Director Conversation Conversion Casebook
Date: 20 October 2026

## Built in isolated Commercial Growth branch

Worktree:
`/home/ubuntu/empire_worktrees/video_commercial_framework_20261019`
Branch:
`feature/video-commercial-framework-20261019`

Files:
- `empire_os/commercial_conversation_casebook.py`
- `scripts/review_commercial_conversation_casebook_20261020.py`
- `tests/test_commercial_conversation_casebook.py`
- `tests/test_commercial_conversation_casebook_cli.py`
- `empire_os/commercial_shadow_offer_reconstruction.py` (shared pure reconstruction helper)

## Actual non-executing preview of owner snapshots

The owner commercial offer-book builder was run IN MEMORY with the current available stored catalog, distribution, and buyer research inputs. No canonical refresh producer was invoked.

- Shadow review targets: 255 historical research/offer targets.
- 49 shadow targets carry conversation references.
- 52 distinct original conversation IDs, 52 exact `root_intent_id` matches in current conversation-recovery snapshot.
- 43 review cases need fresh commercial provenance and original inbox/opt-out verification before possible next steps.
- 9 remain held on missing canonical context or suppression flags.
- 3 source recovery records have no match in the shadow offer review.
- 0 verified inbound replies, 0 new sales, 0 outbound permissions, 0 CRM mutations or new buyer identities were established by this casebook.

**Cases are not verified buyers or verified inbound replies.** The recovery flag `recoverable` is just a historical workflow state; it cannot authorize a live follow-up. Original provider events, contact identity, tenant scope, reply context, opt-out and suppression must be checked by the existing Sales Director/CRM owner.

## How the casebook can be used

Cases are sorted with suppression/context and ambiguity holds ahead of ordinary historical thread reviews. Every case has:
- An operator-only case number and read-only state.
- A 1-based **original conversation recovery snapshot row number** that an authorised operator can use to inspect the source.
- A 1-based **shadow offer row number**, valid only for the same in-memory reconstruction, *not* the historical September output.
- Product codes as research context, not quotes, deal matches or accepted terms.
- Verified **false** flags for recent reply, contact binding, opt-out check, inbox inspection and outbound permission.

No company names, email addresses, original conversation IDs or personally identifying details appear in printed casebook output. Case numbers and row numbers refer to the input snapshots as used at calculation time and must be revalidated when upstream sources update.

All joins are exact on the original `conversation_refs` and `root_intent_id`, never matched by company name, recipient email, domain, social author or inferred identity. Duplicate exact references and ambiguous recovery IDs are held.

## Run

```bash
cd /home/ubuntu/empire_worktrees/video_commercial_framework_20261019
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_commercial_conversation_casebook_20261020 --read-only
```

The script prints JSON to stdout, performs no disk writes, and does not connect to Gmail, mail APIs, the database, the CRM, a publisher or a campaign engine.

## Ownership and release boundary

This is an offline reporting component only. Existing Sales Director owns live inbox and provider receipt inspection, suppression, reply/recovery case handling and any governed next steps. Commercial catalog owner owns products/terms, and Buyer Development owns direct-purchase evidence.

Never auto-send, infer buyer intent from historical deliveries, merge agent owners, schedule tasks, deploy to production or refresh upstream snapshots from this branch.

Run regression tests (including historical owner consumers):

```bash
cd /home/ubuntu/empire_worktrees/video_commercial_framework_20261019
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
 tests/test_commercial_conversation_casebook_cli.py \
 tests/test_commercial_conversation_casebook.py \
 tests/test_commercial_distribution_shadow_cli.py \
 tests/test_commercial_distribution_shadow_refresh.py \
 tests/test_commercial_shadow_reconstruction_cli.py \
 tests/test_commercial_shadow_offer_reconstruction.py \
 tests/test_commercial_growth_owner_bridge_cli.py \
 tests/test_commercial_growth_existing_owner_review.py \
 tests/test_video_commercial_growth_framework.py \
 tests/test_commercial_offer_book.py \
 tests/test_gtm_offer_strategy.py \
 tests/test_commercial_funnel.py \
 tests/test_revenue_os_learning.py
```

**Release status: isolated, not deployed.** Requires source owner review and separate production approval.
