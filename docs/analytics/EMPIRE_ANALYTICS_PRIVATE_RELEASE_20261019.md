# Empire Analytics — private, rollback-safe visual release
19 October 2026 | Current Founder Console only | NO public publishing

## Baseline and candidate
Live existing service:
  empire-founder-console.service
  127.0.0.1:3001
  /home/ubuntu/empire_worktrees/empire_founder_gsc_trends_commercial_v2_candidate_20261019

Prepared immutable candidate:
  /home/ubuntu/empire_worktrees/empire_analytics_platform_branded_candidate_20261019

The new candidate was byte-for-byte copied from the live source except
the two modified page files (src/app/department/page.tsx and
src/app/page.tsx), two added evidence/analytics styles files
(src/app/department/evidence/page.tsx and src/app/department/analytics.module.css)
and the published-brand logo PNG under public/brand. All Founder Mail,
commercial operations, CRM and YouTube source was preserved.

## Verified functionality
- Next.js 16.3.5 production webpack build and TypeScript pass.
- All 10 existing private routes and new /department/evidence passed
  HTTP 200 on a disposable 127.0.0.1:3197 preview.
- Chromium at 390/768/1440 tested Empire AI branding, source-verified
  GSC metrics, bar/click graph, first-party provenance, 404 category
  analysis, visitor/conversion/revenue missing-evidence truth,
  client-side no-write behavior, noindex, no horizontal overflow.
- Legacy original /department review remains at /department/evidence;
  archived review regression tests passed.
- New logo is copied from the currently published Empire AI public
  website asset, with SHA256 matched. Founder visual review may choose
  a newer approved globe-mark asset through a separate update.
- Running Search Intelligence/EmpireDB unchanged, £0 spend,
  no new tracking or advertising integrations.

## Source and release preflight (no service changes)
  cd /srv/empire_os
  ./.venv/bin/python -m scripts.review_empire_analytics_private_release_20261019 --read-only
  bash scripts/deploy_private_empire_analytics_20261019.sh --preflight

Expected when source and current owner still match:
  FROZEN_BRANDED_ANALYTICS_READY_FOR_FOUNDER_RELEASE
  EMPIRE_ANALYTICS_PRIVATE_PREFLIGHT_PASS
  EMPIRE_ANALYTICS_STAGED_NOT_DEPLOYED

Checks exact frozen build SHA256, verified published logo, source diffs,
seven active systemd drop-ins 70-98 and exact owner WorkingDirectory,
all existing ten routes, new public /department/evidence 404,
existing public /department and /v1/search/department/review 404,
and the first-party GSC daily source contract.

## Privileged activation (needs founder approval)
  sudo bash scripts/deploy_private_empire_analytics_20261019.sh --apply-founder-approved-private-analytics-v1

Activation adds ONLY
/etc/systemd/system/empire-founder-console.service.d/99-private-empire-analytics-release.conf
with an exact WorkingDirectory. It restarts ONLY the existing Founder
Console service; no Search Intelligence service or website mutation.

On post-release failure the operator removes only the 99 drop-in and
attempts to restart the original chart-enabled console.

Manual authorised rollback:
  sudo rm -f /etc/systemd/system/empire-founder-console.service.d/99-private-empire-analytics-release.conf
  sudo systemctl daemon-reload
  sudo systemctl restart empire-founder-console.service

On success check 11 private routes, the branded server-rendered charts,
old evidence view, Search Intelligence health and three public 404 paths.

## Remaining data work
The current data is first-party GSC, SEO and search cache evidence. No
genuine site users/sessions, engagement, attribution, GA4 reports or
realised revenue joins are available from this module. The next phase
must reuse Tag Intelligence, comply with consent requirements and
connect canonical CRM/payment receipts. Never pretend GSC impressions
are web visitors; do not expose the loopback-only console publicly or
describe it as independently founder-authenticated.
