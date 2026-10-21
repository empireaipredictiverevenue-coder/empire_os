# Empire Search / Quora — Founder Console private release candidate
Observed 21 October 2026. **Staged, not activated.** Canonical EmpireDB, no Supabase.

## What has actually been built
- Existing production Search Intelligence API (127.0.0.1:8771) serves 56 read-only question themes across roofing, HVAC, solar, dental, legal and B2B, with no actual Quora question URLs or published answers claimed.
- Source commit `c18b44e55` protects the `/department/quora` page behind the current private Founder Console SSH/loopback ingress pattern. This checks forwarded-host/IP and hostile proxy headers and requires `EMPIRE_PRIVATE_FOUNDER_INGRESS_REVIEWED=1`. Such ingress checks do **not** independently prove application-level session identity.
- Active Founder release was independently hash-verified using its own pinned original manifest, then copied verbatim into a **separate** new immutable candidate. Original Agency/CRM/commercial/Founder source remains byte-for-byte unchanged.

## Exact release paths
- Active original: `/home/ubuntu/empire_releases/founder_agency_private_console_20261020/releases/65ab711f28ae4eed9227eea2d8803f273b543ce3`
- New stage: `/home/ubuntu/empire_releases/founder_quora_private_console_20261021/candidate-from-65ab711f`
- Staged release manifest: `candidate-from-65ab711f/quora-release-manifest.json`
- New manifest SHA256: `25700774cdca63e4b9e015cdd875277abd774c27f282e4cb0d33b2c54761458d`
- Candidate build ID: `jcJ5sy4XU3rv8whW4YD7_`
- Exactly three source changes vs original release: `src/app/department/page.tsx`, `src/app/department/quora/page.tsx`, `src/lib/search-api.ts`.

## Independent end-to-end preflight results
- Webpack/TypeScript production build passed, all existing 24 generated routes compiled.
- SSH-private preview at `127.0.0.1:3109`: 17/17 sampled existing + new Founder pages HTTP 200, including `/founder/agency` with its explicitly permitted preview port and genuine existing checks.
- Four hostile proxy/Host-header tests returned HTTP 404 on `/department/quora`.
- Public `https://empire-ai.co.uk/department/quora` and search Quora endpoint returned HTTP 404.
- Existing frozen Founder service still active from the original Agency release. Real Lead Smart call admission remains OFF.
- `python -B -m scripts.review_quora_founder_release_20261021` returns `IMMUTABLE_PRIVATE_CANDIDATE_VERIFIED_RESTART_APPROVAL_REQUIRED` when no active release drift. The verifier checks all pinned hashes, exact source path scope, 56-topic API, active service root and negative public boundaries.

## What remains before deployment
- Obtain **explicit founder approval** for the exact existing Founder Console service restart/change to this immutable candidate. Do not infer restart approval from general permission to continue development.
- Original founder application-level identity remains unproven in the existing release; SSH/private ingress is the currently enforced boundary. Owner must determine whether this is sufficient for read-only non-identifying Quora research or require a stronger signed session before release.
- Before applying a systemd drop-in, privileged operator must recheck active WorkingDirectory, full drop-in ownership, current production root and current manifest; stage rollback to exact prior root and restart only the Founder Console, with negative public tests and existing route checks. **No apply has been executed.**
- Search Fabric still lacks independent genuine Quora question-origin evidence. Quora themes cannot be promoted into verified discussions, referral sessions or revenue without independent source and authorised account review.

Do not rebuild Search Fabric, Search Command Centre, publishing pipeline, Founder API, CRM or EmpireDB.
