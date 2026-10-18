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
