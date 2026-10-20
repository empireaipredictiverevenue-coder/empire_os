# Empire AI — Verified 632-file private flagship + checkout release candidate

20 October 2026. Existing **Website & Growth** owner; read-only prepublication work.
No public website writes, DNS, gateway switch, new server, buyer POST or payment.

## Original evidence and exact held problem

The independently verified full ASTRA cinematic/checkout stage exists at:
`/home/ubuntu/empire_worktrees/flagship_checkout_source_convergence_20261020/apps/empire-public-site/out`.

Its original source + complete 135-file manifest remains valid:
`docs/website/release_candidates/FLAGSHIP_CHECKOUT_COMBINED_STAGE_20261020.json`.
The source contains premium cinematic homepage, 3D assets, original checkout,
native nonbinding commercial proposal and newer roofing/UK route exports.
The stage's prior Chromium owner verification passed desktop and mobile.

The actual public static tree at `/srv/empire_os/apps/empire-public-site/out`
contained **603 regular files** at preflight, made up of several publication
generations. Naively replacing it with only 135 files would silently remove
eight published HTML pages and many prior hashed JS/CSS chunks.

Read-only exact content inventory:

| Property | Observed |
|---|---:|
| Original independently signed stage files | 135 |
| Current live files | 603 |
| Exact identical path+content | 33 |
| Changed overlapping paths | 73 |
| Current-live only paths | 497 |
| Stage-only new paths | 29 |
| New combined candidate files | **632** |
| Overlapping changed RSC/text routing payloads | **56** |
| Live-only hashed JS bundle files retained | **448** |

Eight retained existing published HTML files:
`about.html`, `treasury-proof.html`,
`_next/treasury-proof.html`, `_next/treasury-proof-v2-20261012.html`,
and four pages under `insights/`.
Three stage-only public HTML routes:
`uk/roofing.html`,
`roofing/installation-checklist.html`,
`roofing/replacement-vs-repair.html`.

## What is built and verified

The nonpublishing release-candidate builder is
`scripts/review_flagship_full_export_union_20261020.py`.

It **first** revalidates the original stage's exact source and full static
manifest. It rejects symlinks, unsafe paths, files over the bounded total
size, missing checkout pages and HTML references to missing local assets.
It assembles the private candidate by preserving all existing public static
files before overlaying the exact **135 pinned stage files**. Each candidate
file must match the computed expected SHA256; source inventories must not
change while copying. The builder refuses an existing candidate destination
and never reads or writes transaction, inbox, buyer or payment tables.

The private candidate and receipts live **only** on the authorized server:

- `/home/ubuntu/empire_releases/flagship_checkout_union_20261020/out`
- `/home/ubuntu/empire_releases/flagship_checkout_union_20261020/RELEASE_CANDIDATE_RECEIPT.json`
- `/home/ubuntu/empire_releases/flagship_checkout_union_20261020/BROWSER_ROUTE_EVIDENCE.json`

The 632-file candidate is approximately **28 MB** and hash-attested.
Zero referenced local static assets are missing from the 19 HTML pages.
No external script tags were added. No public files were changed.

`scripts/review_flagship_union_browser_20261020.cjs` runs private
Chromium against a temporary localhost static server. It reuses the
existing checkout's **real public GET-only APIs** for catalog, tiers and
brokerage while substituting only the four safe nonbinding offer options.
It blocks all non-GET requests and all external browser requests.
It never submits a commercial form, creates a buyer, issues an order
or invokes any BSC payment mutation.

Tested at **1440px and 390px**:

- 12 of 12 route checks passed: homepage, checkout, commercial, about,
  existing revenue-assessment insight and new roofing guide.
- 4 of 4 interactive navigation checks passed: `/buy` to
  `/commercial`, `/about` to `/buy` at both viewports.
- 0 page errors, 0 missing assets, 0 blocked external requests,
  0 buyer POST attempts and 0 payment actions.
- 12 existing public GET-only service requests succeeded.
- The original isolated stage's 135-file source/build receipt still passes.

Mobile's first navigation trial clicked a hidden header anchor and timed
out. This was an auditor selection issue: choosing a visible, rendered link
passes both mobile journeys. No live website source was edited for this fix.

## Governance and outstanding release holds

**This combined export is still a MIXED-GENERATION candidate.** Older JS and
routing artifacts are retained intentionally for other published pages,
while newer checkout, homepage and RSC payloads replace the matching paths.
The 12 page checks and four navigation checks are bounded technical smoke
tests, **not** an exhaustive safety guarantee for all 632 files, all live
legacy pages, SEO, privacy policies, founder-approved visual design or
production rollout.

Candidate receipt explicitly sets:

- `new_public_release_authorized=false`
- `mixed_next_build_routing_navigation_review_required=true`
- `legacy_unreviewed_routes_included=true`
- `payment_execution=false`
- `public_files_modified=false`.

The immutable **13 October buyer checkout HTML manifest remains held** and
must not be repinned or marked passing. Before live publication, the existing
website owner must:

1. Review the complete intended flagship/browser visual output including
   820px and 320px and key older insight, privacy/terms and mobile routes;
   verify branding, 3D fallbacks, accessibility and static RSC transitions.
2. Review which of the 497 live-only files are intentional compatibility
   assets rather than accidentally retained scripts, and accept an explicit
   mixed-generation release or produce a clean owner-attested full rebuild.
3. Take a separate root-protected preproduction backup and verify a rollback
   procedure before switching the live static tree.
4. Issue a **new versioned** public website/checkout release receipt
   independently approved for those exact bytes. Never mutate the 13 October
   artifact to make an old canary green.
5. Deploy with the existing website owner and verify actual
   `/`, `/buy`, `/commercial`, legacy pages, RSC navigation,
   consent-gated first-party form routes and buyer status from public.
6. Reconcile or formally supersede the original checkout release canary
   through a reviewed new-version contract; don't bypass that old security
   gate just because the new build has a newer hash.
7. Use a real opted-in enquiry and original CRM tenant/source evidence for
   end-to-end sales proof. No synthetic lead/order/payment production write.

## Exact nonpublishing operator commands

```bash
cd /srv/empire_os

PYTHONPATH=. .venv/bin/python -B \
  -m scripts.review_flagship_full_export_union_20261020 --read-only

PYTHONPATH=. .venv/bin/python -B \
  -m scripts.review_flagship_full_export_union_20261020 --verify-private-candidate

node scripts/review_flagship_union_browser_20261020.cjs
```

The preparation command is one-time, explicitly nondeploying:

`PYTHONPATH=. .venv/bin/python -B -m scripts.review_flagship_full_export_union_20261020 --prepare-private-candidate`.

Do not rerun it over the existing candidate; the script refuses replacement.

**Ownership:** Website & Growth. Existing Ops Core monitors the historical
checkout HTML hold. Revenue & Buyers retains the first real buyer task.
No fourth general chat, no new timer, no paid traffic, no false sale.


## Additional original public rollback custody

After the release-preparation source commit, a separate root-protected,
read-only archive of the existing public static folder was created:

- `/var/backups/empire-website/flagship_current_live_20261020_before_union.tar`
- `/var/backups/empire-website/flagship_current_live_20261020_before_union.tar.sha256`

The archive is root-owned mode 0600 and contains **603** original live
static files (about 25.5 MB). The web and checkout services remained
active. This is a **reference recovery copy**, not authority to overwrite
the public website, and should be superseded by a fresh, owner-reviewed
pre-switch snapshot if any live static file changes before eventual
deployment. No rollback has been invoked.
