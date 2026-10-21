# EmpireOS / Jev — real original-page evaluation intake

2026-10-22 · Existing Search Intelligence, GSC and Jev typed-decision architecture.

## Verified original URL observations — NOT ground truth
- First-party GSC property sc-domain:empire-ai.co.uk; final **page-only** dimension, 7–19 October 2026, with existing allowlisted same-origin HTTP checks (not a new crawler).
- 32 returned GSC page rows; two homepage aliases excluded; **30 deduplicated legacy owned-URL rows** currently HTTP 404, **44 page-only impressions**, zero returned clicks.
- Original review categories: 11 Empire product topics, three roofing, one buyer-intent/TAM and 15 off-core. These classifications are NOT Jev predictions, reviewed truth, ranked opportunities or verified commercial value.
- 30 private candidate records with stable case IDs, original owned URL paths, first-party sample window, observed HTTP status and evidence digest. All human review labels are empty.
- Private immutable one-shot receipt: /home/ubuntu/empire_releases/search_jev_owner_receipts_20261021/jev_original_page_review_intake_20261022.json (0600; directory 0700); SHA-256 f4e224ba92bf00e7c36da857ee96e09d6c9f13233d19d7db192b55b5afe52c26. No URL-level evidence in Git.
- Existing private Search Intelligence API: /v1/search/jev/evidence/summary — scalar-only readout pinned to exact receipt digest. No original URL paths, GSC queries, customer records or external Jev inference in this API response.
- Source for an operator panel added to private /department/quora workbench; do not equate 30 observations to accepted human labels.

## Required original human review
1. Authenticate independent reviewers through existing first-party access, and show the original URL, source receipts, current page and historical context privately. User-submitted reviewer IDs or Boolean assertions do not by themselves prove identity.
2. Independently inspect the original content/equivalent target and publisher rights before proposing redirects, page restoration or publication.
3. Record real reviewed labels and their true reviewer provenance. Synthetic, cloned or deterministic URL taxonomy labels never qualify as human ground truth.
4. Compare Jev and deterministic baseline only for the **same task and same case**. The first real Jev call classified an *aggregate* sample; no fair comparison to URL-level labels is possible without task-matched observations.
5. Retain the existing evaluation gates: substantial real labelled sample, independent review, offline accuracy/calibration/latency/cost measurement, safe fallback, monitored drift and separately scoped authority to activate repeated inference.

## Operational scope
The one-shot review script scripts/review_jev_original_pages_20261022.py reuses existing GSC and Host-pinned first-party probes. --write-private performs an O_EXCL write only once in the existing secured owner evidence folder; repeated attempts are blocked. Default mode outputs summary only. No new keys, databases, schedulers, paid traffic, publishing, outreach or payments. API summary requires the pinned SHA-256; source drift fails closed.

Production mode remains OBSERVE; accepted human labels = 0; benchmark-ready cases = 0; unattended Jev inference = OFF.
