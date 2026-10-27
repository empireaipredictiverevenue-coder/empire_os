# Chicago — Original ASTRA Website Owner Integration V14 (DRAFT PR)

Date: 27 October 2026. **Not a deploy request; no public page or owner approvals.**

## Scope

Clean isolated review worktree based on `origin/agent/data-cloud-wave4` at `b1690f609ffa455765fca4e7dd401c1bb5194619`:

`/home/ubuntu/empire_worktrees/chicago_original_gateway_owner_integration_20261027`

Branch `review/chicago-original-gateway-owner-20261027`. The local production `/srv/empire_os` is >1,000 commits ahead with unrelated dirty working files. This review branch is **not merged or applied to production**; the original ASTRA owner must reconcile remote and current live states prior to any change.

## Exact small patch

1. Introduce existing, tested `empire_os/microsite_original_gateway_addendum_v12.py` from the original Chicago workstream. Only one deterministic Chicago campaign ID is eligible, bound to the exact source SHA, existing original five-release SHA, independent SEO/brand/site owner-custodied records and deployed asset SHA. No approvals are supplied by this branch.
2. One optional fallback in original `empire_os.owned_campaign_release.released_html()`, **after** all five incumbent IDs are checked. Keep `load_release()` intentionally **exactly-five**, unchanged.
3. Keep original `GET /research/{campaign_id}`; add explicit `HEAD` parity to this older remote branch, matching current production's already present decorator. No extra web service, router, port or owner.
4. Fix existing test fixture isolation: when validating an empty `tmp_path`, the original gateway was reading the *real five released campaigns* from `/srv/empire_os` and falsely failed. It now injects the test root only for that test.
5. Include original gateway GET/HEAD regression tests and distinct synthetic-only role-record tests. **Test fixture owner references are not real approvals.**

## Observed verification

- Original real `load_release()` PASS; five original `released_paths()` all returned live HTML.
- Proposed Chicago `/research/campaign_ce77b7b6230b2c29f8ede779` correctly returns **404 GET/HEAD** without owner approval.
- Isolated test-only role approvals demonstrate possible admission of exactly one asset; missing one approval → 404. Unknown campaigns → 404.
- Current base with original site release, optional addon, HTTP gateway and test fixture: **104 passed**, one existing AnyIO deprecation warning.
- Original production's immutable five-member receipt SHA-256: `81f5b73b6275b45e64e0869695dcf9d2e220c202739c50b11582a877bcef672a`.
- Chicago draft source SHA-256: `3ee2f8d08d12d306ab3842b3cb5b041d34fb340f2f6a8d8a898821b2200293a0`.
- Existing 4K/desktop/mobile browser QA from V10 remains in private EmpireOS stage. No private logo PNG, artwork, photographer originals or page source HTML is added to this public repo branch.

## Original owner-controlled release responsibilities

- **SEO/source owner** independently validates Chicago city jurisdiction, official source freshness/helpfulness and indexation decision. No exact search-demand proof has been invented.
- **Canonical brand owner** independently clears original orbital-A artwork public-use rights and actual photo license/attribution; do not confuse branding-system approval with unrestricted image release. Native editable vector remains unverified.
- **ASTRA website owner** reviews reconciled branch against actual production HEAD, obtains real independent owner decisions, stages export with real HTML/asset digest, verifies original five before/after, performs controlled publishing with authentic HTTP deployed readback and rollback. The addon should never be activated by arbitrarily minted JSON files.
- **Original measurements** only follow a genuine deployed page: Search Console, consented analytics, CRM accepted enquiries and independently settled money receipts. UNKNOWN remains UNKNOWN.

Do not merge PR until these conditions are fulfilled. No production flags, campaign changes, checkout, paid spend, outbound, or new marketing agents.

Existing single-owner tracker: https://github.com/empireaipredictiverevenue-coder/empire_os/issues/138
