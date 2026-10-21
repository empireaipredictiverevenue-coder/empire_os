# Empire AI / ASTRA — Lead Smart roofing campaign: FULL OPERATOR HANDOFF

**Checkpoint:** 21 October 2026, production inspected ~09:45 UTC. **Status: LIVE WEBSITE, CALL ADMISSION OFF, NO VERIFIED PAYABLE REVENUE.** This handoff closes the engineering/evidence work in this chat; it does **not** claim the revenue objective has been achieved.

## Owner mandate — do not drift

The user wants one accountable operator to acquire **genuine US homeowners needing eligible roofing replacement/installation** and earn buyer-accepted payable phone calls and collected payments. Work on this campaign, not site redesign or unrelated infrastructure. No paid traffic, paid editorial, fabricated leads, incentivised test calls, unsolicited homeowner DMs, source laundering, spending, funding or mainnet/checkout activation. Do not expand beyond the exact founder-approved call scope or treat buyer permission as founder authorisation.

The companion user prompt, “ASTRA — OWN THE CAMPAIGN FROM HOMEOWNER DEMAND TO MONEY RECEIVED,” identifies three acquisition lanes: **public in-market demand**, **local complementary/referral partners**, and **permitted owned/community distribution**. Use existing assets; track source -> enquiry/call ID -> buyer leg -> qualification -> buyer disposition -> payable $ -> settlement. Do not call a draft an executed placement.

## Production truth / exact identifiers

- Ubuntu production server: `ubuntu@62.210.95.205`; canonical checkout: `/srv/empire_os`, active branch `agent/data-cloud-wave4`; database **EmpireDB**, not Supabase.
- Approved website: `https://empire-ai.co.uk/`. Live homeowner entry: `https://empire-ai.co.uk/roofing`; disclosures: `/roofing/call-privacy`. Industry internal link: `/industries/roofing`.
- Buyer: **Lead Smart**, Seth and team, `info@leadsmartinc.com`; original Gmail thread ID `1a0d9ce883c87d4a` in connected `flavag83@gmail.com`.
- Ringba tracking phone `+1 888 357 9305`; exact campaign `CA8278ed3f26e9495b881fe3833174d007`.
- Production control: `runtime/revenue/lead_smart/pilot/approved_control.json`; **`mode=FULL_CAMPAIGN` is historic only, `enabled=false`, `full_campaign_scope_revoked=true`**. Never infer from the old mode that an ongoing campaign is authorised.
- Tested edge responses at checkpoint: `/`, `/roofing`, `/roofing/call-privacy`, `/industries/roofing` = HTTP 200. POST `/roofing/pilot-handoff` = HTTP 503 (intended closed state). ZIP `60601` is listed in recent guidance but listing is **not** current payable capacity or permission to dial.
- Home page uses the founder-approved V2/cinematic design; **do not rebuild/overwrite it**. The V2 roofing content has a pinned, root-owned technical compatibility attestation `/etc/empire_lead_smart_v2_landing_compatibility.json`; this is **landing equivalence only, not legal/call readiness**.

## Buyer correspondence: verified, no need for another repeat test

- **21 Oct 02:01 UTC**, Seth/Lead Smart Gmail ID `1a15c31a128651bb`: “No need for the test window, we already tested your numbers and everything looks good. You can go live.” This confirms buyer willingness/number test, **not** independent proof of specific buyer-leg connection or the founder's permission to launch indefinitely.
- Founder later corrected the broad 7-day interpretation: only a **10–20 minute supervised pilot**, max **five handoffs**, had been intended. Those strict runtime limits are deployed; the old seven-day authority was expressly revoked. A new exact founder-approved short window is required before any reactivation.
- **21 Oct 09:20 UTC**, the user expressly approved and the assistant SENT the outstanding commercial-terms email from primary Gmail, message ID **`1a15dc2f341f4638`**, same thread. It asked for exact Direct 120-connected-second threshold, additional disqualifiers, 30-day duplicates, Ringba payable disposition/dispute path, ZIP/capacity/current hours, live bid and UK-compatible payout method/monthly settlement. **Gmail label SENT confirmed**. The final check at ~09:45 UTC found **no newer buyer reply**; do not send a duplicate.
- Current original email guidance: first-party owned organic/SEO, roof **installation/replacement**, not indiscriminate roofing traffic; Lead Smart Direct IVR collects ZIP; affiliate ZIP ping not required; original ANI must pass through; typical payout qualification at **120 connected seconds**, subject to offer/acceptance confirmation; duplicate caller within **30 days** pays once; payout **variable by the bid at call time**. Historic onboarding says payment by the **10th of following month**, except CPL. **Current final offer terms, minimum threshold exceptions, rejection/dispute timing, current price and usable UK payout method are unverified.**
- Buyer-reported operating schedule: Mon–Fri 08:00–18:00, Sat–Sun 10:00–16:00, labelled CST, zone America/Chicago. **DST/CST interpretation is not independently verified**; live time gate still fails. Do not invent live receiving availability.
- The user cannot assume US ACH, PayPal, Stripe or USDT/BSC will be accepted by buyer; request an actually usable payout route.

## Ringba and revenue evidence — do not conflate these

- Authenticated live Ringba observation as of **21 Oct 09:29 UTC**: campaign/tracking binding valid; **one historical matching call row**; reported **48 seconds total**, **32 connected seconds**. New restricted provider call-detail observation confirms an authenticated **ConnectedCall** event and `isDuplicate=true` for this row. This **does not** identify the specific Lead Smart buyer destination, prove a buyer agent answered, satisfy 120 seconds, or create an accepted payable call. Treat it as a **possible historical test call**.
- Provider CallRoutes remains **403** for our affiliate access. Original ANI pass-through is buyer-attested but **not independently observable** in current role.
- **0** first-party site handoffs recorded; site-handoff ledger file is **absent** (distinguish from a populated zero ledger). **0 independently verified buyer-leg connections**, **0 accepted payable calls**, **0 verified cash receipts**. No revenue is to be recognised.
- Call-level privacy-safe reviewer (already deployed): `scripts/review_lead_smart_call_to_cash_20261021.py`. Latest root-only receipt: `runtime/revenue/lead_smart/commercial_pulse/call_to_cash_latest.json`, mode **0600**, no caller ANI or raw account token. Call IDs are hashed; provider candidate amounts are not accepted/paid dollars.
- Automatically refreshed every **4 hours** using `empire-roofing-call-to-cash.timer` and root-only `empire-roofing-call-to-cash.service` (active, last successful). Existing `empire-roofing-ringba-refresh.timer`, `empire-roofing-coverage-refresh.timer`, `empire-roofing-commercial-pulse.timer` are active and read-only. The revoked week-long cutoff timer is disabled.
- Code commits: `0e32bf4f4` (read-only source-bound call-to-cash proof); `5923e2cef` (mode-0600 atomic receipt and periodic monitor); `8548e9cfd` (provider detail connection/duplicate flags, never buyer identity/revenue inference). Broader production regression at prior checkpoint: **415 passed, 1 deprecation warning**; more recent code may have landed independently.

## Live launch readiness: still RED

As of 21 Oct ~09:45 UTC, exact `compute_live_launch_readiness().blockers`:

1. `legal_release_verified` — independent review/signoff still not present.
2. `recording_notice_and_retention_verified` — the public disclosure and buyer's recorded disclaimer test exist; independent recording, responsible-party retention/deletion and legal assurance **not** certified. Existing privacy notice states Ringba recordings may be retained indefinitely and buyer says it can delete on legal request.
3. `pilot_stop_verified` — short runtime duration and cap controls have been hardened but end-to-end verified stop/receipt in the actual authorised trial context remains absent.
4. `operating_hours_verified` — buyer Chicago schedule + time interpretation do not prove current, unambiguous receiving availability.
5. `caller_id_pass_through_verified` — buyer says yes; independent route-level evidence missing.
6. `routing_runtime_verified` — affiliate CallRoutes 403; no buyer-leg connection evidence.
7. `landing_publication_authorized` — public site technically compatible/approved, but scope/launch predicate still held; do **not** alter gates to make a report green.
8. `founder_live_traffic_authorized` — founder explicitly revoked old week-long authority. New exact activation approval required once other gates pass.

Verified TRUE in the same live reader: `tracking_verified`, `zip_targeting_verified`, `buyer_landing_page_approved`. **No live consumer calls until the complete independent gate passes.** Do not restart website, change legal retention flags, invent independent CallRoutes proof or promote buyer statements into provider receipts.

## Genuine acquisition already done (not all three experiments complete)

- **Two genuine publisher approaches sent**: Roofing Mate `partners@roofingmate.com` Gmail sent `1a15a400b30bc00a`; Roofing Calculators `partners@roofingcalculators.org` Gmail sent `1a15a403568e911a`. As of 21 Oct ~09:45 UTC **no incoming replies**. Neither has agreed to traffic, tracking, terms or performance share.
- RoofPitch (`contact@roofpitch.net`) was already contacted and replied from Ali on 11 Oct `1a1286f08693e96d`: only **paid sponsored/guest placements**; exclude from zero-budget performance campaign and do not duplicate the pitch.
- Existing approved first-party links: roofing industry page -> homeowner ZIP checker. Site `/roofing` appears in `sitemap.xml`, `robots.txt` permits indexing. Google Search Console 7–20 Oct report: **no /roofing page row, 0 reported clicks / 0 impressions**, indexing not independently proved (sitewide organic demand previously tiny). A sitemap is not real traffic. Do not rebuild website to manufacture progress.
- Public roofing form calls `POST /roofing/coverage-check` for exact five-digit ZIP. API provides coverage **guidance only**, does not reveal tracking digits or authorised call route while closed. The site displays the consent-gated call action only when backend live readiness and available admission agree. No need to fake a mobile call.
- No homeowner requests have been answered in approved communities, no completed 20-partner local cohort, no approved community placement, no genuine homeowner call, no payable acceptance or settlement. **Do not claim those experiments executed.**

## Next agent: exact priority order and ownership

**1 — Commercial reply / payer rules (external: Lead Smart).** Recheck thread `1a0d9ce883c87d4a` for an authentic response *after* sent message `1a15dc2f341f4638`. Extract binding Direct threshold/exclusions/duplicate/claim dispute, current ZIP/offer/available capacity, bid/per-call payable status and accepted settlement method. Do not chase Seth for re-testing or re-send the same terms email without a sensible follow-up cadence. Buyer response is outstanding.

**2 — Call compliance/route (external provider + Empire legal/operations).** Obtain Ringba account-owner supplied **narrow call-detail/target evidence** or grant allowing verification of actual buyer leg, connected destination and ANI, without requesting homeowner phone numbers or exposing recordings. Provider target/CallRoutes 403 is not a software bug to circumvent. Have responsible operator certify consent notice/recording party/retention/deletion instructions under applicable laws. Verify Chicago DST/time window, offer capacity and site admission automatic stop before any traffic switch.

**3 — Founder activation decision (founder, only after 1–2).** Bring exact current window, ZIP cohort, duration `10–20min`, cap `<=5`, customer messaging, proof of real stop, and rollback. Obtain founder approval for that particular controlled release; the buyer's “you can go live” email is not enough to supersede the founder's separate revocation. No direct mutation of the old `FULL_CAMPAIGN` config.

**4 — First genuine homeowner acquisition (commercial acquisition owner).** While waiting, use three **free, permitted** lanes from the user's ASTRA prompt: (A) locate real, recent publicly shared roof replacement/installation requests in an actually eligible cluster; help publicly only if community rules permit, **no unsolicited DM**; (B) collect and qualify 20 local referral candidates (real, rights-respecting complementary services), check past sends/suppression, prepare a small personally relevant batch and obtain needed outreach signoff; (C) distribute accurate homeowner ZIP guidance only through owned assets and authorised communities, with working unique source attribution. Do **not** direct homeowners to a disabled call endpoint or represent third-party visits as `EMPIRE_FIRST_PARTY_ORGANIC`; do not add a new affiliate source without buyer consent. The two publisher emails are already sent—follow replies, no duplicate sends.

**5 — Close economic loop (data/finance owner).** Once source/call permission exists, reconcile: source -> site dial admission -> hashed Ringba ID -> authenticated call events -> buyer destination verified -> duplicate + 120s and other offer rules -> buyer disposition -> final payable live bid USD -> invoice/receivable -> authenticated settled cash. **Test calls and apparent connection events are not revenue.** Use canonical EmpireDB for any authorised tenant record; don't write finance rows on synthetic or unverified evidence.

## Operator commands (safe read-only)

```bash
cd /srv/empire_os
PYTHONPATH=. .venv/bin/python -B - <<'PY'
import json
from empire_os.lead_smart_site_handoff import CONFIG
from scripts.materialize_lead_smart_launch_readiness import compute_live_launch_readiness
c=json.loads(CONFIG.read_text()); r=compute_live_launch_readiness()
print(json.dumps({"enabled":c["enabled"],"revoked":c.get("full_campaign_scope_revoked"),"ready":r["launch_ready"],"blockers":r["blockers"]},sort_keys=True))
PY
sudo -n .venv/bin/python -B -m scripts.review_lead_smart_call_to_cash_20261021
systemctl list-timers --all --no-pager | grep empire-roofing
curl -sS -L -o /dev/null -w '%{http_code}\n' https://empire-ai.co.uk/roofing
```

`sudo ... --write-latest` refreshes **only** the root-readable aggregated commercial observation; it does not dial or activate. Do not `cat` any root API token or raw caller ANI logs into chat.

## Explicit success / stop conditions

**Commercial mission is NOT complete.** Handoff complete; launch is blocked on genuine external evidence and founder-scoped activation. Stop pretending code/test/page views represent success. Continue only authorised work. Next user-visible update should be short: **Executed / Actual accepted calls and cash / One blocker owner / Next real action**. Do not launch out-of-hours or fabricate revenue.

**This handoff is the source-of-truth continuation brief for the next agent.**
