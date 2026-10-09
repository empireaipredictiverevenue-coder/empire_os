# Buyer Evidence Quality 020E

The existing Buyer Review Materializer now creates a read-only aggregate
scorecard in runtime/buyer_acquisition/evidence_quality_latest.json.

Scout counts describe one discovery run. Pending Buyer Review counts describe
a separate accumulated holding queue, not a conversion rate for that run.

Published emails and named people are observations, not verified person-email
bindings. Buying statements require a valid dated first-party purchase receipt.
A source page receipt by itself does not prove purchasing.

Snapshots must be fresh and aligned to be interpreted together.
No new timer, external action, outbound permission or database migration.
Reporting errors are logged but cannot grant commercial authority.

Run regression tests in tests/test_buyer_evidence_quality_scorecard.py.
