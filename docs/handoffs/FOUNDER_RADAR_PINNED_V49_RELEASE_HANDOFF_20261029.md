# Original Founder Read API owner — pinned Radar compatibility release (29 October 2026)

**State: TESTED AND STAGED — NOT LIVE.** Founder instructed us to correct Radar and then verify lifecycle, one after the other. This is an existing-owner deployment handoff, not an independent release authorisation, new service, or new app.

## Exact existing live baseline
- Unit: `empire-founder-dashboard-api.service`, loopback `127.0.0.1:8766`, running pinned overlay `predictive_cloud_v49_existing_api_overlay_20261025:app` since 25 October.
- Prior pinned overlay SHA-256: `ba6aad410ec626410e8c50c5ce783535eb9324c156898df93e8f5bcb10fd4c76`.
- Real live GET `/health`: HTTP 200, read-only. GET `/v1/founder-dashboard/overview`: HTTP 200 but `opportunity_radar.available=false`, missing `lifecycle_evidence`. The live pinned app reads obsolete release-local runtime instead of the current canonical `/srv/empire_os/runtime`.
- A fresh in-memory import of the original pinned API **also** returns Radar unavailable; blind service restart does not fix it.
- Canonical `empire_os.founder_dashboard._opportunity_radar_runtime` already returns OBSERVE-only, current source-bound Radar and full verified lifecycle, with zero commercial/send authority.

## Scoped candidate and tests
- Additive application wrapper: `scripts/founder_radar_pinned_v49_compat_20261029.py`, SHA-256 `63ab2e7ff2f112602b59ba481ad0780aa8431d8878fe011b2c779be826d754ec`.
- Exact service override **candidate only**: `scripts/empire-founder-dashboard-api-radar-20261029.conf`, SHA-256 `7fe9da3c93b4e7f294e6debf5837b18cc641250bd19b56792530179063653166`. Focused test file SHA-256 `e1c495296d81903fb023db8990cd9dd1233cc33e2624710c804ddba911f87e31`. Its final target is a root-sealed copy under `/opt/empire-ai/founder-read-releases/radar-v1-20261029`. Never run the live service directly from user-writable `/srv/empire_os/scripts` or this source worktree.
- Focused tests: `tests/test_founder_radar_pinned_v49_compat_20261029.py`; combined with `tests/test_founder_radar_evidence_surface.py`, `tests/test_completion_runtime_evidence.py`, `tests/test_founder_dashboard_service_routes.py`: **68 passed** on the host (one dependency deprecation warning, no failures).
- Wrapper reuses the **existing pinned V4.9 FastAPI app** and changes only the JSON `opportunity_radar` field of `GET /v1/founder-dashboard/overview`. All other routes remain on the pinned app. Incompatible, stale, future or untrusted canonical source keeps the prior unavailable response. The preview preserves original top-level dashboard keys, refuses external execution and does not create routes, payments, sending or trading authority. Outsize responses are streamed unchanged.

## Original-owner protected release procedure
1. **Independent preflight:** inspect exact diffs and SHAs of all three candidate files, compare current `systemctl cat`, current route inventory, health/JSON status and all active drop-ins. Ensure no other owner's release is in progress. Preserve the V4.9 service configuration and a root-owned rollback receipt.
2. **Seal:** original protected root release process creates `/opt/empire-ai/founder-read-releases/radar-v1-20261029`, copies only the reviewed wrapper there and verifies its exact SHA-256; directory/file and all parents must be safe and non-writable by an unprivileged owner. Reject symlinks, SHA drift and unapproved import changes. Python imports remain pinned to the existing V4.9 overlay; do not replace its source or old property/JEV/CRM routes.
3. **Activate through original owner controls:** install the reviewed override as root-owned `/etc/systemd/system/empire-founder-dashboard-api.service.d/zzzzzzzzzzzz-founder-radar-20261029.conf`, verify the last override wins over `zzzzzzzzzzz-predictive-v49-20261025.conf`, then owner-controlled `systemctl daemon-reload` and `systemctl restart empire-founder-dashboard-api.service`. No privilege escalation from this handoff.
4. **Prove live:** health 200; unchanged route inventory and existing V4.9 shadow-readiness 200; live founder overview 200 with canonical Radar `available=true`, verified lifecycle `CURRENT_DERIVED_HISTORY_OBSERVED` and `execution_authority=none`; check GET/POST boundaries, no external actions, actual timestamp and source freshness. Capture source, unit and source-hash receipts. **Radar first, lifecycle second, both from one atomic and protected release.**
5. **Rollback on any failed gate:** original root owner removes **only** the new Radar override, confirms the prior override SHA and V4.9 target, daemon-reloads/restarts, then independently checks the old health/route inventory. Keep the failure receipt; never advertise the candidate as LIVE. Do not touch unrelated drop-ins.

## Outstanding business blockers after this code-only candidate
- Founder Console Radar is still **not released** until the actual root owner publication/readback succeeds.
- Two model-provider holds: Sensor Mesh domain completion and queue→route→lease→worker→verify tracing. Failed model evidence requires a real available provider or independently reviewed deterministic implementation; do not forge output.
- Two founder gates: bounded safe internal task advancement and only those production actions whose original gate is evidenced. Founder's broad continuation approval does not automatically lift money/outbound/trading/production release safeguards.
- Astra workstream ranking and Daily Results were **runtime observed**, but their checklist formal closures are separate from this Radar API change.
- Business-wide: buyer capacity still zero, 154+ identity-ready prospects not equal saleable leads; no verified settlement/revenue. Current completion monitor tracks 286 pending and seven immediate attention items. Continue using the existing master register.

No production service, unit, credential, queue, DB, live payment, outreach or trading change was performed in this handoff.
