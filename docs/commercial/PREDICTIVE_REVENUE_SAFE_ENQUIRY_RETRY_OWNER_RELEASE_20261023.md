# Predictive Revenue first-party form retry integrity — release handoff

23 October 2026 | Existing Empire AI website | Staged code only, NOT published

## Actual defect and narrow remedy

The current Predictive Revenue browser form generated a brand-new idempotency key for each POST attempt and fell back to timestamp + Math.random if crypto.randomUUID was unavailable. After a successful POST with a lost response, a visitor retry could therefore use a different ingest key. This was a retry-safety issue, NOT evidence of any real duplicate buyer.

The Commercial form already implements secure in-tab request-key reuse. The Predictive Revenue form now uses an equivalent source-local helper, with its own complete input fingerprint: approved product, company, email, company domain, industry, geography, annual revenue band, desired outcome, sorted integration selections, response-consent checkbox, and honeypot. Identical retry retains one key; changed details rotate key. crypto.randomUUID is required; no weak fallback. No cookies, persistent storage, analytics or server modifications.

After an independently confirmed deployment_interest_recorded response containing a non-empty original prospect ID, it disables resubmission until page reload. Ambiguous network failure keeps safe retry. Form explicitly states no order or payment was placed and retains existing purpose-specific response consent and privacy link.

## Verification performed

- node --test tests/test_predictive_interest_attempt.mjs tests/test_commercial_interest_attempt.mjs: 8 passed.
- Existing Python checkout and Predictive Revenue domain tests: 10 passed.
- TypeScript project tsc --noEmit: passed.
- No browser POST, database mutation, customer row, outbound, payment, public build publication, service change or live rollout in this work.

## Existing owner's release gate

Have the existing website release owner inspect the exact source diff and build against current pinned public assets. Check mobile form UX, actual origin/same-origin headers and catalogue response using read-only or controlled staging fixtures only. Reconcile any concurrent website changes and preserve the mixed-generation public static tree, legal pages, source consent and checkout restrictions. Publish only with explicit website-owner/founder release authorisation and pre/post rollback verification. After publication, measure authentic user-initiated submissions via original canonical EmpireDB/tenant CRM readers; do not manufacture a lead.

## Separate source-of-truth observation

The existing root-operated Ops Control verified 0 canonical first-party sales acquisitions (commercial 0, Predictive Revenue 0) as of the checked 23 October snapshot. Original GTM already receives this via the existing observer. The Ops snapshot directory is currently owned by ubuntu and writable by ubuntu, which means a non-privileged replacement can temporarily render the source truth unverified before the root owner refreshes it. GTM fails closed for untrusted snapshots. The Ops owner must own an explicit permission and single-writer review; do not change shared runtime directory ownership or service privileges here. The original root-owned snapshot's verified zero means there is no demonstrated sales-to-CRM missing link, only the lack of recorded genuine submissions in these two sources.

Next commercial action: existing SEO/organic owner attracts legitimately interested companies to /commercial or /predictive-revenue. The existing first-party form receives actual buyer permission. Original EmpireDB and tenant CRM verify exact identity, consent, current suppression and commercial fit before founder-approved contact. Neither search impressions nor JEV pain themes are buyers.
