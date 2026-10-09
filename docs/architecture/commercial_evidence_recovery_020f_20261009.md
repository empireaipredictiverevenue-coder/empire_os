# Commercial Evidence Recovery 020F

## Why
A five-page commercial probe prioritised homepage navigation and generic
contact/about paths. It missed purchasing-related pages discoverable only
through a first-party sitemap.

## Upgrade
- Reuse the existing Search Fabric and Buyer Scout orchestration and timer.
- Read at most two same-domain XML sitemap files, only on root-homepage
  commercial probes with at least three HTML-page slots.
- Skip sitemap discovery if two relevant commercial links are already on
  the homepage. Prefer existing navigation, then at most two sitemap-backed
  buying-page candidates, then the normal contact/about fallbacks.
- Keep the existing five-page HTML crawl limit and deadline. Reject
  third-party URLs and cross-domain redirects.
- A sitemap path is a discovery clue, not purchasing evidence. Only text
  fetched from actual first-party pages enters the purchasing classifier.
- Record discovery and actual fetched-page counts separately in Scout and
  the existing evidence-quality scorecard. No new agents or timers.

## Safety and acceptance
Regression covers hidden buyer pages, nested XML, external URLs, ambiguous
commercial wording, missing buying statements, existing nav priorities,
public-only mode, Buyer Review and Outbound Governor.
No DB schema change, credential dependency, outbound send or approval gate.

## Operational limitations
More discovered page paths do not prove buyer intent, a named person's
email ownership, budget or delivery. The current crawler's public-only
flag is not a complete robots.txt policy implementation; a separate
crawl-compliance review is still required before expanding crawl volume.
Real website probes are read-only and are not proof of commercial revenue.
