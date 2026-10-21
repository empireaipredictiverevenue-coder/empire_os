# Lead Smart — bounded pilot runtime hardening, 21 October 2026

**Owner:** existing Lead Smart roofing/acquisition lane. No new buyer email sent, no live traffic, funds, routing or commercial activation.

## Changed and proven

- Production commit: `567649e4f`, source-controlled in `/srv/empire_os` on `agent/data-cloud-wave4`.
- Existing `empire_os/lead_smart_site_handoff.py`: any founder-scope-revoked control that switches to `SUPERVISED_PILOT` now requires a 10–20-minute weekday Chicago window, at most five call-link admissions, and the exact existing founder pilot authority reference. A mode rename cannot silently reuse the old two-hour period or the seven-day cap.
- `scripts/activate_lead_smart_supervised_retry.py`: preview and apply both reject handoff budgets over five. `--apply-founder-approved-window` was **not** invoked.
- Runtime simulation accepted the 15-minute/five-admission candidate and rejected 9, 21, 120 minutes and a 140-admission candidate. The real control remained `enabled=false` and `full_campaign_scope_revoked=true`.
- Canonical production regression result `398 passed, 1 upstream Starlette deprecation warning`; recorded at `/tmp/empire_lead_smart_bounded_runtime_canonical_final_20261021.txt`.
- After an operator restart, transient public 502s occurred during Uvicorn startup. Subsequent origin and public edge checks were 200 for `/`, `/roofing`, `/roofing/call-privacy`, `/buy`, `/commercial`; health endpoint 200, service active. Never report the transient error as an ongoing outage.
- Public POST to `/roofing/pilot-handoff` with recording consent was 503 UNAVAILABLE; zero website handoffs.
- Read-only Ringba root probe: provider campaign/number binding observed; restricted CallRoutes remains HTTP 403, one historical matching call row, no buyer-leg or payable revenue proof. Search Console page-level `/roofing` still reported zero clicks/impressions through 20 October.
- Read-only Ringba, coverage and commercial pulse timers are active. The revoked seven-day cutoff timer is disabled.

## Buyer permission and genuine blockers

Latest Lead Smart Gmail message `1a15c31a128651bb` (21 October 02:01 UTC) says, “No need for the test window, we already tested your numbers and everything looks good. You can go live.” This is buyer permission, **not** an independent provider-connected payout receipt. The founder's later correction limits our operating scope to a supervised 10–20-minute test. Do not send Seth repeated requests to retest or open a seven-day campaign.

The live `compute_live_launch_readiness()` still returns PREACTIVATION. Missing independent legal/recording governance, routing/ANI proof or scoped buyer attestation, current Chicago business hours, verified stop, and exact founder traffic authority must be dealt with without inventing their evidence. The new runtime duration safety guard does not satisfy any of those source gates.

**Next owner action:** source-verify the remaining real provider/recording and exact founder-authorised pilot window, then run the existing supervised operator only after independently passing all gates. Do not route actual homeowner calls while the public handoff returns 503. No revenue recognised.
