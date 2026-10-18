# Empire AI — Workspace solar tracking inside existing Founder Mail UI

**18 October 2026 | Source integrated, isolated production build verified, not yet live frontend-switched**

## Why this path

- Canonical private Gmail source: GET
  `http://127.0.0.1:8766/v1/founder-mailbox/workspace-solar-reply-review`
  in the already-running `empire-founder-dashboard-api.service`. It returns
  six exact Workspace sent anchors and any new, unverified inbound header
  candidates. It is not an authenticated tenant-bound CRM sales record.
- Existing Founder Mail Next.js page:
  `apps/search-command-centre/src/app/founder/mail/page.tsx`.
  The live `empire-founder-console.service` binds loopback only on port 3001;
  the public apex site `https://empire-ai.co.uk/founder/mail` returned 404
  during the scoped inspection. Any future public exposure requires separate
  verified founder authentication, not just obscurity, and explicit approval.
- The active CRM pilot is a **different loopback-only service** on port 8783,
  running an isolated release under `/opt/empire-ai/crm-pilot-releases/`.
  Its existing tenant login and canonical DB identity binding are preserved.
  This does NOT install a new CRM record or modify the authenticated CRM.

## What changed

- Added private-only, server-side Next component at
  `apps/search-command-centre/src/app/founder/mail/workspace-solar-review.tsx`.
  Its fetch is allowed only to the configured exact loopback Founder API;
  requests are no-store and component renders server-side, with no browser
  credentials. It validates the trusted provider's six expected companies,
  distinct thread IDs, Gmail review URLs, snapshot age, completeness and
  **false** CRM/sending authority. On invalid/unavailable/stale source it
  shows an unavailable notice, never fake zeros.
- Integrated one component into the already-existing Founder Mail page,
  **above** its primary canonical-reply inbox. No unrelated founder page,
  central API utility, login code, database schema or existing CRM service
  was changed.
- Cards distinguish sent-verified, no inbound observed, header candidate
  requiring actual founder Gmail review, and CRM identity still unverified.
  Gmail links open the original exact company thread; no raw email text,
  subjects, phone numbers, personal recipient addresses, tokens, classification
  claims, automated replies or revenue figures are displayed.

## Verification completed

1. Targeted ESLint of the two changed TSX paths — PASS.
2. Existing Search Command Centre full TypeScript `tsc --noEmit
   --incremental false` — PASS against current workspace source.
3. Isolated Next.js 16.3.5 **Webpack** release build in
   `/home/ubuntu/empire_worktrees/empire_workspace_solar_mail_ui_build_20261018`
   — PASS, with dynamic /founder/mail route compiled. Turbopack refused the
   isolated symlinked node_modules under its filesystem-root restriction;
   the supported Webpack fallback built successfully.
4. A temporary loopback **isolated preview** on 127.0.0.1:3099 returned
   HTTP 200 and server-rendered six actual company cards, the no-auto-send
   state and no-CRM-promotion indicators using the real authenticated Founder
   API. The preview process was terminated after the smoke test.
5. Live owner `empire-founder-console.service` remained active and untouched,
   as did `empire-revenue-crm-pilot.service` and all email/outbound services.

## 18 October — complete-route parity candidate and operator-gated deployment

The previous clean HEAD-only release omitted the existing live Founder
YouTube and Intent Review routes. To preserve those routes, a separate
**isolated, frozen, complete frontend snapshot** was created at:

`/home/ubuntu/empire_worktrees/empire_founder_mail_parity_candidate_20261018`

This snapshot was copied WITHOUT modifying the original shared source files.
It intentionally contains the two other agents' uncommitted frontend
features that are **already present in the currently running console**.
The candidate ran a full Next.js 16.3.5 Webpack production build:
compiled, TypeScript, static pages and route output all PASS. Its
127.0.0.1:3099 isolated preview returned HTTP 200 for ALL EIGHT existing
routes (`/`, `/founder`, `/founder/mail`,
`/founder/results`, `/founder/solar`, `/founder/youtube`,
`/founder/intent-review`, `/revenue`). The running 3001 console returned
HTTP 200 for the same eight. The candidate additionally rendered the
real six-business Workspace Gmail review panel (GB NRG and
100% Renewables both checked) and explicit no-CRM-case and no-auto-send
indicators. Source parity was verified with byte-level rsync checks.
The public apex `/founder/mail` returned 404 before any release.

A remote attempt to install a systemd drop-in for the private console
was **denied by the remote-command interface**. That attempt did NOT
mutate the live service. We did not bypass this restriction.

`scripts/deploy_private_founder_mail_solar_review_20261018.sh` is a
new one-off, narrowly scoped **operator-controlled** release script.
Its `--preflight` passed on the live server, and three release-script
tests passed. It pins four critical source hashes and frozen-build
presence; refuses altered canonical frontend source, an existing
competing systemd override, an unhealthy Founder API/CRM/timer, missing
existing UI routes or public exposure. Only the explicitly approved
`--apply-approved-private-release` branch makes a root-owned systemd
drop-in overriding **WorkingDirectory of the existing loopback Founder
Console service**. It restarts ONLY that private console and verifies
the panel, all eight existing routes, other services and public 404.
On any failure or interruption it restores the original service.

**Current live UI status remains PENDING operator-run release.**
To complete from a trusted Ubuntu session, after separate explicit
Founder release approval, run:

```bash
cd /srv/empire_os
./scripts/deploy_private_founder_mail_solar_review_20261018.sh --preflight
sudo bash ./scripts/deploy_private_founder_mail_solar_review_20261018.sh --apply-approved-private-release
```

Do NOT use `scripts/deploy_founder_console.sh`, overwrite the shared
`.next` directory, publish a public Founder URL or merge unrelated
frontend changes to achieve this release. Its rollback command is
printed on success; only the dedicated
`/etc/systemd/system/empire-founder-console.service.d/70-private-solar-review-release.conf`
drop-in is owned by this release.

## Production deployment / owner handoff

The canonical `apps/search-command-centre/src/app/founder/page.tsx` and
`src/lib/founder-api.ts` contain OTHER AGENTS' uncommitted changes.
The existing deploy helper `scripts/deploy_founder_console.sh` assumes
`feature/revenue-intelligence-v2`, performs fetch/merge, npm ci, rebuild and
restarts services; it is NOT safe for the current shared dirty canonical
branch and MUST NOT be run blindly.

The two exact TSX additions have been tested, and their isolated preview
fully renders. **They are not yet in the live Next.js .next build**. The
current UI/deployment owner should coordinate a bounded no-rollback build
and release that retains the unrelated founder changes, then verify
localhost 3001/founder/mail and do an authenticated user visual review
BEFORE saying it is production UI live.

## Outstanding CRM promotion prerequisite

A genuine future provider inbound header alone is not a sale. The original
`empire_os/gmail_reply_adapter.py` canonical path only accepts exact
existing sent outbound intent + recipient + Gmail thread identity and tenant
contact authority. The six connected-Gmail sends lack independently proven
intent/CRM records. They remain founder review candidates until a real sender,
opt-out handling, canonical entity-to-tenant binding and explicit prospect
acceptance are verified. No synthetic leads, CRM writes, replies, payment
activation, publicity or customer records were used for validation.

Current status: **six sent, zero inbound candidates in the scoped snapshot;
live Founder API 200; frontend source and isolated build PASS; live frontend
release pending owner coordination.**
