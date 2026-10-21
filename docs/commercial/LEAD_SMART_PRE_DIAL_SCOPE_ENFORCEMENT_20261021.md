# Lead Smart — pre-dial homeowner eligibility enforcement

21 October 2026. Existing Direct roofing campaign; the call-admission switch remains OFF.

**Why:** Lead Smart's authenticated reply (Gmail `1a15ea2dfa8c46b1`, 13:24:51 UTC) states renters, unrelated enquiries, solicitors, coached and incentivised calls are non-payable, and warns of programme sanctions. The eligible first-party intent is roof replacement or new roof installation.

**Scoped implementation:** The existing `/roofing/pilot-handoff` pre-dial recording-notice step now requires self-reported property ownership, a replacement/installation project selection, a voluntary and non-incentivised request, plus existing affirmative recording consent. The old consent-only POST cannot issue a dial permit. Missing, unexpected, duplicated, invalid or repair-only answers return a generic 422 with no phone link and no permit consumption. The original ZIP, freshness, recording, legal, route, operator, stop, and Chicago-window controls are still separately enforced.

**Evidence limits:** These answers are anonymous visitor declarations, not ownership verification, booking authority, buyer acceptance, a qualified call, a payable dollar amount or settled revenue. Form answers are not written to a database, ledger, user profile, email or URL. The existing ledger can record only an admitted dial-link count after all release gates pass.

**Review and release HOLD:** `empire_os/lead_smart_launch_readiness.py` deliberately pins the prior reviewed consent API source SHA-256 (`4ad55e9de33009ce75a9981cd83a962f15004f7a8f9b1a79e5cdf40c1713fb60`). This code change has a different digest. **Do not update that reviewed-source pin or treat this as recording/legal clearance without independent source/copy review.** The deployed static roofing landing page is unchanged; its older Chicago-hours and repair/inspection copy requires separate editorial/buyer review. The buyer's caller-local hours and dynamic buyer-capacity claims still require reconciliation. Do not send paid, coached, or fabricated calls.

**Release authority:** Build and test only. No RTB switch, new buyer terms accepted, independent recording/retention verification, Wire payout onboarding, live call activation or money movement is authorised by this document.
