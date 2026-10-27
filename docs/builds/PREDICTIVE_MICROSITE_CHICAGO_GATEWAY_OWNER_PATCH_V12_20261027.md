# Chicago V12 — Minimal Original Gateway Route Extension (OWNER REVIEW ONLY)

**Date:** 27 October 2026
**Branch:** `agent/predictive-microsite-slopmonster-20261026`
**State:** `OWNER_RELEASE_PATCH_READY_FOR_REVIEW` / Chicago route **NOT LIVE**.

## Why this change

The original first-party FastAPI gateway already owns `GET /research/{campaign_id}` and `HEAD /research/{campaign_id}`. Its existing `empire_os.owned_campaign_release.released_html()` reads a separately verified original manifest containing **exactly five** production research campaigns. That original exactly-five gate must be preserved intact; trying to insert a sixth record would invalidate all five previously released campaigns.

The proposed V12 owner-reviewed approach **does not touch the gateway, its public ports, those five campaigns, or its original release manifest**.

Instead, `empire_os/microsite_original_gateway_addendum_v12.py` is a **dormant importable helper** which can return exactly one additional independently approved asset **only after original owner adoption and independently issued approvals**. It is not imported by the live gateway and does not create a file or write any production state. All path/campaign IDs and the original V10 source preview SHA are fixed in code.

Proposed unique route (NOT presently deployed):
`/research/campaign_ce77b7b6230b2c29f8ede779`.

### Minimum owner-only patch (review, do not apply as-is without owner authority)

At the **end** of existing `empire_os.owned_campaign_release.released_html(campaign_id, root=ROOT)`, *after* its original five-campaign loop, and before the final `return None`, the original site owner would insert:

```python
    from empire_os.microsite_original_gateway_addendum_v12 import original_owner_chicago_html
    return original_owner_chicago_html(campaign_id, root=root)
```

No `public_gateway.py` route change, new publishing service, DB schema, ad/phone/CRM service, or file mutation is required. **The existing five-item `load_release()` condition stays untouched**.

### Required original-owner controlled evidence

The dormant extension must reject until ALL are true:

1. Existing actual `load_release(root)` and `released_paths(root)` still verify exactly five unchanged live campaign paths; not caller-created test data.
2. An original-owner controlled, one-candidate immutable receipt is present at `runtime/public_website/one_chicago_research_release.json`, bound to the original five-release SHA and the exact Chicago source preview SHA `3ee2f8d08d12d306ab3842b3cb5b041d34fb340f2f6a8d8a898821b2200293a0`.
3. Independent SEO, brand-artwork rights and website publication decisions are present as **separate original-owner-custodied** documents under `runtime/public_website/approvals/`, all scoped to the exact candidate, source SHA and deployed page SHA, with actual owner provenance. The module validates only records and hashes; **a JSON `owner_ref` is not a cryptographic signature or independent proof of human approval**. Original owner must enforce and verify approval identity and file custody, not assume arbitrary submitted JSON equals consent.
4. Original website owner creates exactly one HTML export at `apps/empire-public-site/out/research/campaign_ce77b7b6230b2c29f8ede779.html`, binds exact bytes to receipt digest, and independently verifies external live HTTP deployment/readback. An unsupported true boolean in a release draft is not an acceptable substitute for real external readback evidence.
5. The page is noindex, without collection forms, scripts, or external network dependencies; no payments, paid spend or outbound is activated.
6. No source-preview SHA, deployed-asset SHA, campaign ID or approval-scope conflict is allowed. No implicit fallback to serving unapproved site files.

## Demonstrated real state, 27 October 2026

Read-only check against original code and its real production root `/srv/empire_os` found:

- `load_release() != None` and `len(released_paths()) == 5`.
- Each of the 5 incumbents still returns actual HTML through original `released_html()`.
- New candidate `released_html(CAMPAIGN_ID) is None` and proposed V12 extension is **also None** (correct fail-closed behaviour).
- 24 V12 controlled original-owner-injected fixture tests passed, including successful return only with fixture approvals, missing SEO/brand/website approvals, invalid source SHA, changed deployed asset, missing original five, symlinks, forms, and script injection. Fixture approvals are **not evidence** that real owners approved release.
- V10 original-brand readback 250 earlier targeted regressions passed; final V12 regression suite run must be recorded separately.

## Source freshness

Five official source references checked in current public research; source evidence strongly supports the Chicago permit eligibility (including 25% repairs and structural exceptions), public permit application limitations (36-month history), Illinois licence lookup and Census distinction between ZCTAs and USPS ZIPs. **This is technical research input, not the independent SEO owner publication approval**. Do not assert an original SEO human made a decision when they have not.

## Next original-owner action

Review this optional dormant helper and proposed two-line original-file fallback. If accepted, original **website release owner** coordinates exact route extension with the **SEO** and **brand/public image distribution** owners, issues real role-bound records through their existing authority, supervises exact site export and HTTP readback, and then separately authorizes deployment. The first five campaigns must remain unchanged throughout. This marketing worktree must not merge into the dirty `/srv/empire_os` branch directly.

Do not send traffic or count conversions/revenue until a genuinely deployed original-site page and original measurement evidence exist.

Issue: https://github.com/empireaipredictiverevenue-coder/empire_os/issues/138
