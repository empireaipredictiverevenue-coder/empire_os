# Lead Smart — launch closure and production truth, 12 October 2026

This is the authoritative continuation of the existing unified release; do not reopen completed buyer visual approval, founder scope approval or ZIP refresh.

## Completed and verified
- Existing first-party EmpireOS public gateway production merge deployed from a hash-preconditioned, rollback-capable surgical stage. Older conflicting operating-hours helper and readiness tests reconciled. 108 targeted production tests passed. Gateway restarted once successfully, with independent origin status checks. No gateway commercial pages removed.
- New `POST /roofing/pilot-handoff` is installed; it currently returns HTTP 503 with no `tel:` link because traffic is not admitted. The atomic site-handoff limiter enforces five **site handoffs**, not an upstream cap on a manually redialled telephone number. Actual supervised pilot control has not been activated.
- Exact source SHA256 of approved roofing page, both copies: `faea59c0d8c6d510db8af876a53af439eac41e294f8d348e20576c75bd43cccb`. Source and 37 associated static assets deployed as a surgical change; whole-site build was not substituted for unrelated commercial pages. Local `GET /roofing` 200 and public edge 200 with buyer-approved title, noindex, no open `tel:`. All six referenced JavaScript chunks tested HTTP 200 both at local origin and public edge. Rollback backup: `/var/tmp/lead_smart_approved_page_backup_20261012`.
- Fresh producer coverage observed 11 Oct 23:03:38 UTC, 27,100 ZIPs. Three production coverage artifacts independently SHA-verified against candidate and backed up `/var/tmp/lead_smart_coverage_pre_refresh_20261011`. Production ZIP API returns `GUIDANCE_ONLY`.
- Buyer visual approval `gmail:1a12bc009d04fcc9` tied to exact frozen source in production `empire_os/buyer_supply_policy.py`; hash-checked single-hunk correction from older unapproved policy, backup `/var/tmp/lead_smart_buyer_policy_before_20261012.py`. Founder scope approval record now in production `docs/evidence/lead_smart_founder_launch_intent_20261011.json`.
- `scripts.materialize_lead_smart_launch_readiness` refreshed the existing production readiness report; founder scope, buyer page and ZIP targeting are passing. Mode **PREACTIVATION**, authority **NONE**, call CTA false.

## Factual external/provider update
- Prior buyer `gmail:1a12d06897ca9ac3` said Seth completed an end-to-end test.
- Our follow-up `gmail:1a12d433f1994a00` requested exact enabled buyer route/ANI and recording terms.
- Reply `gmail:1a12d44d7e2f46a8` confirmed **recording enabled** and **test ended before connection, with no recording**. This retracts the implication that a completed buyer leg was independently evidenced. The affiliate reporting view is insufficient to inspect restricted buyer CallRoutes.
- Follow-up `gmail:1a12d47934923a1d` requested a buyer-admin **configuration** attestation of enabled Direct target/ANI plus disabling recordings for five-call pilot, or real notice/consent/retention/owner arrangements. Do not send another identical query while awaiting the answer.
- Official Ringba Recording FAQ (updated 9 April 2026) states recording retention is indefinite while the account remains open, and individual access via shared recording URLs is not tracked: https://support.ringba.com/hc/en-us/articles/29804960197527-Call-Recording . Account-specific retention and legal responsibilities still require confirmation.

## Legal
- Existing full-site `/privacy` and `/terms` route return 404 with noindex, because existing exported documents contain draft/review markers and no exact-content legal release receipt exists. Do **not** treat founder general launch approval as exact legal text approval.
- Proposed source-grounded full-site notices prepared as `docs/LEAD_SMART_PRIVACY_POLICY_FINAL_REVIEW_20261012.md` and `docs/LEAD_SMART_TERMS_FINAL_REVIEW_20261012.md`. Incorporate confirmed sole-trader business, Bolton contact address, verified incoming `founder@empire-ai.co.uk` forwarding test, buyer recording confirmation, and Ringba's retention FAQ. They expressly remain review copies and are **not** enacted policies. Verify the trader's full legal name and data-controller, provider transfer/data-retention/recording details before final approval.
- ICO transparency guidance: https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/the-right-to-be-informed/what-privacy-information-should-we-provide/

## Remaining live gates: do not re-litigate completed work
1. Buyer admin supplies the enabled Direct buyer destination and original ANI configuration plus an actual recording choice and caller notice/retention/deletion arrangements. The last 'test' did not connect to a buyer.
2. Final exact legal/owner notices receive qualified/founder signoff, exact exported SHA release receipt, and site verification. Until then do not expose a recorded-call route to homeowners.
3. Refresh authenticated Ringba number/route evidence through authorised provider reader (no protected-secret bypass), establish a monitored 10:00–12:00 America/Chicago weekday pilot with actual stop ownership, and only then authorise restricted call CTA/indexation through the existing release controls.

No paid traffic, RTB expansion, fabricated acceptance, revenue recognition, extra caller tests, or unsafe recording claims. The commercial objective remains the first genuine accepted and settled payable inbound call.

## 12 Oct 2026 09:35 BST continuation: launch gate is now request-scoped

The previous materialized `launch_readiness/latest.json` is a historical report, **not a per-call authority token**. The live `call_available` and final handoff reservation must both recompute the release gate from exact current Ringba tracking, ZIP activation and routing snapshots, current America/Chicago clock and source-approved landing publication, current legal export admission, founder scope, current ANI proof policy and existing five-site-handoff control. This requires no agent timer, no extra service, no writes, no new provider calls.

Also recognise the already-published **buyer-approved** static landing page as a **separate** checked publication gate only if the frozen source copies are SHA256 `faea59c0d8c6d510db8af876a53af439eac41e294f8d348e20576c75bd43cccb` and deployed `roofing.html` is `3b79c7856d2a9135900d797631693c75277947a78af47d10e1b9d6d4dff47997`, matching Seth's `gmail:1a12bc009d04fcc9` and recorded founder scope. **Publication does not bypass the required legal/ANI/routing/stop gates.**

344 `tests/test_lead_smart*` tests passed in candidate; final production deployment and tests must be separately verified before calling this live. No new Seth reply since `gmail:1a12d44d7e2f46a8`; previous request `gmail:1a12d47934923a1d` remains outstanding. Do not resend it.


## 12 October 2026 — Ringba one-hit proof and recording-specific gate

- Found existing credential file \`/etc/empire_ringba.env\`, **0600 root:root**. The Ubuntu app account cannot read it. Keep credentials root-owned, and do not print, copy, loosen its permissions or add a new token. The desktop remote command policy disallows privileged execution, so no fresh authenticated Ringba provider proof has yet been obtained.
- New \`scripts/probe_lead_smart_ringba_root_readonly.py\` reads ONLY that exact root-owned configuration with a strict literal parser, rejects symlinks, weak file permissions, unsupported/shell-expanded values and ambiguous account selection, resolves account identity once, and uses the existing Ringba observer contracts for three bounded provider reads: call logs, tracking and routing. Diagnostic output omits tokens, account IDs, personal phone numbers, raw provider bodies and dangerous exception messages. **Never** changes a route, sends mail, calls the number, records money, creates agent timers, refreshes production snapshots or grants traffic approval. A 403 on CallRoutes means access restricted, not "route missing."
- When a privileged founder-controlled operator elects to run this one-time **read-only** preflight after reviewing the committed script: \`cd /srv/empire_os && sudo -n ./.venv/bin/python -m scripts.probe_lead_smart_ringba_root_readonly\`. The output itself is safe to share; do not share the environment file. This is the only privileged command proposed by this handoff, and it does not activate anything. The command is **not** represented as executed.
- The existing live computed launch state now has an independent explicit gate \`recording_notice_and_retention_verified\`. This gate is false until real responsible-party consent/notice, recording access, retention and deletion proof exists. Buyer recording "enabled" and an approved Privacy/Terms export are **not** substitutes. Even otherwise fresh Ringba tracking, visual approval and approved legal pages cannot open a call route while this gate is false.
- Existing legal policy exports, public reviewed-content receipt, current tracking, Ringba buyer route/ANI and the supervised-pilot approved control remain separate. Do not mint legal sign-off or buyer administrator evidence from this code.

Release checks include the complete Lead Smart regression suite, plus root-preflight negative tests. Runtime's public gateway must receive a separately approved restart before counting the new request-scoped recording gate as loaded; until then the existing live gate still blocks all call handoffs.

## 12 October 2026 — bounded Chicago supervised-pilot window

The existing **buyer-general** hours remain as independently confirmed by the buyer: America/Chicago Monday–Friday 08:00–18:00, Saturday–Sunday 10:00–16:00 (source \`gmail:1a12229d9d3ffe75\`). These do **not** constitute authority for a homeowner-facing revenue pilot at all those times. The initial monitored roofing pilot is separately limited to **Monday–Friday 10:00–12:00 America/Chicago**. The pre-existing \`empire_os/lead_smart_site_handoff.py\` atomic handoff control now validates **both** configured start and end against this narrower weekday window as well as the active buyer-general-hours readiness gate. Weekend, early, late, timezone-naive, unsupported and overlong handoff windows fail closed. A future operator config cannot silently widen the first bounded pilot. No new timer, control-plane server, buyer email or outside paid traffic.

The exact real-provider and legal blockers remain **unchanged**: current authenticated Ringba evidence, enabled Direct buyer destination/ANI proof, recording controls and legally sufficient notice, approved deployed privacy/terms, and a named/verified site-handoff monitoring and stop receipt. The configured Ringba token and account ID were **not** available in the executing remote session; the current provider route could not be independently refreshed by this operator. Do not infer that a provider route is missing from a forbidden API response or that a truncated Ringba test completed a buyer leg. No calls/CTA enabled.

Tests: complete \`tests/test_lead_smart*.py\` suite **193 passed**, including simulated weekday 10–12 acceptance and rejected weekend/08–10/12–13 pilot windows. Deployment remains fail-closed; the source patch is not a production-service restart or live call activation.

## 12 October 2026 additional production completion
- Production code commit `2f1c2786` deploys request-scoped computed live readiness. The two call-site checks no longer trust historical `launch_readiness/latest.json`, and the published buyer-approved roofing export is exact-hash-checked. Candidate tests: **344 passed**. Production targeted tests: **122 passed**, gateway restarted, origin roofing/commercial both 200, call handoff 503; no real call admitted. No new agent timer/runtime.
- One official public coverage observation at **2026-10-12T08:46:10.628938Z** verified **27,100 ZIPs**, latest observed provider row update **2026-10-11T14:00:41.597557Z**. Intelligence and ZIP activation refreshed by atomic production receipt-backed replacement of exactly 3 existing coverage artifacts; backup `/var/tmp/lead_smart_coverage_refresh_backup_20261012`. The source hash remains `279fa020dc7162684cc08a7f3f9fbc239c61a06a657ecdf36bfd44abceac7db0`. No provider routing proof resulted.
- Currently passing gates: ZIP targeting, frozen buyer page approval, signed-off landing publication by actual HTML/source hashes, founder launch scope. Call remains disabled. Blocked: effective legal policy, five-call operator control, Chicago buyer hours if outside window, original ANI, fresh authenticated tracking and actual buyer route. **Do not ask founder to approve those completed gates again or resend Seth the same email**.
- The draft Privacy and Terms files adjacent to this handoff are **review copies only**. No approved live legal export, no consent or recording guarantee. Last buyer reply `gmail:1a12d44d7e2f46a8`: recording enabled and Seth's alleged test hung up before connection. Last follow-up `gmail:1a12d47934923a1d`: buyer-side configured target/ANI plus recording disable or actual notice/retention requested. No later reply on this run.


## 12 October 2026 evening — founder-executed privileged Ringba proof (READ ONLY)

Founder executed the pre-existing one-shot tool directly on EmpireOS:

\`cd /srv/empire_os && sudo -n ./.venv/bin/python -m scripts.probe_lead_smart_ringba_root_readonly\`

Observed sanitized diagnostic: schema \`empire.lead_smart.ringba_privileged_one_hit.v1\`, status \`OBSERVATION_COMPLETE_LAUNCH_HELD\`, \`account_selection_resolved=true\`, current authenticated Ringba \`provider_number_campaign_binding=true\`, and \`matching_campaign_number_call_rows=3\`. This establishes the Ringba number/campaign association and three logged matching rows **only**; it does not prove three connected calls, a buyer handoff, payability or revenue. \`buyer_leg_connection_proven=false\`, \`caller_ani_pass_through_proven=false\`, \`recording_notice_and_retention_verified=false\`, \`revenue_verified=false\`, \`launch_authorized=false\`.

\`CallRoutes\` returned HTTP **403** for the authenticated affiliate scope, with \`FORBIDDEN_NO_ROUTE_ABSENCE_INFERENCE\`. This is **unavailable route visibility**, not evidence of no buyer destination. Buyer-admin verification of the enabled Direct destination and original caller ANI remains outstanding. The last buyer-side email explicitly says their test was hung up before connection; no full buyer-leg/recording proof exists. Latest request \`gmail:1a12d47934923a1d\` already asks those **two exact confirmations** (configured Direct/ANI and recording disabled vs notice, consent, retention and access). Gmail search on 12 Oct found no newer Seth/support response. **Do not resend the same request.**

One-hit probe is intentionally **observation-only** and neither persists/upgrades live Ringba tracking nor changes traffic gates. At this later clock, the request-scoped launch also reports stale \`tracking_verified=false\` and \`zip_targeting_verified=false\`, in addition to \`legal_release_verified=false\`, \`recording_notice_and_retention_verified=false\`, \`pilot_stop_verified=false\`, \`caller_id_pass_through_verified=false\`, \`routing_runtime_verified=false\`. Re-refresh bounded provider/ZIP receipts **only** during coordinated prelaunch after buyer/admin and legal evidence; refreshing them now would not authorise live calls. No outbound, production restart, legal publication, route write, traffic, money, or call activation was performed.

## 12 October 2026 — reviewed legal drafts and disabled operator template

Existing exact-build **review-only** Privacy and Terms pages were located in the Lead Smart isolated worktree:
- /var/tmp/empire_lead_smart_unified_release_20261011/apps/empire-public-site/out/privacy.html (SHA256 d231a3a906f9803703366b59d846863e1ed9087b474e2b6d2a257a10bf60546d)
- /var/tmp/empire_lead_smart_unified_release_20261011/apps/empire-public-site/out/terms.html (SHA256 e17c8c4e4b3727f8f1a4d0826a1077f0da3ca3764ff7de21458b6b2ec591abb0)

Both contain the existing Founder/legal review draft marker and **must not** be copied into the live public export as effective policies. The updated 12 October Markdown policy documents are also explicitly PROPOSED and are not automatically equivalent to those earlier HTML builds. We are preserving those existing engineering assets, not rebuilding another website or creating a release receipt.

The existing public gateway's static reviewed-content admission is hardened for the later policy wording: Status: PROPOSED, NOT EFFECTIVE OR PUBLISHED, and final review copy all fail closed even with matching synthetic page SHA and all otherwise-approved fixture flags. These are negative status markers, **not** new legal sign-off authority. Coverage remains governed by the original deployed site and founder/legal exact-content receipt. A new isolated test covers proposed policy fixtures, absent genuine receipt, and current live 404/noindex outputs.

The new docs/evidence/lead_smart_supervised_pilot_DISABLED_TEMPLATE_20261012.json specifies the **existing** five-site-handoff stop method, campaign and number, but is explicitly disabled, has no selected start/end and uses a placeholder monitoring owner. Tests verify this draft can **never** count as a running control receipt. Before first live call, select an authorised named monitoring operator and a confirmed weekday America/Chicago 10:00–12:00 monitored slot, then independently verify buyer route, caller ANI, recording controls, actual legal release and a current provider+ZIP snapshot. Nothing here authorises that activation.

No service restart, deployed legal export, provider write, paid traffic, outbound, homeowner call or new agent runtime was performed in this continuation.
