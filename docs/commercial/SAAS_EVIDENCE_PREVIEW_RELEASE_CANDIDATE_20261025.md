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

The offline candidate at `/home/ubuntu/empire_worktrees/saas_evidence_preview_20261025/candidate_union_20261025/` contains **672 files**: 661 wholly unchanged prior files, exactly one replacement `predictive-revenue.html`, and **10 new noncolliding hashed assets** under `_next/static`. No other prior file was changed, zero hashed asset collisions, zero missing referenced resources, and no staging catalogue fixture was included. Prior HTML SHA-256: `7144c99317d5a38d2f44e94bdd992bb26a6544a1626a0cab8973d25b9e0c9e9a`. Candidate HTML SHA-256: `1eaaa66e633967d553b18ebe3ed5180af36a555778c2efce4235679e1fc31053`.

Machine-readable evidence: `/home/ubuntu/empire_worktrees/saas_evidence_preview_20261025/preview_visual_receipts/saas_evidence_union_manifest.json`. Manifest explicitly reports `release_owner_approved=false`, `site_published=false`, and `live_site_mutated=false`.

## Go-live gates still held

1. Original public website owner independently verifies the 672-file union against current live inventory **at the moment of release**, including legal/privacy, mobile design and any newer production changes. Do not deploy from a stale pin.
2. Capture specific founder/website-owner permission for publishing this exact single-page-and-new-only-assets candidate and pin a private rollback of the current exact HTML/assets.
3. Only then use the existing approved surgical release workflow with before/after GET and hash readback; never overwrite the live tree with the smaller standalone export and never touch other agents' routes.
4. After genuine visitors enquire, review authentic consent-bound evidence through the existing original Ops acquisition and Smart CRM ownership path. Do not manufacture leads, contacts, messages, payments or conversion improvement.

**Commercial reality:** Clueso LinkedIn first-touch is founder-reported sent, platform confirmation/reply unverified; canonical first-party acquisition snapshot observed zero in the latest read. There is no confirmed new buyer, sale or realised revenue from this interface upgrade.
