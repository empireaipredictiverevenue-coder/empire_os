# Empire AI — public site privacy operational review
**12 October 2026 | READ ONLY | NOT LEGAL APPROVAL | NO PUBLICATION**

## Why this matters

Empire AI is preparing its first first-party US roofing pay-per-call buyer launch and independently negotiated LeadBank, Inquirly and Connexis partnerships. The shared public website's Privacy and Terms remain proposed review drafts. This note records only operational facts from one scoped, privacy-safe server diagnostic. It does not replace a jurisdiction-specific legal review, partner approval or the founder's explicit publication gate.

## Proven diagnostic scope

Run once, locally, without sudo or a deployment:

`cd /srv/empire_os && PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m scripts.probe_public_privacy_release_readonly`

The probe reads effective journald **configuration metadata only**, journal **disk-use metadata only**, local gateway HTTP headers using **GET** against seven fixed known paths, and the 16 owned website TS/JS source files. It never fetches journal entries, visitor IPs, form bodies, private buyer records, provider recordings, secrets, cookies, credentials or wallet data. It does not change settings, open a call, publish a legal page, send mail, create a timer or grant launch authority. The output is observational JSON `empire.public_site_privacy_operational_observation.v1`; no persistent DB or production receipt is written by the script.

Tests: `tests/test_public_privacy_release_probe.py` and existing `tests/test_lead_smart_legal_review_copy_guard.py` — **23 passed** on 12 October 2026, evidence command output at `/var/tmp/empire_privacy_one_hit_evidence_20261012.json`, test output `/var/tmp/empire_privacy_one_hit_gate_20261012.log`. Those files are ephemeral operational receipts, not release certificates.

## Exact local observations (not a platform-wide compliance claim)

| Item | Observed | What remains unknown |
|---|---|---|
| Local GET `/`, `/roofing`, `/predictive-revenue`, `/buy`, `/commercial` | HTTP **200** on each | Complete browser/cookie behaviour and vendor/Cloudflare edge handling |
| Local GET `/privacy`, `/terms` | HTTP **404** on each | Actual legally approved and deployed policy content |
| Local origin `Set-Cookie` headers | None in these **seven anonymous GET** responses | Cookie headers after browser interactions, third-party edge storage, client-side JS and other endpoints |
| Owned source code scan | 16 TS/JS files; **0 direct pattern matches** for localStorage, sessionStorage, document.cookie, or selected common analytics calls | Bundled/dependency scripts, Cloudflare NEL/reporting, proxy/edge storage or other instrumentation |
| Public gateway service | `StandardOutput=journal`; systemd start 12 October 10:45:49 UTC | Complete request logging, redaction, access control, backup replication and physical deletion |
| journald effective settings | No explicit active `MaxRetentionSec`, `SystemMaxUse` or `RuntimeMaxUse` was reported by the one-hit diagnostic | Actual record lifetime, active defaults and data deletion guarantees |
| journald disk-use metadata | Journal disk usage was reportable; separate direct metadata check observed **approximately 3.8 GB** | Whether these archives include individual visitor metadata; duration of any particular record |
| Roofing call/recording | Independent recording consent, access and retention evidence is still **not verified** | Authoritative Ringba/Lead Smart/buyer configuration and state-specific consent obligations |

**Do not infer:** "no cookies anywhere", "no analytics data", "logs held for exactly four weeks", "GDPR/US privacy compliant", "Ringba recording disabled", or "call activation approved". The earlier observed rsyslog weekly/four-rotation rules do **not** establish journald or Cloudflare retention.

## Shortest remaining internal verification

1. **Founder/legal identity and rights channel.** Confirm the precise legal sole-trader data-controller name, business correspondence and working `founder@empire-ai.co.uk` rights-response procedure. Existing forward-delivery test is not full deletion/access workflow verification.
2. **Logging retention/roles.** Identify the effective journald storage cap, archives/backup lifetimes, access roles and secure deletion/review procedure; check Cloudflare Log/NEL/Report-To configuration, any processors and transfer controls. No retention change or production restart without separate approval.
3. **Browser and form data flow.** Review actual compiled static assets, Cloudflare edge, storage/analytics scripts and every public form's app/database/mail handling; determine real data fields, access, retention and DSAR paths.
4. **Buyer call consent.** Obtain exact buyer/provider recording disablement evidence **or** authoritative notice/consent/recording owner/access/retention/deletion and caller-ANI evidence. Buyer statement "recordings enabled" is not legal release.
5. **Publication.** Legal review and founder approve *exact* effective Privacy and Terms HTML plus hash-bound reviewed-content receipt. Only then deploy using the existing guarded gateway process. Publishing these draft notes, inserting a fake receipt, enabling indexation or traffic is expressly **NOT** authorised.

## Current effect on revenue

No new third-party system was built. This narrows legal transparency unknowns for **all four** independent buyer pathways, while the founder continues with first-party SEO, buyer reviews and eventual supervised, separately authorised traffic. No buyer terms or revenue were asserted by this audit.
