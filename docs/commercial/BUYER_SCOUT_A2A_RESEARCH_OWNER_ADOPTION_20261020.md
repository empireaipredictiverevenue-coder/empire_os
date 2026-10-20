# Buyer Scout — read-only adoption of A2A public business evidence
20 October 2026. Owner checkout: /home/ubuntu/empire_worktrees/resilient_buyer_scout_business_release_996946a3

## Reason
Existing A2A first-party source collector has 9 website status packets:
7 allowed HTTP200, Scrapling and Crawl4AI parsed, 2 held.
The official Little Rock mechanical permit source supplied 40 event rows,
7 conservatively recognised contractor business-name hypotheses. Latest
permit issue date 2026-09-25, not fresh current buying demand.

The canonical Buyer Scout service did not consume A2A source evidence.
This work provides owner-side research intake without changing canonical CRM.

## Built and deployed
- empire_os/buyer_scout_a2a_research_intake_20261020.py
  Validates owner evidence schemas, observe-only authority, source hashes,
  valid public HTTPS company origins, target city/industry, duplicates,
  non-HTTP200 holds and website evidence freshness.
  Compares research domains with current Buyer Scout/public-search snapshots.
  Does NOT claim full canonical CRM or database-wide dedup.
- scripts/review_buyer_scout_a2a_source_intake_20261020.py
  Reads four current source files plus first-party freshness report and
  atomically writes a 0600 isolated owner review JSON. No network, CRM,
  model, outbound, paid APIs, login, or sending.
- ops/systemd/user/empire-buyer-scout-a2a-owner-evidence-review.service
  With private tmp, protected home, AF_UNIX only, strict filesystem, writes
  restricted to its own research runtime, dedicated owner-side review.
- ops/systemd/user/empire-buyer-scout-a2a-owner-evidence-review.timer
  Enabled and scheduled hourly at *:25 UTC with up to 3min delay.
- tests/test_buyer_scout_a2a_research_intake_20261020.py
  Validated duplicate/domain, forged buyer/contact/dispatch flag, source
  freshness and stale/nonreviewable records.

## Live evidence as of 20 Oct 2026
- 9 first-party website status packets read; 7 current for owner review.
- 7 permit-derived contractor company name hypotheses, not homeowner leads.
- 0 domain overlaps within the current rotating Scout/search snapshots.
- 0 independently verified buyer companies or explicit purchase requests.
- 0 canonical CRM lookups, changes, records accepted or outbound messages.
- 0 authenticated signed commercial owner receipts.
Owner report: runtime/buyer_acquisition/a2a_research_owner_intake_latest.json
Installed systemd owner intake: Result=success, ExecMainStatus=0.

Research packets have been accepted by the isolated owner-side REVIEW
WORKSPACE only, not by the canonical production Buyer Scout or CRM.

## General search provider / Tampa blockers
Existing Search Fabric keyless providers fail: DuckDuckGo HTTP202, Mojeek
HTTP403, Bing quality rejects. Search Fabric already implements the official
Brave API adapter behind BRAVE_API_KEY; this release has not provisioned a key.
Brave currently lists $5/1000 Search API queries, with $5 monthly credits;
signup requires a credit card. An account and budget approval are needed
before running live account-backed searches. Never store API keys in Git.

Both official Tampa City ArcGIS and business-tax site redirected this server
to the City's outside-US restriction page (HTTP307). County host timed out.
No geo-block, access control, CAPTCHA, or robot-policy bypass is authorised.
Florida DBPR advertises contractor licence record downloads, but initial
portal robots was HTTP403 and a tested guessed CSV endpoint was HTTP404.
Do not claim another source is live until legitimate access is demonstrated.

## Next canonical ownership gates
- Search Fabric owner: provision approved official provider account,
  explicit spend cap and bounded query preflight; capture source receipts.
- Canonical Buyer Scout owner: independently verify company identity,
  territory, legal source rights, buying need and capacity, canonical CRM
  duplicates and suppression, and signature of evidence owner.
- A2A identity owner: cryptographic owner issuer receipts before promotion.
- Production release owner: review/cherry-pick minimal code into maintained
  canonical mainline, with live service preflight and no dirty checkout edits.

These gates do not block observing real publicly permitted business research,
but they block claims that qualified lead buyers have been acquired.

## Verify or rollback
Run:
  cd /home/ubuntu/empire_worktrees/resilient_buyer_scout_business_release_996946a3
  PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_buyer_scout_a2a_source_intake_20261020 --read-only-owner-review --write-local

Check:
  systemctl --user show empire-buyer-scout-a2a-owner-evidence-review.service -p Result -p ExecMainStatus

Disable only this new owner review:
  systemctl --user disable --now empire-buyer-scout-a2a-owner-evidence-review.timer

Do not delete the isolated worktree while this user timer references it.
