# Empire Analytics private release: false-negative rendered heading check

19 October 2026 — Controlled release fix and proof

## Incident / scope
The founder approved and ran the exact private-only release command
scripts/deploy_private_empire_analytics_20261019.sh
--apply-founder-approved-private-analytics-v1.

Source/build/owner preflight passed, but its post-deployment raw-HTML
substring assertion expected "analytics command centre" to appear as
contiguous lowercase source text. The actual correct React heading
renders as:

    <h1>Analytics <span>Command Centre</span></h1>

When the HTML is parsed correctly the H1 has text pieces
["Analytics ", "Command Centre"]. The original implementation searched
HTML source and failed despite the visible correct heading. The
script then raised BRANDED_METRICS_NOT_RENDERED, deleted only the
99-private-empire-analytics-release.conf override and restarted the
previous Founder Console.

An independent audit confirmed:
- empire-founder-console.service ACTIVE, original
  empire_founder_gsc_trends_commercial_v2_candidate_20261019 live;
- 99 private analytics override ABSENT after the trap;
- existing private Founder Console routes HTTP 200, old evidence present;
- Search Intelligence read-only SEO department endpoint HTTP 200;
- public /department still HTTP 404.
The first check made no database, buyer, financial, marketing or public
website changes.

## Fix
- New bounded, strictly server-side Python HTML parser:
  scripts/verify_private_empire_analytics_html_20261019.py
- The deployment now calls that parser with the live localhost
  /department HTML on stdin instead of searching raw HTML strings.
- Checks semantically visible H1 including nested styling markup,
  real Empire AI brand image, actual observed-GSC section, click SVG,
  accessible evidence-view link, Search Console labels, explicit
  unknown visitors/revenue text, and noindex/nofollow meta.
- Skips Next.js hydration scripts/styles so injected JSON tokens cannot
  make a missing visible metric appear present. Rejects both source
  unavailable fallback states.
- Preserves every original preflight, pinned-build hash, origin check,
  route verification, public HTTP 404 test, and systemd rollback trap.
  It does NOT weaken the active-owner guard or allow a new public path.
- Unit tests include the actual nested-heading failure mode,
  HTML-entity normalisation, expected missing evidence, faked
  hydration text, unknown old dashboard, size cap and fallback states.

## Verified
- Semantic parser returned
  EMPIRE_ANALYTICS_BRANDED_RENDER_VERIFIED on the original
  exact frozen preview HTML (85,326 bytes).
- The same validator correctly rejected the old currently active
  non-branded dashboard.
- 52 Python tests passed in the isolated feature worktree.
- Preflight on real production still returned
  FROZEN_BRANDED_ANALYTICS_READY_FOR_FOUNDER_RELEASE.
- A new disposable 127.0.0.1:3197 Next.js session tested both
  post-release HTML verifications end-to-end: the branded page
  validator succeeded, the archived SEO raw assertion succeeded,
  and all tested current founder/commercial/SEO routes returned 200.
- The previously compiled/pinned branded Next.js candidate did not
  need a rebuild or modification. No service restart, site change,
  tracking activation or DB write was carried out to fix the script.

## Re-run only if the preflight still confirms exact owner and hashes

    cd /srv/empire_os
    bash scripts/deploy_private_empire_analytics_20261019.sh --preflight

Then, subject to the prior specific founder approval for this exact
private-only release:

    sudo bash scripts/deploy_private_empire_analytics_20261019.sh \
       --apply-founder-approved-private-analytics-v1

Expected:
    EMPIRE_ANALYTICS_BRANDED_RENDER_VERIFIED
    EMPIRE_ANALYTICS_PRIVATE_RELEASE_VERIFIED

The newly added 99 overlay remains exclusively created by this
operator; the previous 98 GSC-chart release is preserved as rollback.
No public access, independent founder auth, GA4 visitor tracking or
confirmed buyer/revenue attribution is implied by a successful release.
