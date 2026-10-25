# Predictive Revenue SaaS — isolated export and visual acceptance release packet

25 October 2026 | Original public website owner | **STAGED / NOT PUBLISHED**

## Source and build

Source baseline: EmpireOS branch `agent/data-cloud-wave4`, component from commit `d43f9f2d8` plus this reviewed layout correction. Original `/predictive-revenue` deployment-interest endpoint, server-side consent, idempotency, published product/pricing catalogue, country/industry input and identity rules are untouched. Only the positioning and hero anchor for `SaaSRevenueEvidencePreview` changed: the full free example now appears after the existing enquiry form, which remains reachable sooner on phones.

The site uses Next.js static `output: "export"`. The independent build ran at `/home/ubuntu/empire_worktrees/saas_evidence_preview_20261025/apps/empire-public-site`, **not in the active public output directory**. Build command: `NEXT_TELEMETRY_DISABLED=1 npm run build -- --webpack`. Next 16.3.5: production webpack compilation passed, TypeScript passed, and 19 static routes were generated. The independent export has 154 files before adding the temporary GET-only catalogue fixture. It is **not** a replacement for the current 662-file mixed-generation live site.

## Genuine browser acceptance (isolated localhost)

Static export was served temporarily at `127.0.0.1:28731` with an ordinary HTTP GET-only server; Chrome for Testing 153 headless produced screenshots in `/home/ubuntu/empire_worktrees/saas_evidence_preview_20261025/preview_visual_receipts/`:

- `saas_desktop_fixed_catalogue_1440.png` — 1440×1080 desktop
- `saas_mobile_fixed_catalogue_390.png` — 390×1800 mobile
- `saas_mobile_tall_390.png` — earlier version used to identify a **mobile form-displacement conversion issue**, which was corrected before the final candidate
- The browser acceptance script `preview_visual_receipts/run_saas_browser_acceptance.mjs` uses Chrome DevTools Protocol against this local origin. The final run exited **zero** and verified 1440px and 390px viewport, no horizontal overflow, form before long sample, correct original form inputs, live public catalogue fixture, all 3 tabs hydrated, the CTA anchor returning to the original form, and **zero POST requests**. No actual buyer data was sent.
- The catalogue fixture was retrieved by **public GET** of `https://empire-ai.co.uk/v1/checkout/predictive-revenue/products` (5 products) and temporarily placed *only* in the isolated export for realistic client-side rendering. The fixture was explicitly **excluded from the release candidate**. It is not a payment, order or prospect.

## Safe surgical union: prepared offline

Owner-approved current live inventory: 662 files, byte-for-byte consistent with `/home/ubuntu/empire_releases/seo_saas_20261024_after_v2/REBASED_CANDIDATE_RECEIPT.json`. A fresh independent audit before and after union confirmed it stayed unchanged.

The corrected offline candidate at `/home/ubuntu/empire_worktrees/saas_evidence_preview_20261025/candidate_union_20261025/` contains **672 files**: 660 wholly unchanged prior files, exactly **two paired replacements** `predictive-revenue.html` and `predictive-revenue.txt` (Next.js RSC navigation payload), and **10 new noncolliding hashed assets** under `_next/static`. The RSC payload was missing from the first candidate; a later independent inspection caught and corrected this. Preserving the old `.txt` could have served stale route code during navigation. No other prior file was changed, zero hashed asset collisions, zero missing referenced resources and no staging catalogue fixture was included.

- Previous HTML SHA-256: `7144c99317d5a38d2f44e94bdd992bb26a6544a1626a0cab8973d25b9e0c9e9a`.
- Candidate HTML SHA-256: `1eaaa66e633967d553b18ebe3ed5180af36a555778c2efce4235679e1fc31053`.
- Previous RSC SHA-256: `6d730f3f9c34a0052c944e05bbddfcaa940fcbdd5056d7dc61afb1ef6c9d9f43`.
- Candidate RSC SHA-256: `9ec0c0306c41b0b8c3311027d662abe9334033d46a8fba1b660a98857c988563`.

This paired release is still **staged, not approved and not live**.

Machine-readable evidence: `/home/ubuntu/empire_worktrees/saas_evidence_preview_20261025/preview_visual_receipts/saas_evidence_union_manifest.json`. Manifest explicitly reports `release_owner_approved=false`, `site_published=false` and `live_site_mutated=false`. **The updated manifest supersedes the earlier single-HTML manifest.** The site owner can rerun the newly committed fail-closed read-only verifier: `cd /srv/empire_os && .venv/bin/python -B -m scripts.review_saas_evidence_release_candidate_20261025` (20 new focused tests). The verifier checks the original 662-file approved hash pin, 672-file candidate, both new route hashes, 10 new hashed files, no other changed old files, 14 embedded resource references and the withheld publication gates.

## Go-live gates still held

1. Original public website owner independently verifies the 672-file union against current live inventory **at the moment of release**, including legal/privacy, mobile design and any newer production changes. Do not deploy from a stale pin.
2. Capture specific founder/website-owner permission for publishing this exact **paired HTML+RSC route and 10 new-only static assets**, and pin a private rollback of both original route payloads plus protected complete site backups before any write.
3. Only then use the existing approved surgical release workflow with before/after GET and hash readback; never overwrite the live tree with the smaller standalone export and never touch other agents' routes.
4. After genuine visitors enquire, review authentic consent-bound evidence through the existing original Ops acquisition and Smart CRM ownership path. Do not manufacture leads, contacts, messages, payments or conversion improvement.

**Commercial reality:** Clueso LinkedIn first-touch is founder-reported sent, platform confirmation/reply unverified; canonical first-party acquisition snapshot observed zero in the latest read. There is no confirmed new buyer, sale or realised revenue from this interface upgrade.

## 25 October — paired Next.js route reconciliation and repeatable owner preflight

An independent second inspection found the first offline candidate had replaced only the HTML while **retaining the old `predictive-revenue.txt` RSC navigation payload**. The old payload pointed to `page-8a641c1798fea86e.js`; the newly built route points to `page-119dcf00a0b5a51e.js`. The candidate has been corrected to replace both file payloads. The corrected 672-file inventory is: **660 identical existing files, 2 replacement route files, 10 new hashed static assets**. Live public assets remain exactly matched to the previously approved 662-file hash inventory.

A browser QA copy (never the actual candidate tree) at `/home/ubuntu/empire_worktrees/saas_evidence_preview_20261025/union_browser_qa_20261025/` hosted a read-only fixture of the live public Predictive Revenue catalogue and the two public Commercial/Brokerage catalogue GET endpoints needed by the old `/commercial` page. The genuine Chrome-for-Testing navigation started on old `/commercial.html`, clicked the first-party Predictive Revenue link, and finished at `/predictive-revenue` rendering the new example and unchanged form. Outcome `MIXED_GENERATION_NAVIGATION_ACCEPTANCE_PASS`, browser HTTP errors **0**, JavaScript exceptions **0**, POST requests **0**. The RSC text was separately fetched by exact local HTTP 200 and checked against the new page chunk. The browser did not itself request a `.txt` route during this navigation (full-page navigation can satisfy the visible check); this is **not evidence that all SPA-prefetch paths have been exercised**. Machine receipt: `preview_visual_receipts/saas_union_navigation_QA_20261025.json` in that isolated worktree.

The new read-only owner preflight `scripts/review_saas_evidence_release_candidate_20261025.py` verifies current live files against the previously approved complete baseline, detects unexpected payload replacements, missing assets, stale RSC chunks, catalogue fixture leaks, symlinks and unmatched manifests, and always returns `publication_authorized=false`. Its focused tests are in `tests/test_saas_evidence_paired_release_preflight_20261025.py` (**20 passed**). It is review tooling, not a release script; it performs no production writes or automatic deployment.

This QA supersedes all earlier suggestions that the SaaS candidate should publish the HTML alone. Original owner still requires an explicit exact-scope go-live approval, fresh protected rollback and appropriate independent prepublish acceptance. No publication occurred.
