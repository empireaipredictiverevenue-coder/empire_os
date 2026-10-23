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
