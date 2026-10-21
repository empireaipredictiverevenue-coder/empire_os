# National Storm Hub — Revenue Pulse & Alerts V1

## Existing system reused
- EmpireOS canonical `empire_os/revenue_pulse.py` V3, restricted EmpireDB PostgreSQL reader and existing Revenue Pulse five-minute timer. No new database, revenue ledger or independent scheduler.
- Legacy `empire_os/alerting.py` exists, but can send real email and uses obsolete Solana nomenclature and paths; it is **not invoked**.
- New pure rules `empire_os/national_storm_hub_revenue_alerts.py`; private one-off review `scripts/review_national_storm_hub_revenue_alerts.py`.

## Separating metrics, not inventing customers
1. **Website operations:** real HTTPS homepage status and public alerts endpoint, checked on demand. Alert candidates for errors; no fake "all clear."
2. **Engagement / acquisition:** no trustworthy NSH consent-first page/ZIP/Passport analytics yet. Counts remain `null`, not 0 or imagined.
3. **Customer enquiry:** only original tenant-scoped, consent-verified, homeowner-initiated canonical EmpireDB receipt may trigger alert. No forms/services to issue that yet, so `nsh_enquiries=null`.
4. **Payments and recognised revenue:** only independent verified payment-settlement/accounting receipts; recognised revenue stays `null` until a tenant-bound ledger reader is connected. The EmpireOS global Revenue Pulse *cannot* establish how much NSH earned.
5. **Storm warnings** remain source-backed weather alerts, **not** commercial enquiries, lead opportunities or revenue.

## Candidate alerts (read-only until notification authority)
- Website unavailable -> critical founder review
- NWS public alert endpoint unavailable -> warning / check source
- EmpireOS canonical Revenue Pulse snapshot stale -> internal warning
- Genuine consented homeowner service enquiry -> high
- Verified settled payment -> high
- Verified accounting revenue event -> high
- De-duplicate by `kind|canonical evidence_ref`; compare previously seen keys across runs. The evaluator never sends or stores.

## Run the review
```bash
cd /home/ubuntu/empire_worktrees/national_storm_hub_depth_20261021
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_national_storm_hub_revenue_alerts.py tests/test_revenue_pulse.py
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  scripts/review_national_storm_hub_revenue_alerts.py --read-only --probe-live
```

## Next implementation gates
- Consent-first first-party event and engagement measurement, respecting browser local Passport and allowing refusal; avoid trackers without notice/choice.
- Tenant authority in EmpireDB, event schema and authenticated private owner dashboard before attaching real first-party receipts.
- No public revenue dashboard revealing internal financial data.
- Notification delivery to the founder requires known verified channel, idempotency and rate-limit, and explicit permission; never use obsolete alerting code to send without review.
- The existing Revenue Pulse timer should remain the company owner. An independent opt-in ChatGPT condition watch can monitor public availability hourly without modifying operational schedulers.

## Implemented website experiences (same branch)

- `https://nationalstormhub.com/alerts`: public NWS alerts page, state + ZIP selection, saved Storm Passport area, official source provenance, acknowledgement stored in the visitor's own browser, manual refresh and 5-minute polling while page visible.
- Optional browser pop-ups for **new Severe/Extreme warnings** while the page is open, after a user gesture/permission. Existing warnings form the baseline and do not trigger mass notifications. Not 24/7 push and not emergency warning delivery.
- `https://nationalstormhub.com/founder/revenue-pulse`: private founder input (access key intentionally NOT stored in URL, localStorage or cookies), automatically rereads the canonical company-wide snapshot every minute while open. Shows only validated aggregate stage counts and observed conversion-gap alerts, with source freshness. Optional desktop pop-ups for new observed gap alerts while open.
- `/api/founder/revenue-pulse`: bearer-key gate from protected systemd EnvironmentFile, constant-time digest check, no-store and noindex; **returns zero private data without authorized key**.
- Important: the website's protected Founder Pulse is **EmpireOS organization-wide evidence**, NOT verified National Storm Hub business results. Separate tenant-specific revenue remains unknown (no authenticated tenant receipts connected).
- No scheduled ChatGPT tasks, no outbound, no live lead dispatch, no email delivery, no payment activation.
- Production operator key is stored in `/home/ubuntu/.config/nsh/founder-pulse.env`, mode 0600. Founder retrieves it directly over authorised SSH; never put access keys in Git or a chat.

### Safe founder access (run locally in Windows PowerShell)
```powershell
ssh ubuntu@62.210.95.205 'sed -n "s/^NSH_FOUNDER_PULSE_KEY=//p" /home/ubuntu/.config/nsh/founder-pulse.env'
```
Copy the returned key directly into the website's founder login form. Do not share the key or screenshot it. Cloudflare Access, rate limits, SSO and a complete founder authentication system should replace this interim single-secret gate.

### Production verification
- All 13 National Storm Hub Node tests and 13 backend Revenue Pulse regression tests must pass.
- `/alerts`, `/founder/revenue-pulse`, home, weather and predictor endpoints return 200.
- Unauthenticated and wrong-key `/api/founder/revenue-pulse` return 401 with no accounting fields; authenticated access returns a source-dated, explicitly organisation-wide read model.
- Both website services remain active, HTTPS remains valid, and existing MX/DNS unchanged.

### Known limitations
- Alerts update only while relevant page is open; no background Service Worker push, email or SMS delivery.
- One saved area in browser, no authenticated per-user notification preferences.
- A canonical revenue ledger is not yet bound to National Storm Hub tenant receipts; no NSH payment/revenue figures can be claimed.
- A single shared founder access token is interim only; protect and rotate as needed, and add Cloudflare Access and rate limiting before broad operational use.
