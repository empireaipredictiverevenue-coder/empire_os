# Empire AI consumer opt-in programme — Roofing Cost Guide

20 October 2026. **Built and tested in an isolated worktree, not published; consumer email collection disabled.**

## First useful deliverable

The new /roofing/cost-guide page offers a real, printable five-step homeowner checklist: problem description; written scope; roofing quote cost factors; licensing, insurance and warranties; comparing like-for-like bids. This is general education, not a contractor quote, case study or price guarantee.

A separate, *optional* Empire AI homeowner newsletter form is coded but deliberately fail-closed: it renders only if a first-party `GET /v1/consumer-optin/roofing/status` endpoint returns a signed-off policy-shaped response including:

- `status=OPTIN_COLLECTION_ENABLED`
- `notice_version=roofing-homeowner-updates-v1`
- `subscription_product=EMPIRE_AI_OWN_BRAND_HOMEOWNER_UPDATES`
- `privacy_notice_url=/privacy`

**No such status endpoint has been deployed.** The existing business/agency commercial enquiry RPC and legacy SQLite lead-intake path are not used for homeowner newsletter email addresses. Guide download is ungated; there is never a requirement to agree to marketing or contractor sharing.

The proposed own-brand POST contract, also not deployed, is `POST /v1/consumer-optin/roofing` with explicit unchecked optional-brand checkbox, original notice version and a `optional_named_buyer_referral=false` assertion. The UI only reports an opt-in success if a separate trusted API genuinely returns `OPTIN_RECORDED_PENDING_VERIFICATION`; it does not claim email delivery or add anyone to a marketing list.

## Release and verification

Isolated source worktree: `/home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020`, branch `feature/consumer-optin-roofing-20261020`.

Isolated static Webpack build: `/home/ubuntu/empire_staging/consumer_optin_roofing_20261020`. Next.js 16.3.5 compiled successfully, TypeScript passed and 20 pages exported, including `roofing/cost-guide.html`. Build ID `l-spB9zu77TJH808k5gaj`; page SHA-256 `6a66993cb9e73c22fd95b154169eba71480120f05ca61268976788a8cdb95031`.

Asset collision inspection: 42 staged static assets; 11 existing live asset paths match byte-for-byte, **zero** existing-path conflicts, and 31 assets are new unique hashes. This does **not** independently authorise a public upload.

A local real Chromium test of the isolated build confirmed all five guide cards, absence of subscriber forms when readiness GET returned 404, no synthetic POST, and only GET/HEAD browser requests. An initial smoke mistook HEAD for a write; this was diagnosed and corrected by logging HTTP methods.

**Existing source-owner content control remains enforced**: `public_gateway.py` is amended in the isolated branch to recognise the exact new roofing guide slug via its original `_STATIC_REVIEWED_ROUTES` and `public_roofing_guide` rules. Without the founder/editorial/privacy/approved-page-hash receipt, `GET /roofing/cost-guide` returns noindex 404. The production route currently returns HTTP 404. No production gateway, static site, buyer campaign or CRM service was changed.

## Actual remaining activation work, existing owners only

1. **Website/Editorial/Lead Smart owner:** review the exact wording, source neutrality, no unsubstantiated local prices, roofing coverage distinction and route metadata. Align the homeowner guide with the existing exact SHA reviewed-content release process and current flagship assets; preserve other owner changes. The current gateway's reviewed guide lane intentionally emits noindex and requires buyer/legal approval before public publication.
2. **Privacy/Legal owner:** establish and publicly review the privacy notice applicable to individual consumers, its retention, age/sensitive-data exclusions, unsubscribes, consumer deletion and any identity verification required. Do not assume the general /privacy page covers every new marketing purpose without review.
3. **EmpireDB/CRM owner:** use a dedicated consumer subscription consent store, not the B2B company prospects schema or legacy SQLite. Store the immutable original notice/checkbox evidence with restricted access and dedupe, correction, withdrawal and suppression. **Do not apply a migration without separate database activation approval**. Do not mix subscriber counts into saleable buyer leads.
4. **Email/Subscriber owner:** confirm sender authentication, email verification where selected, actual unsubscribe workflow, delivery receipts, suppression and sane anti-abuse rate limiting.
5. **Buyer Exchange/Sales owner:** a separate named-receiver and channel-specific agreement is needed to transfer any identified consumer to a roofing buyer. Guide download/own-brand subscription do not confer those rights. Buyer pricing, self-qualification, returns and fulfilment require independently agreed terms.

`empire_os/roofing_guide_optin_contract.py` provides a PII-free original-consent receipt reviewer and an activation evidence checklist; it never independently authorises a release, writes a database row or sends email.

## Acceptance commands

```bash
cd /home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_roofing_guide_optin_contract_20261020.py \
  tests/test_roofing_cost_guide_reviewed_release_20261020.py \
  tests/test_lead_smart_legal_review_copy_guard.py
```

**Commercial truth:** we have a complete informational lead magnet and an optional opt-in *interface*, but **no live email capture, subscribers, independent consent approval, buyer contact transfer, qualified lead or customer revenue**.
