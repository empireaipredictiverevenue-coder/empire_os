# EmpireOS — Original SEO daily-to-F​ounder action lifecycle

**Date:** 26 Oct 2026. **Scope:** existing SEO daily Google index observer, existing weekly GSC growth queue, existing Founder Console. **No second agent, database, scheduler, direct marketing, indexing writer or website publisher.**

## Evidence chain

- Original weekly observer: `weekly_seo_growth_actions_YYYY-MM-DD.json` under `/home/ubuntu/empire_releases/seo_weekly_gsc_two_page_20261022`. It uses final owned GSC *page dimensions*, actual legacy 404 observations, sitemap and live buyer-path inspection. A missing GSC row is NOT proof of zero traffic or demand.
- Original daily owner: `google-index-YYYY-MM-DD.json` under `/home/ubuntu/empire_releases/seo_daily_index_status_20261026`. No Google indexing or URL submissions.
- Original release evidence: `/home/ubuntu/empire_releases/seo_aeo_governed_three_cta_20261026_v2/activation_result.json`.
- Original buyer-journey observer: `scripts.review_live_organic_buyer_journey_20261024.review` by bounded first-party GET. Separates actual existing first-party research forms from enterprise `/commercial` CTA links.
- New lifecycle module `empire_os/search_intelligence/seo_action_lifecycle_20261026.py` maps stable reason+URL action IDs into a staged lifecycle without falsely promoting historical observations into fresh traffic or paid outcomes. Publication is only shown where the original release and a **currently live link** agree.
- New daily runner `scripts/review_original_seo_action_lifecycle_20261026.py`: up to eight exact owned-site, read-only HTTPS QA checks per daily cycle (HTTP 200, canonical, robots/meta, HTML). Holds missing or unsafe evidence rather than guessing. It emits an immutable 0600 `seo-actions-YYYY-MM-DD.json` into the **existing daily SEO owner directory**.
- Existing `scripts/review_daily_original_google_index_20261026.py --write-daily` invokes the new runner only after the primary original daily index review. The primary index receipt and timer status are preserved if optional lifecycle work fails.
- Private Founder page source: `apps/search-command-centre/src/app/founder/seo-operations/page.tsx`; existing Founder Results page links to it. The Next.js process reads only latest private receipt, with exact schema validation and no mutable UI controls.

## Stage semantics

| Stage | Exact meaning |
|---|---|
| detected | Issue exists in original observer data |
| prioritised | Original SEO growth queue assigns priority and original owner |
| staged | Safe technical QA checks generated; no public release |
| tested | Owned site responded 200 with single matching canonical, indexability and HTML checks |
| published | Reachable only through an existing approved public owner release receipt, not through this runner |
| verified | Owner release+live target match, **or** problem proved already solved by an existing first-party research form; former counts as published, latter does not |
| measured | Requires later independent first-party traffic and true downstream buyer/revenue evidence, **unverified at present** |

Do not equate the latest stage with all milestones reached. `state_counts` counts current states and `milestone_reached_counts` counts historically reached stages. No claimed indexation or revenue from a technical test.

## First live snapshot executed 26 Oct

The original weekly archive contained 32 previously identified actions. Reconciliation on 26 Oct identified **three** approved, live AEO direct commercial CTAs and **five** research pages with already existing appropriate enquiry forms (eight resolved, no duplicate forms). Eight more owned pages passed bounded live read-only SEO health checks. There is **no** independently verified increase in rankings, unique visitors, enquiry conversions, commissions or realised revenue in this release. First private lifecycle receipt generated and SHA-256 recorded; it remains immutable even if the lifecycle code is improved subsequently.

## Operational boundaries

- Run daily only as part of the original `empire-organic-search-recovery` timer, which already invokes the original Google index after-review. No new scheduler. Main `preflight_organic_search_legacy_recovery` remains untouched.
- The systemd service's existing `ReadWritePaths=/home/ubuntu/empire_releases/seo_daily_index_status_20261026` permits the lifecycle receipt without adding filesystem permissions. It has **no write permission to the published website**.
- Original Founder Next.js production build is under concurrent owner changes. The route should be released through the ORIGINAL Founder UI owner after reconciling their working tree and rebuilding/restarting that **existing** app, not copied blindly over the current `.next` tree.
- The second layer of “hands” — bounded, reversible public metadata/link mutations with backups — must use each original page publisher, hash-gated release and explicit scope. There is no general unsupervised page writer.
- A completed action may still have **zero realised revenue**. Commercial systems must later join organic source attribution → consented enquiry → approved buyer/offer → verified settlement in the existing CRM and EmpireDB PostgreSQL.

## Replay and verification

```bash
cd /srv/empire_os

# Safe observation; shows headline and at most 8 actions, no website writes:
PYTHONPATH=. .venv/bin/python -B -m scripts.review_original_seo_action_lifecycle_20261026

# Original owner hook; on scheduled daily cycle:
PYTHONPATH=. .venv/bin/python -B scripts/review_daily_original_google_index_20261026.py --write-daily

# Existing Founder route after standard UI owner release:
# http://127.0.0.1:3001/founder/seo-operations
```

**Security:** Never expose private receipts through public gateway; remain under the existing private Founder Console. Do not create third-party backlink purchases, mass AI doorway pages, unconsented contact, speculative revenues or unauthorised Google submissions.
