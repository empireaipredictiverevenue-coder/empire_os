# Empire AI Solar and Commercial premium redesign — original website owner

26 October 2026. Founder rejected the dated Solar page and asked for the Commercial page to be redesigned too. This is ONE paired static-site review candidate; do not run an alternative website owner or publisher.

## Precisely three application source paths

- New src/components/SolarIntelligenceExperience.tsx only used for solar.
- Existing src/app/industries/[slug]/page.tsx branches on solar only; other sectors preserve original template.
- Existing src/app/commercial/page.tsx presentation redone, original form and offers loading unchanged.

These paths are relative to apps/empire-public-site. No changes to original gateway, EmpireDB, consent, payment, customer data or SEO dashboard.

## Visual and commercial requirements

Premium Empire navy/blue/warm-gold, existing brand and first-party solar sunset and flagship atrium assets. Solar tells the evidence-to-commercial-decision story with its own hero and buyer qualification narrative rather than the generic lime-green orb. Commercial puts a B2B scoped proposal, original approved offers and real commercial consent first, while keeping the premium brokerage and TAM evidence guides.

Original Commercial function from state declarations through pre-render return, including the approved GET offer allowlist, POST request fields, bounded claimedEntryForReview, crypto idempotency, anti-repeat, consent, errors and honeypot, remains exactly unchanged. The original one-form structure, privacy notice, dynamic prices and source-aware Solar CTAs remain. Solar is a research page with no separate lead form. No invented inventory, actual customer volume, trade agreements, paid conversions or realised revenue.

## Source and packet release

The source is committed in the isolated website_solar_commercial_premium_20261026 worktree. Next.js 16.3.5 Webpack static production build, TypeScript and 19 generated routes succeeded.

The complete rebuilt out directory MUST NOT be published: rebuilding changes unrelated generated HTML and risks other owners. Private candidate packet at /home/ubuntu/empire_releases/website_solar_commercial_premium_20261026_candidate has ONLY the two proposed HTML pages, their eight corresponding Next.js route-data TXT sidecars, additive non-colliding hashed assets, original preimages of those ten route files and a SHA-256 manifest. The 60 other rebuilt TXT sidecars and 16 other rebuilt HTML files are EXCLUDED. Original /commercial and /industries/solar public HTTPS both exactly matched repository out before candidate staging.

Before publishing, the original ASTRA website owner must check the staged source hashes, exact public baseline, mobile/browser appearance, commercial/legal copy, unchanged first-party form and two-page/asset scope, then handle backup, publish and independent rollback/live readback through its own release operator. Staging is not an activation or final founder visual acceptance. No production mutations, Google indexing submissions, outbound or payment were performed.

An existing unrelated industry navigation test fails on unchanged production: it demands a literal /commercial href instead of the already-deployed source-aware link and expects existing /uk/roofing to be absent. It is not a new redesign failure and should be repaired by its own test owner without discarding the source-aware attribution implementation.
