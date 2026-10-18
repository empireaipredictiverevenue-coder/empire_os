# Empire AI SEO department — evidence-led legacy 404 prioritisation
18 October 2026 | Existing department operator, no new job/service

## Why this was needed
The integrated SEO reader initially showed only the aggregate legacy 404
count. That could tempt indiscriminate page regeneration and mass 301s.
The existing independent first-party GSC page-only legacy reviewer already
classifies each historical /aeo URL. This patch consumes that exact bounded
queue within the current integrated department report; it does NOT generate
a second crawl, search provider, publication job or indexation signal.

## Verified Google Search Console window
Final sample 4–16 October 2026:
- 34 returned page rows; 76 reported impressions and **1 reported click**
  across those rows. This is a PARTIAL PAGE-DIMENSION SAMPLE, not a
  complete property traffic census, observed search ranks or buyer receipts.
- 31 legacy /aeo URL rows were live 404, representing 48 impressions and
  zero reported clicks in the returned subset.
- 11 Empire-branded product-topic editorial checks.
- 4 roofing topical / geographic editorial research checks.
- 1 accounting TAM buyer-intent editorial review.
- 15 off-core pages whose correct action is to **retain 404 pending
  evidence**, NOT mass rewrite them or invent corresponding products.
- Core editorial review count = 16; no redirect/page restoration approved.

The reviewer does not automatically infer topical identity or replacement.
Its original per-URL queue remains available through
scripts.review_live_search_page_404_revenue_readonly.

## Connected operator
./.venv/bin/python -m scripts.review_seo_department_integrated_20261018 --review-only

New bounded report fields:
- gsc_returned_page_sample_clicks
- gsc_returned_page_sample_impressions
- legacy_404_editorial_category_counts
- legacy_404_core_topic_editorial_review_count
- legacy_404_off_core_retain_404_count
- legacy_404_restorations_approved (always zero without owner approval)
- legacy_404_redirects_approved (always zero without owner approval)

Validated input must match the existing historical GSC window and 404
queue, category counts, path uniqueness, live 404 response, and reported
impression/click subtotals. Unsafe/unreviewed source envelopes fail closed.

## Operational priorities
1. Review the 11 Empire product topics against actual current products;
   preserve original brand naming and official claims.
2. Review four roofing topics against first-party roofing expertise and
   verified geography only (no generic templated city doorway pages).
3. Review accounting TAM topic only when existing commercial scope and
   adequate original subject-matter evidence exist.
4. Keep 15 off-core URLs retired pending real product/topic equivalence.
5. Have ASTRA handle website publication, canonical and internal linking
   in its controlled flagship release only after review.
6. Independently verify ranking/citation provider and genuine consented
   buyer enquiry → EmpireDB receipt → CRM before claiming organic revenue.

No site assets or HTTP routes, source permissions, scheduled units, DB,
Search Intelligence server, customer rows, provider credentials, paid
requests, checkout or outbound marketing were changed.
