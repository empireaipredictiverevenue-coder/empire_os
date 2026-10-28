# Chicago microsite — original ASTRA owner acceptance (28 Oct 2026)

**Single canonical original website review:** https://github.com/empireaipredictiverevenue-coder/empire_os/pull/148
**Tracked issue:** https://github.com/empireaipredictiverevenue-coder/empire_os/issues/138
**Current state:** `SOURCE_TO_EXPORT_AND_MEDIA_QA_PASS` — **no original release authority, no public site, no revenue**.

This is not another website generator, new route, scheduled agent, marketing pipeline or owner role. It extends the existing original ASTRA PR with a **read-only verifier** that reconciles the source, corrected metadata, final photographic page and original Chromium/4K screenshots into a single byte-verified owner handoff.

## Exact canonical asset chain

| Stage | Exact SHA-256 |
| --- | --- |
| V10 source-backed Chicago citywide pilot, held unpublished | `3ee2f8d08d12d306ab3842b3cb5b041d34fb340f2f6a8d8a898821b2200293a0` |
| V16 original-site title/meta/H1 corrected export | `93c9f75a56b93cf4fde40656d177d734bf2814afd39ffe84bfd4d71555b15275` |
| **Final V17 owner-review HTML**, 387,684 bytes, five images | `1ed1e468a51db0de0f633d955f86b6283b396924db71219816dd9c379dd25c88` |
| Separately rendered native 3840×2160 photographic review | `7d7b864877c9a40c49e483f8717d2c121b8afb6d90e54b3e197f1357a41cf916` |

The original candidate ID remains `microsite_c4c5a13b626d293fe15c`. The proposed one-page first-party route `/research/campaign_ce77b7b6230b2c29f8ede779` is **not deployed**.

## Single read-only owner verification

```bash
cd /home/ubuntu/empire_worktrees/chicago_original_gateway_owner_integration_20261027
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /srv/empire_os/.venv/bin/python -B - <<'PY'
from pathlib import Path
import json
from empire_os.microsite_owner_evidence_chain import verify_chain
print(json.dumps(verify_chain(Path("/home/ubuntu/empire_releases")), indent=2))
PY
```

It must fail if the original V10 site source, original held manifest, V16 export, V17 HTML, **any of five Wikimedia photo source bytes**, photo attribution/source URL/licence, original SHA-bound browser screenshot, original noindex layout, or exact high-resolution 4K browser receipt changes. The verifier never treats synthetic review fixtures or boolean approval flags as human rights signoff.

**Evidence receipts** are private on EmpireOS:
`/home/ubuntu/empire_releases/chicago_original_owner_evidence_final_review_20261027/ORIGINAL_SITE_SOURCE_TO_RELEASE_READBACK_20261028.json`.

Observed 28 October 2026: `SOURCE_TO_EXPORT_AND_MEDIA_QA_PASS`, 3 stages of desktop/mobile browser proof verified, actual 4K proof verified, five licence-bound image file identities verified, and **137 original website/gateway/source/photo tests passed** (one existing AnyIO dependency deprecation warning). Production release files and the original five campaign routes remain untouched.

## What remains outstanding — real owner authority, not technical work

1. **Original SEO/source owner** must approve source claim accuracy, Chicago building permit jurisdiction and useful publication/indexing rationale. The private page is `noindex,nofollow,noarchive`. Source-file correctness does not equal SEO approval.
2. **Original brand/media owner** must verify commercial distribution rights for the original orbital-A PNG and five exact adapted Wikimedia photographs (especially CC BY-SA attribution/change disclosure/share-alike obligations), including the two earlier Unsplash imagery masters. The presence of a Commons licence/credit and source byte hash is not a signed rights review. The live flagship brand owner record still lists `media_source_rights_cleared=false`, native editable master unverified.
3. **Original ASTRA website/release owner** must reconcile draft PR #148 with live production (remote base is stale relative to the dirty working tree), accept the guarded original 5+one code change, prepare the exact reviewed HTML as an approved first-party staged asset, record the owner decision through original authority, supervise deployment and verify actual GET/HEAD/hash readback with the existing V15 readback tool. The website owner signoff record still says false.
4. Only after real publishing, the existing measurement owners may connect actual Search Console, first-party consented analytics, accepted CRM outcomes and independently verified settlements. Revenue is not inferred from a page preview.

**Do not merge or deploy automatically; do not manufacture approvals or create a second timer/owner/system.** Keep all original five research campaigns intact.
