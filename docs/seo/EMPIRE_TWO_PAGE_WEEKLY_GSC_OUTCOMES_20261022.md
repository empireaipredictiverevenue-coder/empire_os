# Weekly evidence monitoring — two live Jev-informed SEO pages

**22 October 2026 | EmpireOS / EmpireDB | observe only**

Monitored existing URLs:
- https://empire-ai.co.uk/predictive-revenue
- https://empire-ai.co.uk/industries/roofing

Published original changes on **22 October 2026**. The previous 30 legacy-404 URLs and their 44 sampled impressions are *research inputs*, NOT baseline traffic for these two pages.

## Original provider and schedule

Reuse authenticated existing `empire-search-intelligence-api.service` on loopback, specifically `/v1/search/search-console/status` and `/v1/search/search-console/pages`. The GSC property is `sc-domain:empire-ai.co.uk`; report MUST use exactly `dimensions: ["page"]`, `source=google_search_console`, `data_state=final`, and matching dated window. No new OAuth, scraper, credential, DB migration, paid Jev inference, visitor tracking or API privilege.

Every **Monday, 10:00 Europe/London**, produce a private summary using a **four-calendar-day data-finality lag**. On 26 October the period still mixes prepublication data; first full postpublication week is 23–29 October, whose seven-day window is eligible from **2 November 2026**. The first clean comparison of two full post-publication weekly windows is eligible from **9 November** (and only if source evidence actually contains pages for both windows). Report not comparable before then.

## Critical three-way metric taxonomy

- `POSTRELEASE_SEVEN_DAY_WINDOW_NOT_YET_FINAL` / `NOT_YET_REPORTED`: the post-release measurement window is not ready. This is not zero.
- `NO_PAGE_IN_RETURNED_GSC_ROWS`: the requested source window is final, but an inspected target URL/alias is absent from Google's returned bounded page rows. Clicks/impressions/CTR are **null**, not zero.
- `MEASURED_ZERO`: a genuine reported page row has explicitly provided *zero* clicks and *zero* impressions. This situation may be uncommon; a zero-click row with nonzero impressions is `MEASURED_PAGE_METRICS` with CTR 0.

Also treat provider outage, invalid response, insufficient fields or query/page cross-product contamination as `SOURCE_UNAVAILABLE`, never zero.

When both current and previous weeks are fully postpublication, final, and actual rows exist for the same URL, calculate week-on-week impressions and clicks and CTR percentage-point differences. Never invent traffic uplift from a missing baseline, zero impressions or an unrelated GSC window.

No buyer, enquiry, contract, settlement or revenue numbers are inserted unless actually reconciled to separately authorised, verified CRM/payment receipts (currently **not connected to this observer**). Jev analysis is optional downstream, never triggered by the weekly observer.

## How to run

For **read-only interactive report** (stdout, no new file):
```bash
cd /srv/empire_os
PYTHONPATH=. .venv/bin/python -B -m scripts.report_weekly_two_page_gsc_20261022 --as-of 2026-10-22
```

For an **immutable private weekly JSON receipt**:
```bash
cd /srv/empire_os
PYTHONPATH=. .venv/bin/python -B -m scripts.report_weekly_two_page_gsc_20261022 --write-private
```

If activated, the existing systemd scheduler owns a single `empire-seo-two-page-gsc-weekly.timer` and runs the service as ubuntu. Files appear at:
`/home/ubuntu/empire_releases/seo_weekly_gsc_two_page_20261022/weekly_two_page_YYYY-MM-DD.json`

Folder is private 0700, receipts are created with 0600 and cannot be overwritten silently. A separate repeat/notifications workflow may read these receipts; the service itself sends no email or push and does not create autonomous Jev model calls. Browser-based manual Google URL Inspection and **Request Indexing** are separate: the available Search Console API is read-only and cannot request indexing for ordinary B2B service pages. The Google Indexing API is restricted to eligible job postings/livestreams.

## Review gates

Do not equate technical indexability with inclusion in Google index, GSC final report availability with search impression, search impression with site click, site click with qualified buyer, or buyer enquiry with settled revenue. No automated publish, outbound, conversion-recognition, funds, API permission changes or spammy forced crawl/Indexing API misuse.
