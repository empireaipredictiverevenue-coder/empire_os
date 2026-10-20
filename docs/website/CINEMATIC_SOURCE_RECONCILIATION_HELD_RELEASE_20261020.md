# ASTRA cinematic flagship — isolated source reconciliation (20 October 2026)

Status: **SOURCE COMPILES; PUBLIC RELEASE HELD**. No live website or payment/call gate files were written by this source reconcile.

Worktree: /home/ubuntu/empire_worktrees/flagship_current_cinematic_source_guard_20261020
Branch: feature/flagship-current-cinematic-source-guard-20261020
Source baseline: 722b4e4d on agent/data-cloud-wave4
Current approved live homepage: https://empire-ai.co.uk/
Live HTML SHA-256: 0e63856577b9894ebc62d3715f95cb96e788c4caf9c0e45c382e14bb5cbecf1c

### Problem resolved in isolated source

Mainline source page.tsx previously imported EmpireWorld, even though the approved live
homepage HTML already served CinematicExperience from ASTRA's separate flagship
worktree. An unrelated full-site export of mainline therefore risks
reverting the live first paint to the old theme.

This isolated worktree copies only missing ASTRA modules, source assets, and
the affected page/layout/global styling from the reviewed
flagship_final_creative_20261018 owner workspace. The existing checkout,
roofing, sector, prospect and commercial route source files were **not**
overwritten. The candidate builds successfully with Next.js 16 Webpack and
TypeScript, with 19 static route files generated; independent release-guard
unit tests pass.

### Why publication is still held

The isolated build generates different HTML bytes from the already-approved
live pages in all these protected paths:

- index.html
- roofing.html
- industries/roofing.html
- industries/solar.html
- buy.html
- commercial.html
- predictive-revenue.html
- trust.html

This does NOT imply every difference is an error. It does mean that copying
the candidate full export to production would overwrite buyer-reviewed
or brand-reviewed live pages and must not happen without independent
page-by-page comparison and approval.

Run:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_flagship_cinematic_source_release_20261020

The review script is read-only and will exit code 2 until independently
approved live bytes are reconciled. A working static export is not a
publication receipt.

### Next website-owner actions

1. Review ASTRA's new source branch, current production build receipt, and
   newer changes on the shared mainline (multiple owners are active).
2. Preserve exact approved live consumer ZIP/recording consent, approved
   roofing and solar imagery, checkout HTML integrity and CRM routes.
3. Resolve the 8 protected-page deltas independently before publishing
   another full site build. Do not force-push or reset active worktrees.
4. Add the founder's labelled first-party roofing CTA to the
   CinematicExperience source if design-approved; do not port it from the
   old EmpireWorld homepage. The live /industries/roofing contextual link
   remains available today.

### Business scope

Two contact enquiries were sent to Roofing Mate and Roofing Calculators
through existing founder Gmail drafts and show SENT status. RoofPitch's
previous reply was paid editorial only, so no duplicate send. Lead Smart's
call admissions remain live under first-party organic provenance only.
No verified site handoffs, payable calls or settlement receipts at the last
read; no third-party traffic links were enabled.
