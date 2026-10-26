# EmpireOS — original daily organic-search indexed-version watch

26 October 2026. No new SEO stack, DB, timer, crawling service or outbound sender.

The existing **empire-organic-search-recovery.timer** (daily midnight UTC) already invokes the original read-only organic-search-recovery.service. Its original ExecStart has concurrently owned changes and is not modified. This release adds an optional review-only ExecStartPost of the original source under /srv/empire_os/scripts/review_daily_original_google_index_20261026.py, installed as a systemd drop-in to that same service. There is no new timer or service, and the failure of Google inspection must not fail the existing original organic audit.

Evidence:
- Original cached loopback 127.0.0.1:8771/v1/search/search-console/indexed-version/fixed: five fixed owned URLs, official Google URL Inspection indexed-version, never a live test or a submission.
- Original website crawler seo_indexing_health.audit_live_indexing, exact technical crawl and owned sitemap graph.
- Original typed gsc_indexed_truth_review.review_owned_google_index_evidence validates Google/crawl evidence and marks genuine observed, Google-unknown, or review needed.
- New additive pure helper google_index_change_watch.summarize_verified_google_index computes changes between exact source-labelled original Google observations, no inferred rankings/traffic/leads or machine-generated claims.
- Dated receipts at /home/ubuntu/empire_releases/seo_daily_index_status_20261026/google-index-YYYY-MM-DD.json, private 0700 directory / exclusive 0600 files; no overwrite and at most one receipt per day. Unexpected provider failure gives SOURCE_UNAVAILABLE, counts null, no fake zeros.
- The existing six-hour cache and existing Google account are reused; ordinary daily observation may trigger up to five provider read-only indexed-version calls, not API indexing submission. A temporary API outage does not disable the original organic observer.
- Systemd drop-in deploy/systemd/empire-organic-search-recovery.daily-google-index-20261026.conf uses existing service under ubuntu with ProtectSystem strict, private ReadWritePaths, TimeoutStartSec 180 and ignore-fail ExecStartPost.
- Founder manual URL Inspection Test Live URL and Request Indexing, if needed, remain separate and require manual Google Search Console action. No automation attempts to use Google's restricted Indexing API.
- This is not a claim of improved ranking, increased clickthroughs, new backlinks, actual traffic, accepted solar referral, live outbound or verified revenue.

Activation: the staged drop-in requires original operator-controlled systemd approval via the guarded installer. It must not be installed while service is running or when another editor owns the same drop-in. No timer restart is required: systemctl daemon-reload loads an ExecStartPost for the next daily run. Before it is enabled, a read-only preview and private first-day baseline are captured.

Tests cover exact-source/ordering/age checks, transitions, previous-source custody, confidential 0700 directory, one daily immutable receipt, and unavailability. After next scheduled run, compare the current dated receipt with the previous one and only count real provider status transitions.
