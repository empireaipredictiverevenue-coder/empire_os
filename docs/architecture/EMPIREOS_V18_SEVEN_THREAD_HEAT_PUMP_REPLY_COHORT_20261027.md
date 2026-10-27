# V18 — original seven-thread UK heat-pump Workspace reply cohort

**Date:** 27 October 2026
**Owner:** Existing EmpireOS Buyer Gmail evidence cycle (no new timer/service/database)
**Mode:** OBSERVE; never automatically send, change buyer acceptance, write CRM, or activate payment.

The existing `empire_os/workspace_heat_pump_reply_tracking.py` production module was originally four sent anchors. The exact three additional sent IDs and thread IDs are:

| Company | Existing Gmail thread ID | Authenticated Workspace SENT ID |
|---|---|---|
| Good Energy | 1a17a526f6945efa | 1a17a797e5a9f0e9 |
| Alto Energy | 1a17a5272d0e2a39 | 1a17a79980d72432 |
| Appian Heat Pumps | 1a17a527931e2d31 | 1a17a79a9700c50f |

V18 modifies only the original heat-pump scanner and lifecycle. The existing `scripts/poll_workspace_solar_outreach_readonly.py` dynamically references `HEAT_ANCHORS` and needs no edits. On the first seven-thread cycle it accepts *only* an exact, restricted legacy four-thread prior snapshot with all prior inbox-candidate IDs, then writes the new seven-thread snapshot. The parallel `heat_pump_relationship_lifecycle.py` accepts only an exact original four-thread or new seven-thread prior state and preserves all old seen-ID and already-surfaced follow-up state.

All seven sent headers must be verified against the *existing authenticated Gmail Workspace mailbox* on the same 15-minute timer. If any anchor is missing, the seven-thread scan fails closed. New inbound headers become human-review candidates only; no acceptance or money claims. The original four-thread metadata and lifecycle receipts are protected (0600) and should be backed up before the first seven-thread write.

Scoped source install: `empire_os/workspace_heat_pump_reply_tracking.py` and `empire_os/heat_pump_relationship_lifecycle.py` only. Do not change original Scout, search fabric, Gmail OAuth, other cohorts, original poll script, or systemd unit.

Regression suite `tests/test_heat_pump_seven_thread_v18_20261027.py` covers 4→7 migration, no dropped headers, incorrect anchors, false approval flags, unchanged follow-up history, seven-thread mock Gmail scan and one-time new inbound reporting. A separate pre-deployment authenticated live Workspace scan confirmed 7/7 headers and produced a seven-thread lifecycle report in memory with zero inbound candidates and no writes.

Note: `tests/test_google_workspace_mailbox.py::test_authenticates_exact_workspace_account_before_read` fails on untouched production as of 27 October 2026 due to test FakeCreds lacking the expected OAuth `scopes` property. Do not change production OAuth or claim V18 caused/fixed this existing test failure.
