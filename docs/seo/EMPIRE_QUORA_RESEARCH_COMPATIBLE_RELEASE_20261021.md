# Empire Search Intelligence — Quora private Founder release on Research owner base

**21 October 2026 · LIVE Search Intelligence; Founder Console candidate STAGED ONLY.**

## Owner collision reconciled
The active Founder Console changed from the older Agency-only release to the approved **Empire Research SSH-private** release during Quora's earlier preflight. The old Quora candidate is therefore superseded; its verifier rightly returns HELD. Do **not** deploy it or replace the live Research release with it.

Current active:
`/home/ubuntu/empire_releases/founder_research_ssh_private_20261021/candidate-39d028058bcd/web`

Compatible Quora candidate:
`/home/ubuntu/empire_releases/founder_quora_research_compatible_20261021/candidate-from-39d028058/web`

Candidate manifest:
`/home/ubuntu/empire_releases/founder_quora_research_compatible_20261021/candidate-from-39d028058/quora-research-compatible-manifest.json`

Manifest SHA256:
`e4d51c21497b32aeb0bd8e254bdfbabd709b1ce7de8a52f398b834482960f4d5`

New compiled build ID: `fpAMS8SsaZ6GKqeOgJBjo`.
Original Research source commit: `39d028058bcdea57637ddc5ad2a12b28b1c8abf9`.
Quora overlay source commit: `b0958a16a`.

## Proved end-to-end
- Independently verified original Research release source/build hashes from original Research owner `release-manifest.json`.
- Source diff vs live Research release is **exactly three** files: `src/app/department/page.tsx`, `src/lib/search-api.ts`, `src/app/department/quora/page.tsx`. Research executable API bridge, signed/session logic, Research page, Agency, CRM, mail, source files remain byte-identical.
- Candidate rebuilt clean after moving inherited stale `.next` output to a separate candidate-local backup; Next.js/Webpack build and TypeScript passed, including the `/founder/research`, `/founder/research/execute` and `/department/quora` routes.
- Private SSH-loopback canary: **18 GET routes HTTP 200** including Research/Agency/Quora, four hostile proxy/Host-header attempts 404, and public Quora route 404. The Research preview intentionally did not possess a real signed Founder session; it proves source rendering and no release regressions, not authenticated Research execution.
- Existing production Search Intelligence loopback on port 8771 returns 56 editor-only topics across roofing, HVAC, solar, dental, legal and B2B; Quora source questions verified=0, published answers=0.
- No live founder service restarted or systemd drop-ins changed during this build. No Quora posting, paid traffic, outbound, database, checkout, call routing or public publication.

## Safe operator check
```bash
cd /srv/empire_os
.venv/bin/python -B -m scripts.review_quora_research_compatible_release_20261021
```
Expected while Research release remains active:
`RESEARCH_COMPATIBLE_CANDIDATE_STAGED_APPROVAL_REQUIRED`.

Any concurrent owner root change or public route access changes status to `HELD_RELEASE_OR_PRIVATE_BOUNDARY_CHANGED`; owner must reconcile and rebuild from newest active release, not force release.

## Exact remaining handoff
1. Explicit founder approval for **restarting only `empire-founder-console.service`** and choosing the manifest-pinned compatible Quora release. No existing approval for unrelated services or API restarts is implied.
2. Privileged operator must verify the latest existing drop-in order, current Research service WorkingDirectory and original manifest, check local SSH auth boundary and stage exact prior-root rollback.
3. After guarded activation, require 18 private GETs 200, negative Host/forwarded/public Quora 404, `/founder/research` signed-session authentication and its existing negative public tests, plus all current founder/agency and commercial routes. If anything fails, restore exact Research release and report.
4. Quora real source discovery remains distinct: the topics are research themes, not independently verified Quora question pages. Only consented, platform-compliant editorial publishing through authorised identity; no bulk spam or affiliate routing.

**Do not rebuild** the existing Search Fabric, SEO department, Founder API, Research, Agency or EmpireDB.
