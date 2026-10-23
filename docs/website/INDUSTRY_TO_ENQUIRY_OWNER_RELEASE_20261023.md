# Industry → commercial enquiry: existing Website & Growth owner release handoff

23 October 2026. **Staged, NOT publicly deployed.** Existing EmpireOS site and first-party intake only.

## Exact artifact under review

- Source commit: `2fa9213bb` (five-file source/test change; no new CRM, sender or tracker).
- Isolated production build: `/home/ubuntu/empire_worktrees/industry_enquiry_release_review_20261023/apps/empire-public-site/out`.
- Pinned before/after source, route and immutable-asset SHA-256 values:
  `docs/website/release_candidates/INDUSTRY_ENQUIRY_SOURCE_HANDOFF_20261023.json`.
- The **existing owner** auditor `scripts.review_native_buyer_proposal_build_20261020 --read-only` passed against this pinned build. Independent 12 Node tests, 29 first-party Python tests, isolated TypeScript and Next.js static export all passed.

## Production boundary and narrow candidate

The current web root has **653** files. A fresh canonical export has only **135**, because the real site includes independently owned premium/legacy assets and routes. **Never replace or sync the entire export.**

The isolated build proposes replacing exactly the `.html` and `.txt` files for:

- `commercial`
- `industries/roofing`
- `industries/solar`
- `industries/hvac`
- `industries/property`

It also contains exactly **six new** `_next/static/` immutable assets. None of the static paths common to both exports has changed content. Every directly referenced built static asset is available in the staged export; **643** existing live files must remain unmodified.

All five currently served public HTML pages match the current live static tree byte for byte; none yet serves the new `/commercial?entry=...` link. The candidate industry pages do serve the bounded link. The compiled Commercial form transmits only the allowlisted, browser-claimed first-party path within the visitor's consented enquiry. This path is **not** verified search/SEO attribution and must never become a paid conversion.

## Owner-only release decision — still HELD

1. The existing ASTRA Website & Growth release owner reconciles this pinned candidate with any subsequent independently owned website changes, the premium homepage, the `/buy` bridge, roofing guides, privacy/consent and checkout gate. Review mobile form visual parity. A passing compile does not imply visual acceptance.
2. Require founder/owner approval of the exact ten route-file replacements and six additive immutable assets; never interpret earlier guide/publication approvals as blanket website deployment approval.
3. Take a versioned rollback snapshot of the exact ten original route files and verify all their **pre-release** hashes still match the JSON manifest. Fail closed on any discrepancy or new concurrent release.
4. Existing owner publishes **only** the approved exact allowlist through its release mechanism, preserving all 643 other live files; no new service, Cron, GTM agent, traffic tracker, CRM role or payment flow. Do not use an uncontrolled `cp -r out/` or delete-existing-files sync.
5. GET-only smoke audit: source industry routes, Commercial offers API, Commercial form, Predictive Revenue, `/buy`, privacy page, legal/roofing pages, all referenced immutable chunks and all five post-release HTML hashes. Verify existing original checkout/consent holds and rollback on a failed canary.
6. Subsequently wait for a **genuine voluntary customer submission**. Only the existing privileged EmpireDB source/consent owner and independently authenticated Smart CRM tenant owner can verify exact lineage and response permission. Do not send a synthetic POST to turn the first-sale count nonzero.

No production website deployment, synthetic contact, CRM write, outreach, payment activation or Economic Memory claim occurred. This is a hash-locked owner handoff, **not** release authorisation.

## V2 visual preflight and release-candidate supersession

The first isolated browser review exposed a misleading commercial offer category:
`Technical Search Audit` and `Solar Opportunity Map — US` were displayed as
`Digital Avatar — scoped deployment`. This was presentation logic in the
existing Commercial page, not a catalog price or product-authority change.

**Fix:** `758a5a31b` explicitly distinguishes `consultancy`,
`digital_avatar`, and `intelligence_product` in the existing Commercial
interface. Unknown categories now display a neutral scope-review label.
Frontend category regression tests and TypeScript passed. The release candidate
was then rebuilt from this exact commit in the existing isolated worktree.

**V2 manifest — use this one for any subsequent release decision:**
`docs/website/release_candidates/INDUSTRY_ENQUIRY_SOURCE_HANDOFF_20261023_V2.json`

The original manifest remains immutable historical evidence. It is superseded
for publication because it does not include the corrected Commercial label.

Read-only browser QA used headless Chrome at 390×844 mobile and 1440×900 desktop,
with an isolated static-site listener and an explicitly GET-only staging bridge
for the currently published Commercial offers API. Production enquiry POSTs
were not made; the staging bridge explicitly rejects POST with HTTP 405.

Verified:
- Industry CTA is present twice, opens `/commercial?entry=%2Findustries%2Froofing#commercial-enquiry`.
- Browser preserves the claimed source path and renders offer selector, form
  fields, specific-response-consent checkbox and submit control on both sizes.
- No horizontal document overflow at either width.
- Fresh browser session displays intelligence offers as
  `Intelligence product — scoped one-time delivery`.
- The existing `review_native_buyer_proposal_build_20261020` auditor passes
  on the V2 staged export.
- V2's same ten route-file replacement paths and six additive immutable assets
  must be verified against current live SHA-256 before any publication.
- All 643 other live files remain protected by the pinned allowlist.

**Release authority is still not granted.** The owner must review the actual
V2 visual assets, confirm no concurrent Website & Growth changes conflict,
capture the rollback originals, and obtain the explicit founder/owner release
decision before publishing. Do not treat this document, the passing automated
tests or the headless browser review as deployment permission.
