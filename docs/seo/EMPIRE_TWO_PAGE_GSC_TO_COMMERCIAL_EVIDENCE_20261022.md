# Empire AI — two SEO pages → verifiable commercial evidence

22 October 2026 · **OBSERVE ONLY · existing EmpireDB · no new tracking storage**

## What is now proven

The two approved pages `/predictive-revenue` and `/industries/roofing` are live. Founder confirmed manual Google URL Inspection indexing requests submitted on 22 October, but **Google acceptance/indexing is not independently verified**. The weekly first-party GSC page-only reader and Monday timer are active, tracking finalised metrics with a four-day buffer.

The canonical EmpireDB founder-sales count-only probe, run as authorised root under `--review-only` on 22 October, returned:

| Canonical observed source | Count |
| --- | ---: |
| `first_party_commercial_sales_enquiry` acquisitions | 0 |
| `self_serve_predictive_revenue` acquisitions | 0 |
| Founder CRM tenant-visible sales prospects | 0 |

**Scope restriction:** This count is limited to those canonical acquisition and Founder CRM views. It does NOT count research enquiries, all website contact attempts, inbox messages, page visitors or any noncanonical events. Zero within these sources does not mean zero search traffic or total Empire AI interest.

## Current source-to-conversion gap

The existing first-party /commercial enquiry frontend submits `product_code`, `business_name`, `email`, `domain`, `industry`, `geography`, `desired_outcome`, `contact_consent`, `idempotency_key` and a blank honeypot `website`. It does not provide verified originating page/referrer for /predictive-revenue versus /industries/roofing.

The existing backend `FounderLedCommercialInterestRequest` and `first_party_sales_interest.py` **already** accept bounded `organic_touch`, `claimed_entry_page`, `source_campaign_key` and `source_landing_url`. These are treated as **browser-stated or campaign claims**, not automatically verified Google attribution. `claimed_entry_page` has a strict published-path allowlist; the public gateway sends `Referrer-Policy: no-referrer`. There is no reason to create an additional tracking DB or assume entry origin from a GSC click.

**Before a future source-capture release**, review the consent/privacy requirements, design minimal first-party entry-page capture without cross-site identifiers or URL parameters, ensure idempotency and retention, test spoofing and browsers landing directly on /commercial, and separately approve a pinned website frontend change. Even a captured entry-page claim does not establish a Google organic session unless a trustworthy source chain exists.

## Built now

- `empire_os/search_intelligence/seo_to_commercial_evidence.py`: strict schema validation of real final page-only GSC weekly receipts plus count-only existing Founder CRM reconciliation. Page-specific `attributed_consented_enquiries`, `attributed_accepted_orders` and `attributed_realised_revenue` are **null** unless independently proven by a future approved receipt join. Does not infer sitewide sales counts as SEO lead counts.
- `scripts/review_seo_two_page_commercial_bridge_20261022.py --review-only`: an **explicit, one-hit, read-only, privileged** observer. Reuses canonical existing probes and the existing GSC weekly reader. No new SQL, DB grant, model call, website tracking, mail or payment action. Run only with pre-existing authorised read-only local operator privilege.
- `tests/search_intelligence/test_seo_to_commercial_evidence_20261022.py`: six regression tests include absent GSC rows, real zero-source counts, nonzero but unattributed CRM totals, source provenance mismatch, and deliberate protection against personal-data disclosure.

## Run (authorized read-only local operator)

```bash
cd /srv/empire_os
PYTHONPATH=. sudo -n /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_seo_two_page_commercial_bridge_20261022 \
  --review-only --as-of 2026-10-22
```

For the actual 22 October run, the GSC status is `POSTRELEASE_SEVEN_DAY_WINDOW_NOT_YET_FINAL`; the two old comparison windows returned no page row, so **page clicks and impressions are null, not measured zero**. This report also records **zero** canonical sales acquisition rows, **zero** tenant-visible Founder sales prospects, and **no verified page-level attribution or revenue**.

## Next integration gates

1. Independently verify one real opted-in enquiry and source evidence, once submitted, using existing first-party commercial intake and CRM. Do not fabricate visitor events or transmit hidden test customers into production.
2. Stage a **privacy-minimised** claimed-entry-page handoff through the existing intake contract (first-party route only; not a proof of Google traffic). Founder review and separate public-site approval required before modification.
3. Compare those consented source claims against actual accepted, fulfilled and settled records in EmpireDB, under existing tenant privileges and exact receipt lineage. Source counts alone are not accepted-order evidence.
4. Incorporate separately verified, aggregate qualified lead and real settled revenue results into weekly SEO reports only after a proper lineaged reader and review. GSC impressions are not money, nor are projections.

**Protected:** no outbound, no live buyer call routing, no CRM writes, no new source-claim collection, no paid Jev use, no payment activation, no new systemd timer, and no commercial or revenue claims without supporting receipts.
