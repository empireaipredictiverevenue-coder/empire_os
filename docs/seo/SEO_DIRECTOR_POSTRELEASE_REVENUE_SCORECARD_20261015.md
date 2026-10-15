# Empire AI — SEO Director post-publication revenue scorecard

**15 October 2026, independent first-party readback · Website / Search Intelligence / Commercial Exchange · OBSERVE**

## One real baseline, not invented rankings

The first-party Search Console API for **`sc-domain:empire-ai.co.uk`** was queried directly through the existing loopback Search Intelligence service. Its GSC data passed the existing `organic_revenue_baseline.py` source, property, window and metric validation. This report is derived from **15 September–13 October 2026**, the latest bounded period in this task after normal Search Console processing lag, compared to the adjacent **17 August–14 September** period.

| Verified Google Search Console metric | Latest 29 days | Previous 29 days |
| --- | ---: | ---: |
| **Sitewide search impressions** | **83** | **168** |
| **Sitewide organic-search clicks** | **1** | **3** |
| Query+page dimensions returned impressions | **27** | Included in prior GSC receipt; not equivalent to sitewide |
| Query+page dimensions returned clicks | **0** | Not full sitewide clicks |

Only **27/83 impressions** are visible against non-anonymised query/page combinations. The missing **56 impressions** and the **one sitewide organic click** cannot be reliably attributed to a specific query or page from this response. In the current visible query/page portion, `/industries/roofing`, `/industries/solar`, `/commercial` and `/predictive-revenue` have **zero displayed matching rows**; this must not be reported as zero actual impressions or zero clicks for those pages. Do not expose or save raw Google search phrases from customer traffic.

**Publication:** Source commit `9bf72992` and verified public release receipts:

- `runtime/public_website/seo_four_pages_20261015_release_v1/release_receipt.json` — original roofing/solar buyer education and commercial/deployment privacy links.
- `runtime/public_website/seo_director_b2b_two_pages_20261015_release_v1/release_receipt.json` — original SEO Director's 14 October Commercial and Predictive Revenue buyer explanations.

The new one-shot audit validates both release receipts' exact page scopes, SHA-256 and unchanged safety flags against the **real HTTPS public pages**. All **four** observed pages return 200 with self-canonicals, one H1 and the expected original buyer copy. Both commercial forms still contain their required consent checkbox and `/privacy` link; the unrelated `/roofing` buyer route remains `noindex`.

**Important timing:** All four updated pages were published on **15 October**, after the GSC report ended on **13 October**. The observed GSC results therefore establish a **pre-publication baseline**, not a post-launch performance test. It is too early to claim an uplift, a failure or any source-to-enquiry conversion. Future observation windows should use equally sized 29-day periods and separately note possible changes in content, redirects, indexing and market demand. Genuine conversion lift requires actual consented contact events with legitimate source evidence and ideally a defensible comparator.

## Revenue operating truth

The live read-only Founder Executive API reports `NO_VERIFIED_COMMERCIAL_CAPACITY` for downstream buyers. **This is not a count of all inbound business enquiries**. Verified publisher-side payable CPC events, accepted calls, paid leads, contractual buyer rates and collected revenue are **not proven by GSC**. Do not create referral redirects, activate call transfer, add consumer forms, advertise a guaranteed ROI or buy paid-search clicks based on website traffic figures.

The root host duplication remains real: public `https://www.empire-ai.co.uk/` returns HTTP 200 rather than a permanent redirect to `https://empire-ai.co.uk/`. The original site has a preferred HTTPS apex canonical. The existing `empire_os/public_gateway.py` is concurrently modified by another owner; the review-only policy `empire_os/public_canonical_host_review.py` remains deliberately unmounted. Correct it only through its owning gateway/Cloudflare release with checkout/OAuth/legal/path protection.

## Actions for the existing weekly SEO Research Council

1. **Measure the newly published pages after Search Console processing lag.** Use this same first-party script and next non-colliding date-stamped private receipt. Inspect newly observed **sitewide**, **visible page**, and **query** data without treating the latter as complete; monitor 7/28-day trends, crawl/indexing diagnostics and whether the new industry copy improves *real* demand.
2. **Improve discovery, not page count.** Existing homepage links to `/industries`, the industry index links to roofing/solar, and the industry pages lead to the `/commercial` nonbinding proposal flow. Review anchor language and useful original buyer research before publishing more duplicate AEO or doorway pages.
3. **Pursue one genuinely sourced commercial buyer question and one link-worthy original resource.** A sensible first candidate is *how US roofing call buyers define accepted calls by job type, ZIP, hours, routing and dispute terms*. Reconcile with the live relationship, verify sources, avoid quoting unsigned payouts or inventing coverage. A second candidate is solar publisher-to-installer eligibility across UK/US/Australia.
4. **Link genuinely consented enquiry outcomes to existing first-party founder CRM.** This current report does not access private customer records or claim a prospect. Use the **separate** approved read-only aggregate CRM reconciliation and exact source receipts if a real opt-in arrives; do not label a Search Console click as an accepted commission.
5. **Fix canonical duplication with the website owner; do not overwrite their active gateway edits.** Keep legal pages published but under metadata/legal review, the separate consumer `/roofing` `noindex`, the paid media budget at £0 and all outbound behind founder gates.

## Delivered without a second SEO agent

- `empire_os/search_intelligence/seo_publication_impact_review.py`: pure, tenant/property-bound merger of existing GSC baseline, two exact production release receipts, four public hash-verified pages and bounded buyer-capacity classification. All result metrics are source-limited; source queries/customer HTML are omitted.
- `scripts/review_seo_director_publication_impact_readonly.py`: read-only one-hit operator uses the **existing** Search Intelligence loopback API and Founder Executive status, then checks only fixed owned HTTPS URLs. Reuses existing `review_owned_organic_baseline`, creates no new scheduler or site gateway and writes only an optional exact-named, private, mode-0600 `/var/tmp` summary receipt, atomically and without overwriting prior evidence.
- Tests explicitly reject cross-property Search Console, contradictory counts, invalid buyer claims, altered page hashes, consent regression, compromised release manifests, unsafe receipt paths and false PPC attribution.

First actual private observation receipt: `/var/tmp/empire_seo_director_postrelease_20261015.json` (created only once, read-only sources). Output `PRE_PUBLICATION_SEARCH_BASELINE_ONLY`, four pages verified, capacity `NO_VERIFIED_COMMERCIAL_CAPACITY`, `www_host_redirect_review_needed=true`, no paid media, customer contact, website publication, DB write or revenue recognition.

**Re-use for the next scheduled SEO council run, without scheduling anything new:** run the same existing one-shot read-only operator from `/srv/empire_os`, with a new `--output /var/tmp/empire_seo_director_postrelease_YYYYMMDD.json` for the new calendar date. Never rerun using an existing receipt filename; updates should be explicit, diffed reports, not mutated historical proof. No new model/cloud spend, no new server, timer or paid ad account.
