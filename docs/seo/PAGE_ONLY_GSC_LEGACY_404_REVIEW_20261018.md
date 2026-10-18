# Empire AI — GSC page-only legacy 404 review with existing SEO observer
18 October 2026 | Isolated feature | Existing first-party Search Intelligence

## Architecture delta and ownership

Purpose: close a verified measurement gap without another crawler or agent.
Reuse the existing Search Intelligence endpoint
/v1/search/search-console/pages and the pre-existing
scripts/review_live_search_404_revenue_readonly.py first-party Host-pinned
GET transport, allowlisted URL paths and HTTP evidence checks.

Pure analysis module: empire_os/search_intelligence/legacy_404_page_review.py
One-shot CLI: scripts/review_live_search_page_404_revenue_readonly.py

The prior query/page reviewer is unchanged except for one fixed GET endpoint
allowlist addition. No new service, worker, model, database table, timer,
crawl runtime, Search Console credentials, Cloudflare rule, redirect, paid
data provider, email or payment authority.

## Exact live observations
Google property: sc-domain:empire-ai.co.uk.
Window: 8–17 October 2026; final-data page-only GSC observations.
The new code reused the GSC source and verified 26 same-origin URLs:
- 28 returned page GSC rows, with 53 impressions and 0 clicks.
- 2 excluded root homepage aliases (apex/www); not probed as legacy AEO.
- 26 allowlisted legacy AEO URLs, all currently HTTP 404, with 37
  returned impressions and 0 returned clicks.
- Classifications: 11 Empire-branded product topic research candidates;
  three roofing research candidates; one existing TAM buyer-readiness
  editorial topic; eleven off-core topics.
- Classification relies only on URL path. Original content/rights and
  genuine commercial fit remain unverified.
- The four published priority industry/product URLs have crawlability
  signals but no rows in this particular historical GSC page sample.

Page-only GSC rows and query/page GSC rows have different anonymisation
and aggregation properties. NEVER add their totals together or equate
impressions to visitors, Google indexing, real buyers or revenue.

## Review shortlist, not a publication order
Historical product-labelled routes that merit original-content review:
- /aeo/empire/ai_lead_gen/ : 2 impressions
- /aeo/empire/empire_leads_engine/ : 2
- /aeo/empire/empire_templates : 2
- /aeo/empire/commercial_roofing/ : 1
- /aeo/roof-repair/MIN/ : 2
- /aeo/roofing/PVD/ : 1
- /aeo/accounting/TAM/ : 1

For the TAM buying-readiness topic, reuse existing unpublished original
research in docs/seo/BUYER_INTENT_TAM_EDITORIAL_DRAFT_20261015.md. Do not
generate a near-duplicate or invent original historic content.
For roofing, coordinate with the already-published genuine industry page.
Off-core legacy locality pages can legitimately remain 404. Require
verified original source, publisher rights and substantive equivalent
target before considering a narrowly matched recovery or redirect.

The prior recovery asset register contains review material but does NOT
automatically grant publication rights, buyer intent or historical
content authenticity. No mass redirects or thin doorway pages.

## Repeatable read-only operator
Run from the isolated worktree:
  cd /home/ubuntu/empire_worktrees/seo_page_only_legacy_404_20261018
  /srv/empire_os/.venv/bin/python -m scripts.review_live_search_page_404_revenue_readonly --start-date 2026-10-08 --end-date 2026-10-17 --summary-only

Summary-only prints counts and categories, not individual public paths.
Full mode includes only allowlisted owned URL paths (never search terms).
Invalid date windows, GSC property/provenance, untrusted metrics,
duplicate URL aliases or unsupported HTTP statuses return HELD rather
than a misleading clean result. No scheduling is installed.

## Integration ownership
SEO owner: inspect this isolated branch, run focused tests and cherry-pick
only the review module, fixed allowlist change, one-shot CLI and tests.
No systemd restart is required for a one-shot standalone tool; the page
dimension API is already live. Do not overwrite ongoing canonical branch
edits or ASTRA's current flagship work.

Revenue proof still requires a genuine consented commercial enquiry,
the immutable canonical EmpireDB receipt, founder-only inbox confirmation,
qualified buyer identity and eventual verified settlement/fulfilment.
GSC impressions alone do not close that loop.

No production website, sitemap, robots.txt, paid traffic, outbound email,
mainnet payments, CRM or database mutation was performed.
