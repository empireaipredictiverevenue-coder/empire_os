# Empire AI — Earned-Media CTA + ASTRA SaaS Website Rebase (26 October 2026)

**Stage:** Private full-static build and browser acceptance complete. **NOT LIVE, NOT PUBLISHED, NOT OWNER-APPROVED.** Original EmpireOS / EmpireDB unchanged. This is a direct continuation of the existing one website release, not a duplicate stack.

## What actually changed in this workstream

The original 38-line source-only website patch was insufficient to deploy because the public gateway serves generated `apps/empire-public-site/out/predictive-revenue.html`; the original pending SaaS preview was already a mixed Next.js static export, with a paired `predictive-revenue.txt` and versioned browser JavaScript. The original browser bundle contains `/commercial#commercial-enquiry`. Editing HTML alone would create client/server link disagreement.

A fresh *isolated build* was made from ASTRA's existing pending SaaS source (`/home/ubuntu/empire_worktrees/saas_evidence_preview_20261025/apps/empire-public-site`) with exactly the Stage 8 guide CTA and existing bounded source-hint helper. No modifications were made to ASTRA's original dirty source worktree; source was copied to `/home/ubuntu/empire_releases/earned_media_saas_union_20261026/build_source/apps/empire-public-site`. Next.js 16.3.5 `build --webpack` completed, including TypeScript and static export. A Turbopack-first attempt failed due its symlinked dependency root; webpack succeeded without changing the original project.

The compiled output contains **one** `/commercial?entry=%2Fpredictive-revenue#commercial-enquiry` link in page HTML, plus the equivalent `encodeURIComponent("/predictive-revenue")` expression in the rebuilt versioned browser page chunk. The old CTA is absent. Original SaaS free sample, deployment interest form, specific response consent checkbox, and public GET catalogue remain present.

## Rebase result (PRIVATE, NOT PRODUCTION)

The old 662-file SaaS release pin was stale. A live-only read-only index comparison showed exactly **five** newer pages relative to that pin:

- `commercial.html` (changed 26 October 15:05 UTC; buyer-readiness copy/metadata)
- `industries/roofing.html`
- `industries/hvac.html`
- `industries/property.html`
- `industries/legal-mass-tort.html`

The rebase copies the **actual latest 662-file live tree unchanged** into private staging, replaces only the newly compiled `predictive-revenue.html` and paired `predictive-revenue.txt`, and adds exactly **eight new-only content-hashed assets** required by those routes. It verifies that the five newer pages remain byte-identical; the only differences from the current live tree are the two route files and eight additions.

**Private candidate:** `/home/ubuntu/empire_releases/earned_media_saas_union_20261026/rebased_candidate` — **670 files**. Full-index SHA, per-file hashes and the exact 8 added paths are recorded in the private receipt `/home/ubuntu/empire_releases/earned_media_saas_union_20261026/private_candidate_receipt.json` and the tracked owner pickup JSON.

The original 662-file live site, ASTRA's earlier 672-file staged union, its prior approval scope, any root-owned backups and all production services remain untouched.

## Real isolated browser QA

In Chrome Headless with CDP and a loopback-only GET static server, the browser loaded the new HTML and the exact content-hashed JavaScript page bundle. The rendered CTA persisted **after hydration**, clicked through to the existing `/commercial` form with `entry=/predictive-revenue`, and displayed its required specific-response consent checkbox.

- Original SaaS evidence preview: **visible**
- New CTA: **present in HTML and hydrated JS**
- Commercial form navigated: **yes**
- Source parameter: **unverified browser-supplied hint**, not proof of Google attribution
- JavaScript exceptions: **0**
- HTTP 4xx/5xx: **0** after adding the existing public premium-discovery GET route to the isolated server's strict read-only allowlist
- External network requests: **0**
- Form POSTs: **0**
- Real buyer/prospect entries, payments, revenue: **none**

Tracked QA: `docs/website/release_candidates/EARNED_MEDIA_SAAS_REBASED_BROWSER_QA_20261026.json`.

**Pre-existing Commercial title parity issue:** the latest live `commercial.html` contains `Buyer Readiness & Revenue Intelligence | Empire AI` as its document title, but the retained `commercial.txt` still contains `AI Consultancy & Revenue Intelligence | Empire AI`; the browser reported the older title after hydration. We preserved **both** original live files exactly, rather than overwriting a concurrent owner's update. ASTRA must reconcile its Commercial HTML/RSC metadata lineage separately before making full website-SEO parity claims.

## Safety and original owner release

The **existing** `scripts.owner_publish_saas_evidence_20261025 --preflight` returns `SITE_RELEASE_HELD_NO_PUBLICATION / LIVE_SITE_NOT_MATCHING_APPROVED_PIN`. Its pinned 672-file/2-route/10-asset publisher and founder-approval hash **cannot be reused** on this materially different 670-file candidate.

Before any deployment, the original ASTRA website owner must independently:
1. Verify authorisation and provenance for the five newer public files; preserve them, reconcile the Commercial title discrepancy.
2. Review exact new route HTML/RSC and eight hashed assets, and complete existing desktop/mobile, brand, privacy, consent, public route and navigation acceptance.
3. Obtain new founder approval for this exact revised payload (earlier consent belongs to the old 672-file candidate), separate original-owner signoff, and root-protected rollback indexed against the **current** live 662-file source.
4. Prepare/review an exact guarded root publisher for the revised two-route/eight-asset payload, with idempotency/rollback and post-publication live byte verification. Do **not** run the original incompatible publisher or cherry-pick the full earned-media branch.
5. After a genuinely approved release, verify origin and public HTTP route, RSC, browser JS, consented real buyer response and original Smart CRM tenant evidence. Never generate a synthetic valid buyer or claim revenue from a page view.

Source scripts in this staged branch:

```bash
cd /home/ubuntu/empire_worktrees/earned_media_advisory_bridge_20261025

PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.prepare_earned_media_saas_rebased_union_20261026 --verify-private

node scripts/qa_earned_media_saas_rebased_browser_getonly_20261026.mjs
```

Both are read-only with respect to production. The browser launcher runs a temporary loopback server and headless Chrome, then terminates both. The `--prepare-private` option cannot overwrite a previously created candidate. No service, Cron, DNS, Cloudflare, live database, mail, payment, or public files are modified.

**Machine pickup:** `docs/website/release_candidates/EARNED_MEDIA_SAAS_REBASED_ASTRA_PICKUP_20261026.json`.

**Owner issue:** [EmpireOS GitHub #103](https://github.com/empireaipredictiverevenue-coder/empire_os/issues/103), same original release review channel. An issue comment is a request for owner review, not proof of acknowledgement or delegated deployment authority.


## Stage 10 — verified full-size private backup and recovery (26 October 2026)

The revised 670-file private candidate is still **not live**. The current 662-file public site matches the unmodified baseline. ASTRA's old publisher is pinned to its superseded **10-asset** candidate and old founder/owner hash receipts; it cannot be used on the new 8-asset payload. No original website owner root deployment command or production-service change has been invoked.

**An independent, user-owned private archive of the live 662-file baseline was created** at:
`/home/ubuntu/empire_releases/earned_media_saas_union_20261026/private_backup_rehearsal/pre_release_662_20261026.tar.gz`.
Its SHA-256 is `8d80f0d679a5c97d4ed71487d8b6b3c72cdcb44a8fece36100b27321530963ef`. It is mode 0600, owned by the normal Ubuntu user (NOT root), about 11MB compressed, and was verified using exact safe-member file-by-file SHA-256 against all **662 live files** (27,559,678 bytes uncompressed). The audit rejects duplicate/nonregular/path-traversal/changed/missing members. This archive is a **development recovery test artifact only**, not the production `/var/backups/empire-website` root-owned approved rollback.

**Full-sized isolated rehearsal**, using a disposable temp tree under the private release folder and the actual current 662 baseline:
1. Copy all 662 live site files into the disposable directory; compare SHA index with original.
2. Overlay only the two new `predictive-revenue.html` / `predictive-revenue.txt` bytes and eight exact new immutable assets; compare all **670 file hashes** with the independently built offline candidate. All 660 other original files and five newer owner pages remained untouched.
3. Simulate a failed postpublication check; remove the eight new temporary assets and recover both original route files from the independently verified private archive. The resulting **662-file hash index equals the entire original source**.
4. Re-read the actual live site and offline candidate SHA indices to verify no source drift or mutations.

Evidence: `docs/website/release_candidates/EARNED_MEDIA_SAAS_PRIVATE_RESTORE_REHEARSAL_20261026.json`. Source-only, reusable commands:

```bash
cd /home/ubuntu/empire_worktrees/earned_media_advisory_bridge_20261025
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.rehearse_earned_media_saas_private_restore_20261026

PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.prepare_earned_media_saas_rebased_union_20261026 --verify-private
```

Source: `empire_os/earned_media_saas_release_scope.py`, `empire_os/earned_media_saas_private_backup_audit.py`, `scripts/rehearse_earned_media_saas_private_restore_20261026.py`, with `tests/test_earned_media_saas_private_backup_20261026.py`. The rehearsal is not a production publisher and does not test ASTRA's actual privileged atomic-swap implementation under root; it proves full-size private forward and recoverability of these exact bytes.

**Next original owner work (not completed):** independently review Commercial HTML/RSC metadata mismatch and five newer live pages, approve the exact **revised** 670-file source/payload, take a new root-owned full-site rollback under the original owner's control, and scope its existing atomic deploy flow to two replacements plus eight additions. New founder and distinct ASTRA owner approvals are required; old 672-file consent does not carry. Live public after-checks and actual consented buyer-to-tenant Smart CRM evidence must follow any authorised publication.
