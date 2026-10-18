# Founder Console — Incremental private SEO department release
18 October 2026 | Existing service only | £0 spend | Source and immutable build

## Release state
STAGED — NOT LIVE. The canonical Search Intelligence backend on
127.0.0.1:8771 is active and returns 200 for GET
/v1/search/department/review, with GSC and Search Fabric first-party
aggregates, independent SERP rank false and realised revenue false.
The live Founder Console on localhost:3001 remains in the **commercial
loop + historical mailbox** frozen release until a separate founder
approval is given.

## Critical concurrent-owner reconciliation
An initial candidate was based on the 90 historical-mailbox release.
Before its preflight finished, a separate owner activated the 95
commercial-loop release and changed WorkingDirectory to:
  /opt/empire-ai/founder-console-releases/bridge-sources-history-75912015

Our original preflight correctly failed
HOLD_ACTIVE_OWNER_RELEASE_CHANGED. The old candidate was NOT deployed.

The replacement SEO candidate is based byte-for-byte on the **currently
active** frozen 95 commercial-loop release:
  /home/ubuntu/empire_worktrees/empire_founder_seo_department_bridge_candidate_20261018

The source parity check confirms precisely TWO existing source files
modified (src/app/page.tsx, src/lib/search-api.ts) and ONE new file
(src/app/department/page.tsx). All founder, mail, historical evidence,
CRM, YouTube, commercial pipeline, analytics and other existing routes
are unchanged, including the active commercial-loop changes.

## Verified incremental build
- Next.js 16.3.5 webpack production build passed, with TypeScript pass.
- New /department is dynamic SSR, not a static snapshot; noindex.
- On a disposable server listening 127.0.0.1:3197:
  10/10 GET routes returned 200 (nine previously available routes
  plus /department, including /founder/commercial-pipeline).
- Chromium mobile 390px and desktop 1440px passed expected GSC/404/
  Search Fabric evidence, held-ranking claims, noindex, navigation,
  no horizontal overflow, no browser POST or external requests.
- Search Intelligence API already returns live evidence; the Next
  candidate uses only server-side
  EMPIRE_SEARCH_API_BASE_URL=http://127.0.0.1:8771.
- The browser test was corrected for CSS-transformed uppercase text;
  the UI itself was not missing a metric.
- Public https://empire-ai.co.uk/department and matching public
  /v1/search/department/review both remain HTTP 404; the local-only
  founder console's existing eight/nine routes were not exposed.
- Existing active systemd unit and prior drop-in files were untouched.

## New one-time private-only release operator
  cd /srv/empire_os
  bash scripts/deploy_private_founder_seo_department_20261018.sh --preflight

The source-bound preflight requires all of:
  * The precise active 95 commercial-loop frozen release and exact prior
    70+80+90+95 systemd drop-in stack.
  * Current founder service healthy and still bound to 127.0.0.1:3001.
  * Every existing private founder route HTTP 200.
  * New SEO route missing from active frontend (HTTP 404).
  * Existing private SEO API GET returns exact OBSERVE schema, and no
    verified ranks or revenues.
  * Public apex paths HTTP 404 with browser UA.
  * All source files unchanged except expected 3 SEO additions, which
    must match the canonical EmpireOS sources exactly.
  * Pinned production compiled Next.js BUILD_ID, SEO page, homepage,
    founder Mail and commercial pipeline build files unchanged.
  * No existing 96-private-seo-department-release.conf drop-in.

Only after **separate explicit founder approval** for this exact private
frontend release can the operator use:
  sudo bash scripts/deploy_private_founder_seo_department_20261018.sh --apply-founder-approved-private-seo-release

This writes ONE new 96-private-seo-department-release.conf drop-in for
the existing empire-founder-console.service, preserving the prior
commercial-loop 95 override for rollback. It sets WorkingDirectory to
the verified immutable SEO candidate and only the server-side
EMPIRE_SEARCH_API_BASE_URL. It restarts ONLY that existing founder
console service. On any post-release verification failure it removes
only the 96 drop-in and restarts the prior service; on success it emits
the exact rollback command. It does not touch Search Intelligence,
CRM, the database, Cloudflare, public pages or content publishing.

## Remaining identity/deployment limitations
- The original existing founder console is private by LOOPBACK/PUBLIC
  404 separation. Independent application-level founder identity
  enforcement for the SEO page has not been verified. Do not describe
  the aggregate view as authenticated or publish it through the public
  site; integrating with owner-authenticated access remains future work.
- No Google ranking, AI citation, organic buyer conversation or
  realised revenue is certified by this release. Cached SERP envelopes
  are diagnostics only, not live Google rankings.
- Do not run the script if another release owner changes the working
  directory, adds a drop-in, rebuilds frozen binaries or the public
  access perimeter changes; the preflight must fail closed.
