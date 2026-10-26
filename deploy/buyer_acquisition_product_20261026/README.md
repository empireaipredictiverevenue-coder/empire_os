# EmpireOS Buyer Acquisition Team — original Founder Commercial Operations integration

**Release candidate:** 2026-10-26, staged and tested on the original Founder frontend release. **NOT activated as of this candidate's creation.**

## Ownership and scope
- Original pinned frontend owner: `/home/ubuntu/empire_releases/property_birmingham_private_stage_20261022_v3/web`
- Source route: `src/app/founder/commercial-pipeline/page.tsx` (additive import and component mount only)
- New components in this directory are byte-for-byte copies of the staged private release.
- Isolated built tree: `/home/ubuntu/empire_worktrees/buyer_acquisition_product_20261026/web`
- Protected original API, SEO, CRM, other routes, existing workers and timers: unchanged.
- Original source snapshot excludes the newer deployed commercial route, so **do not apply to the older canonical apps/search-command-centre src without a frontend-owner reconciliation**.

## Working evidence
- Next.js 16.3.5 webpack optimized build completed with all original routes.
- TypeScript check passed.
- Local isolated Next production server returned HTTP 200 and showed `Buyer intelligence workbench`, interactive company search, industry and workstream filters, and real records including polyares.com.
- Local original Founder page also returned HTTP 200.
- Public empire-ai.co.uk Founder route returned HTTP 404; the workbench is intended for the private Founder console, **not** a public landing page.

## Release
The immutable activation preflight checks the exact original frontend source SHA-256 and build ID, protected SEO source parity, and the presence of *only* the three approved source-file differences. It saves the previous `.next` build and original page before changing the running service, verifies the Buyer workbench plus existing Founder/SEO pages, and rolls back on failures.

User/operator root action (not performed by the remote automation connector):
```bash
sudo bash /home/ubuntu/empire_worktrees/buyer_acquisition_product_20261026/activate_buyer_acquisition_product_20261026.sh
```

Expected confirmation: `FOUNDER_BUYER_ACQUISITION_PRODUCT_LIVE_VERIFIED`.
If not displayed, examine the console journal and backup; do not claim activation succeeded.

## Product limits
- Source: original EmpireOS private `founder_qualification_actions_latest.json`; read server-side, with a guarded schema, timestamp, size, file-type and no-outbound contract.
- UI projection excludes recipient addresses, direct message contents, personal contacts and raw source text.
- Filter controls are local client-side research navigation; they cannot send email, alter EmpireDB, approve buyers, initiate lead delivery, settle payments or claim revenue.
- Sector match means first-party sector research relevance. Matched ZIPs, approved capacity, paid contracts, actual deliveries and settled revenue remain separately unverified.
