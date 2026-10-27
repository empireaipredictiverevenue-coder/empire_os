# Empire AI — earned-media / consultancy commercial evidence reconciliation

**Observed 27 October 2026; READ ONLY; not website release or buyer authorisation.**

## Original source lineage restored without copying/upserting data

The earned-media operator CLI previously defaulted `--pr-root` and `--distribution-root` to its isolated review worktree. That hid the original, already available PR consulting files and `/srv/empire_os/runtime/revenue_distribution/latest.json`, incorrectly reporting **0** research leads and source gaps.

An opt-in `--existing-original-source-map` now points **only** to:
- Existing PR source branch worktree `/home/ubuntu/empire_agents/empire_pr_consultancy_20261011`, where provider sent-receipts, outlet notes and founder-approved *starting-price policy* originate.
- Canonical existing Revenue Distribution at `/srv/empire_os/runtime/revenue_distribution/latest.json`.
- This existing isolated earned-media worktree for original website-independent demand research and the dated public index observation `docs/commercial/PR_CONSULTANCY_MARKETPLACE_PUBLIC_OBSERVATION_20261027.json`.

**Repeatable operator command** (in isolated worktree):

```bash
cd /home/ubuntu/empire_worktrees/earned_media_advisory_bridge_20261025
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_earned_media_advisory_bridge_20261025 \
  --review-only --with-leadgen --existing-original-source-map --summary
```

Source files are loaded in-place, source hashes preserved, no research row imported into CRM. All four previously held source health fields were restored to `EVIDENCE_FILE_READ`.

## Real observations ≠ qualified prospects

The reader now reports **23 historical research observations**:
- **3 source-only demand signals**: two direct Upwork RevOps/CRM specialist requests, one brokered Australian dashboard listing.
- **8 canonical research accounts**, not intent-verified purchasers.
- **12 identity-unbound research accounts**, not CRM prospects.
- **0 verified qualified buyers, 0 outreach-eligible, 0 proposal-eligible and 0 verified revenue**.

Public search recheck on 27 October: both exact Upwork URL results appeared in the public search index, with specialist HubSpot implementation evidence required and many competing proposals. Direct unauthenticated Upwork page retrieval returned 403, so **authenticated listing availability, buyer identity, supplier eligibility and permission to apply are NOT verified**. The brokered Flexstack source was inaccessible through the independent public retrieval and remains HELD. Do not upgrade these observations into confirmed buying conversations, leads, appointments, contracts or pricing.

Potential starter offers in the existing founder PR consultancy policy are historical approved **starting prices**, not client-specific quotes: £2,500 assessment, £7,500 strategy blueprint, £3,000/month strategic advisory. No contact, proposal, payment or live product activation is authorised by that policy.

A local **illustrative, not buyer-specific** ERP-to-CRM revenue-lineage sample was generated successfully for the highest public research signal (`leadreview_ac36776ad29081378b678e8b`), covering source-of-truth, join IDs and duplicate handling, commercial relevance, forecasting hygiene and delivery scope. It explicitly denies access to client systems, verified HubSpot delivery, a secured budget, or real results. No email, bid or quote was sent.

## Original PR reply check

The original founder-approved 11 October PR evidence contains two SENT provider receipts: **Prolific North** and **BusinessCloud**. I independently read those exact threads using the connected **personal** Gmail account on 27 October. Each contained one original sent message and **no inbound publisher reply within the thread**. The same thread IDs did not resolve through the separate professional Gmail account. This is direct thread evidence as observed, NOT a claim that no publisher ever replied elsewhere or through a different channel. No duplicate pitch or follow-up sent; suppression and current publisher contact rules remain required.

## Current canonical revenue blocker

Latest `/srv/empire_os/runtime/commercial_loop/latest.json` snapshot on 27 October reports 25 sent/delivered/replied outbound intents across the **wider** commercial engine but 0 verified buyer conversations and 0 commercially accepted terms. The canonical revenue pulse reports **0 recognised revenue**. These wider intents are NOT the 23 earned-media research observations or the two PR publisher sends and must not be double-counted.

**Next legitimate action:** Prioritise genuinely verified buyer reply/requirement evidence or authorised authenticated application on a direct job with demonstrable HubSpot implementation competence. Confirm seller delivery capacity, current buyer scope, platform terms and identity before any personalised proposal. Use the existing canonical CRM and revenue-recognition pipeline **only** for actual consented/authorised, provenance-backed events. The original ASTRA team exclusively owns the separate 708-file website release through PR #125; no site editing or release operations from this commercial lane.

## Test / ownership boundary

**60 scoped commercial Python tests passed** after the original source-map and fresh public-search-index reader update. An exploratory wider run had **85 passes and one unrelated owner-baseline check failure**: `tests/test_earned_media_public_cta_release_20261026.py::test_owner_release_patch_and_manifest_match_exact_current_review` returned `HELD_PUBLIC_OWNER_BASELINE_OR_PATCH_DRIFT` rather than the obsolete two-file patch's expected match. That historic public website source/patch is under the **separate original ASTRA release**; do not rewrite the accepted 708-file candidate, published website, protected backup or SEO pages from this commercial lane.
