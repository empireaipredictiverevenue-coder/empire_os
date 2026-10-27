# Microsite Factory — Original Owner Integration Handoff (27 October 2026)

**Purpose:** Close existing owner-to-owner handoffs. Do not create another publisher, CRM, scheduler, predictive database, revenue table or analytics collector. This is a read-only acceptance packet. All website/SEO changes stay with their current owners.

## Current verified state

- Existing production site owner `empire_os.owned_campaign_release.load_release()` independently validates **five existing owned research campaign deployments** from `runtime/astra/owned_campaign_deployed_release.json`. These are **not** microsite factory publications.
- Original release contract requires **exactly five campaigns** and recomputes campaign HTML/asset digests. It has no factory `candidate_id -> original noindex preview -> approved deployable asset` mapping. **This is the specific release contract gap.**
- Factory stage has **two research candidate packets**, no authenticated owner-approved factory releases, no factory GSC metrics, no site-to-enquiry receipts and no independently settled attributable revenue. Unknown measurements remain unknown (not zero).
- Only existing first-party GSC baseline is for two older approved pages (separate from the factory). Buyer ZIP targeting guidance is not approval to launch or evidence of payment.
- Original Predictive Cloud forecast registry read role exists but its read-only DSN is not present in the factory shell. No independent calibration source bundle is currently attached here. Scores remain *research-review priority*, not model ROI or demand predictions.
- Current `SlopMonster` stage checks editorial cliché/patterns, generates a quality score, and leaves drafts in private review. It cannot judge truthful marketing claims or accessibility on its own.

## Handoff sequence (one canonical site/CRM/data flow)

| Existing owner | Exact source/API | Next owner action and acceptance evidence |
|---|---|---|
| **Predictive Cloud** | `predictive_registry_transport.PostgresPredictiveRegistryReader` + `microsite_calibration_bridge_v4.review_historical_model_calibration` | Supply source-custodied pre-outcome forecasts and subsequent independent actuals with exact keyword, market, ZIP/postcode, model, forecast date and outcome date. Require at least three independently verified out-of-sample cases for the queue's calibrated tag. Never use in-sample R² as validation. |
| **Website publishing (with SEO owner)** | `owned_campaign_release.load_release` and `owned_campaign_preflight.inspect_campaigns` | Extend the **existing** original release contract (not the frozen five-campaign release file) to admit one genuinely useful, unique factory page; verify `candidate_id`, noindex draft SHA, reviewed deployable HTML SHA, exact canonical `campaign_<24hex>`, `campaign:landing`, HTTPS `/research/<campaign>`, source/claims, SlopMonster copy findings, mobile visual inspection, rights/consent and independent owner approval. Preserve existing live releases. Output a site-owned immutable readback with true deployed SHA and source preview SHA. |
| **SEO/GSC** | `search_intelligence.weekly_two_page_outcomes` existing owner; V5 `original_seo_first_party_gsc` page reader contract | Add exact approved-page + reporting-window resolution for newly released canonical URLs. Return original indexed-page impressions/clicks with provenance. Do not substitute global property totals or counts for older pages. |
| **First-party analytics/CRM** | `owned_campaign_intake.validate_event`; canonical CRM owner | Reuse original `campaign_page_view`, `campaign_cta_click`, `campaign_enquiry_started`, `campaign_enquiry_submitted` schemas and strict UUID/event/source/consent rules. Bind source events to exact approved asset hash and reporting dates; return verified sessions, consented and qualified enquiries, and unique buyer-accepted event IDs from the original CRM. Don't count every click as a lead. |
| **Settlement / finance** | Canonical original finance settlement readers; `microsite_verified_outcomes_v5.reconcile_approved_page` | Supply only settled cash rows with unique settlement receipt and original accepted-event refs, amount in minor units and currency. V5 sums individual receipts, prevents reusing the same accepted event on another microsite, checks the owner total and rejects arbitrary revenue booleans. |

## Immediate next bounded release
The current owner should choose **one** genuinely useful microsite, prove actual demand/territory utility, and produce owner-reviewed deployable source (not a swapped ZIP doorway template). No automatic multi-domain spinning. Review and release must happen in the existing site owner's active worktree and change window, not in this marketing branch; the SEO implementation workstream remains separately owned.

There is **no permission here** to publish the site, un-noindex pages, activate buyer phone numbers, spend on PPC, send emails or enable payment collection. All changes must be separately authorised and verified by the owning source.

## Machine-readable original release handoff

The existing one-shot `scripts/review_ranked_microsite_outcomes_v4_20261027.py` now reads the actual incumbent `load_release()` and adds `original_site_owner_release_handoff.json` to the existing private output folder. Unlike an imagined release state, the owner reader validates the current production asset manifest. A false/unavailable source yields **unknown** original counts; it never greenlights a factory release.

Staged private report:
`/home/ubuntu/empire_releases/predictive_microsite_factory_slopmonster_v4_20261027_stage/original_site_owner_release_handoff.json`

Run remains the **same V4 command**. No additional agent, daemon, database, network API, site build or SEO owner changes.

## Owner acceptance order
1. Predictive owner attaches genuine forecast/actual evidence, or leave the calibrated designation **unverified**; research can continue meanwhile.
2. Website + SEO owners admit and deploy exactly one reviewed genuinely useful page in their original release mechanism, return dual SHAs and canonical campaign ID.
3. Existing GSC/event/CRM/settlement owners expose bounded read-only source readers for that exact page and reporting period.
4. V5 independently reconciles all sources. Failed/unknown joins remain `null`. Only truly settled original cash can be counted as realised attributed revenue.

**Source state on 27 October 2026:** original five campaigns released, factory zero released, calibrated factory zero, payable factory settlements unverified. No production changes made by this handoff.
