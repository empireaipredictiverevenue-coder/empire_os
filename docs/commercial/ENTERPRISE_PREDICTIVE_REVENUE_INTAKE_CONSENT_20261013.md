# Empire AI — Predictive Revenue enterprise enquiry consent release
13 October 2026 · isolated source-only candidate · **NOT DEPLOYED**

## Problem confirmed against existing production contract
The live, publicly accessible `/predictive-revenue` page renders the founder-approved $25,000–$250,000+ deployment catalogue and contains a buyer-interest form. The corresponding `POST /v1/checkout/predictive-revenue/interests` is same-origin and rate limited, but the initial page/API implementation did **not** ask for or record explicit specific-response contact consent. In contrast, the existing `/commercial` enquiry lane already records a timestamped explicit consent object and uses a hidden honeypot. We must not treat a buyer-initiated form or an existing sent email as automatic consent to unsolicited/ongoing marketing.

This fix reuses the existing first-party form and `ingest_prospect_atomic` path; no new CRM, DB schema, scheduled task, sender, buyer campaign or financial product is created.

## Smallest bounded changes
1. `apps/empire-public-site/src/app/predictive-revenue/page.tsx`: add an unchecked, required contact-consent checkbox scoped to **one specific enquiry**, not marketing; add hidden honeypot; send both to the existing API; disallow submit without consent.
2. `empire_os/self_serve_checkout_api.py`: require `contact_consent`, accept bounded `website` honeypot field, reject absent/false consent and filled honeypot with HTTP 422 **before** any call to the buyer intake function.
3. `empire_os/predictive_revenue_self_serve.py`: use strict literal-true opt-in and empty honeypot; refuse untrusted/naive time; attach UTC source/time `contact_consent_evidence` exactly analogous to the current first-party commercial-sales contract; retain `automatic_followup_authorized=false`, `payment_action=false`, `execution_authority=none`.
4. Align only the existing affected regression fixtures; add explicit offline tests proving rejects **before** an EmpireDB RPC, strict consent, timestamp integrity, frontend checkbox presence and a genuine consent capture without sending.

## Independent verification
- First focused tests: **51 passed**.
- Expanded Python suite: **85 passed**, one dependency deprecation warning (Starlette/AnyIO). The first wider run found a single pre-change positive test without `contact_consent`; updated the fixture to the strengthened contract, **not** the enforcement to accommodate it.
- Isolated frontend TypeScript: `tsc --noEmit -p tsconfig.json` **PASS**.
- Full static Next.js production build **PASS** with `next build --webpack`. Default Turbopack build aborted because this isolated worktree temporarily symlinked `node_modules` to a dependency installation outside its filesystem root; **not a source failure**. Webpack was a supported isolated-worktree compatibility mode. No npm install, version bump or dependency update.
- Production checkout/order/payer wallet and live outbound systems: **not modified**. No synthetic valid buyer/DB write, no public activation, no payments, no customer data created.

## Exact release gates for Astra / founder
**This is NOT a green light to deploy.** Live website is undergoing Astra visual changes, and the code was isolated expressly not to overwrite that design or runtime.

- Rebase/merge only after inspecting current modified website files and any subsequent production commits. Apply a minimal conflict-resolved diff, not the entire static export from this worktree.
- Deploy the consent-bearing frontend and stricter internal checkout API as one coordinated release, avoiding a period where old public clients encounter a new required-field contract. Note cached old clients can fail closed with HTTP 422 until refreshed; do **not** silently accept consentless leads to avoid this.
- Confirm GET `/predictive-revenue` and product catalogue; public **invalid-only** POSTs must fail 403/415/422 without hitting a valid production buyer request. No fake legitimate customer enquiry is allowed for testing.
- Verify use of existing first-party contact-consent evidence in founder CRM readback with the first authentic customer submission. This must not be turned into standing outbound marketing authority.
- Exact founder approval still required for any service reload, production static promotion or DB mutation. Existing independent direct BSC order admission and payment-approval policies are untouched.

## Revenue relevance
This improves the ability to make a **lawful, attributable response** to a qualified $25k+ enterprise enquiry. It does **not** create a buyer, contract, recurring managed-service rate, payment collection or recognised revenue. Real £100k MRR requires actual won and fulfilled recurring customer agreements; the enterprise funnel remains nonbinding.

## 13 October later integration and deployment preflight (supersedes 'isolated source-only')
**SOURCE INTEGRATED / PRODUCTION RELOAD HELD.** The existing isolated fix `4930d671` was cherry-picked onto then-current checkout source in new isolated worktree `feature/predictive-consent-release-20261013` as `06d3a0a5`. No source conflicts. It was subsequently merged into canonical `agent/data-cloud-wave4` as **`223c932c`**, preserving unrelated dirty work and payment changes.

- Focused tests in the candidate: **57 PASS**; expanded affected contract set: **59 PASS, 1 SKIP** (preview-only unless export path supplied), one Starlette/AnyIO deprecation warning. Isolated TypeScript `tsc --noEmit` **PASS**.
- Independent full `npm run build -- --webpack` in the isolated candidate: **PASS**, 17 static pages generated. No version upgrade, dependency download, broad site deployment, production build directory replacement or wallet action.
- Original live static `apps/empire-public-site/out/predictive-revenue.html`: 0 checkboxes, self-canonical `https://empire-ai.co.uk/predictive-revenue`. Candidate rendered page: exactly one required consent checkbox, same self-canonical, includes specific-response contact consent text.
- Candidate HTML references 8 existing/new content-hashed Next.js assets. Of them, exactly **2** are not currently present in live `out`; shared already-present assets have identical SHA-256 hashes (no collision).
- A **non-deployed** private stage/backup exists at `/var/tmp/empire_predictive_consent_release_20261013/` with mode-0600 `manifest.json`, original HTML at `before/predictive-revenue.html`, candidate at `after/predictive-revenue.html`, and exactly two required new immutable assets under `assets/`. `mode=PREPARED_NOT_LIVE`, `backend_restart_authorized=false`, `public_page_promotion_authorized=false`; no live files changed by this stage.
- Running `empire-self-serve-checkout.service` entered active state at **2026-10-13 19:49:52 UTC**, PID `1203819`, prior to the new source integration. **Do not treat committed Python source as live backend enforcement until controlled restart and independent HTTP negative-contract readback.**
- New canonical checkout health shows `payment_proposal_authorized=true` and `binding_order_creation_authorized=true`, but `payment_execution=false` and `revenue_recognition=false`. This is an already-existing separately approved controlled BSC order-admission change, **not** part of this consent fix. Do not revert or widen the payment gates while releasing contact consent.

**Next exact gated action:** founder-authorised coordinated restart of only `empire-self-serve-checkout.service` to load merged consent validation, verify invalid-only consent/honeypot POSTs return 422 and service health unchanged, then atomically promote exactly the staged `predictive-revenue.html` and its two non-colliding hashed assets, inspect external HTML and assets, and preserve old-page backups. If any service/API negative-path precondition fails, do not publish the new page; if post-publication checks fail, restore only the exact prior page after SHA match. Protect any newer ASTRA owner updates and checkout functionality from overwrite. No synthetic valid buyer submission, CRM entry, outbound, payment, paid spend or legal/index publication is authorised.

**Status remains:** fix CODE_COMPLETE / main branch committed / fully built / stage checked / **not yet live**.
