# OpenMontage reintegration — canonical Empire Media OS
Date: 2026-10-17. Scope: existing Media OS, no independent platform.

## Implemented in existing production checkout source
- `empire_os/media_renderer.py`: provider `openmontage` and `review_openmontage_edit()`. Accepts existing `empire.media.timeline.v1` only, checks contiguous scenes, data provenance, selected pipeline, AGPL-3.0 licence review, source rights, explicit zero paid providers and existing render-cost governor. Declares `execution_authority=none`.
- `empire_os/agents/video_editing_agent.py`: historical agent is read-only compatibility. Deleted unsafe `shell=True` and fictitious `render_demo.py --pipeline` integration. No auto self-demo, no independent job queue, no scripts or external API calls.
- `tests/test_media_production_contracts.py`: source gating, review, blocked pipelines, denied public release, retired execution path.
- No site, gateway, systemd, DB, customer data, infrastructure, or publishing modified. All other agents' pending work preserved.

## Source verification
OpenMontage upstream https://github.com/calesthio/OpenMontage
Inspected source commit `c8066452325cb57c8fc1ba8c2a71b6e8842e6b65`, cloned only for read-only inspection at `/tmp/empire-openmontage-source-review-20261017`. `render_demo.py` supports named demo fixtures only; old `--pipeline/--brief` commands would fail. OpenMontage itself includes a HyperFrames compositor, but Empire's existing HyperFrames and FFmpeg remain the preferred local compositors.

Allowed editorial manifests: clip-factory, documentary-montage, talking-head, screen-demo, hybrid. More GPU-heavy `avatar-spokesperson` deliberately excluded until funded.

The licence is GNU AGPLv3. The integration references upstream manifests; no upstream AGPL code is copied into proprietary EmpireOS. Commercial deployment / network-service licence implications need review before enabling execution. OpenMontage upstream pipeline may select third-party hosted generation or paid APIs; there is **no** implicit cost permission. Human-verified source rights required for video and audio.

## Tests and activation truth
- Active `/srv/empire_os`: `python -m pytest -q tests/test_media_production_contracts.py` -> 9 passed.
- Isolated previously existing media worktree: `python -m pytest -q tests/test_media_production_contracts.py tests/test_media_hyperframes_bridge.py` -> 15 passed.
- Upstream `clip-factory` manifest inspection found matching real YAML; review held on licence, rights and paid-provider exclusions, `render_executed=false`.
- No standalone OpenMontage daemon was installed, no nightly auto render. No new video made or published by this reintegration. Existing YouTube publication controls still apply.

## Single-stack usage
`build_media_timeline(...)` -> `review_openmontage_edit(timeline, pipeline="clip-factory", ...)` -> existing Media OS rights/QC/founder approval -> **future independently reviewed execution mechanism** -> Media OS outputs.

Next legitimate test: source-rights-approved 30-second sample from existing Empire-owned documentary, local FFmpeg/HyperFrames only. Do not label the existing review function a renderer; the runtime bridge remains inactive pending licensing/cost/rights review and explicit approval.
