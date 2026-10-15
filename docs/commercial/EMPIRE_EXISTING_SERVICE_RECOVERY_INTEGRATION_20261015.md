# EmpireOS — Existing-service integration fixes (no new server)

**Date:** 15 October 2026. **Repo:** /srv/empire_os.
**Authority:** Existing department-cycle and Media OS service owners only.
No new server, container, timer, DB, agent, paid dependency, credentials,
outbound, customer distribution, or payment authority.

## 1. Campaign runtime promotion: remove false cross-lane dependency

The live Campaign observer already reported valid `VERIFIED_RUNTIME`
proof for 7 target controls, including `evidence_lineage`. The
canonical Campaign lane had an EXISTING `evidence_lineage` slot in
`UNVERIFIED` status. The old promotion script insisted on cloning a
VERIFIED `conversations_replies` row to promote a Campaign control,
which failed because that unrelated lane has no verified
`evidence_lineage` template. This was an incorrect cross-lane
dependency, not evidence that Campaign lacked an existing slot.

Updated `scripts/promote_campaign_runtime_bindings.py`:
- Keep `validate_control_proof` (lane OBSERVE, fresh timestamp,
  exactly allowed controls and no outbound/write authority).
- Require an EXISTING, unambiguous canonical same-lane Campaign
  control for every target; fail closed if missing.
- Copy only that SAME-LANE slot, rebind existing observer artifact
  paths/matched keys, retain previous confidence without inflating
  to a manufactured 0.90/HIGH score.
- Preserve canonical writer lock, expected-byte CAS and
  audit change-history already owned by runtime control plane.
- No conversation lane mutation, no new control, no external
  identity, no permission to send mail, no customer distribution.
- A fresh department-cycle execution will use this code; no
  service activation/restart is part of deployment.

## 2. Media OS preflight: bounded zero-spend provider deferral

Prior Media OS failed during its existing `ExecStartPre`
`refresh_media_claim_verification.py` task:
OpenCode free-tier provider returned HTTP 403; North-mini free
provider returned repeated HTTP 429 and entered an accumulated
provider backoff longer than the 300-second service start budget.

The EXISTING Media OS preflight now calls the existing
`refresh_media_claim_verification` function with
`defer_model_inference=True` by DEFAULT.
This preserves source metadata, previously verified unchanged packs
and unresolved work items, and writes its normal existing runtime
research status. It starts **no external model router**, no
inference, and no network source probes in the defer branch.
It cannot promote unreviewed search observations to verified
claims, scripts or public publication. An explicitly separate
manually initiated model-inference run can be assessed under
founder provider / model rights governance later. No model
weights or fallback claims are invented.

The service remains the existing `empire-media-os.service`;
no systemd unit file changes or new worker. Its normal refresh
workflow is not equivalent to approved public video publishing.

## Verification and governance

- Disposable real Campaign control fixture tests prove that
  missing observer proof and missing same-lane Campaign slots
  fail without a canonical write; no synthetic confidence
  promotion, cross-lane mutations or outbound authority.
- The original old Campaign test fixture was updated to use
  the current observer proof contract (lane, mode, generated_at,
  authority flags) rather than stale incomplete metadata.
- Media tests deliberately inject a model constructor and source
  probe that throw if either is called. In defer mode neither
  executes and the pending pack remains outstanding.
- Neither fix changes existing production database or
  systemd service files.
- An existing systemd timer/cycle may later materialize the
  Campaign same-lane binding update; that is an OBSERVE
  canonical runtime control proof update, not a customer action.
- Engineering completion is NOT equivalent to live healthy
  service proof. Observe the next full department cycle and Media
  OS systemd result before marking services recovered.

## Next

1. Read-only verify whether existing systemd service cycles
   completed after this code revision; identify independent
   ExecStartPost failures if any.
2. Verify new Founder Ops infrastructure health field appears
   in existing `/v1/founder-ops/status` after Ops Control timer.
3. Investigate existing pgBackRest backup recoverability and
   restore proof; no second-server purchase.
