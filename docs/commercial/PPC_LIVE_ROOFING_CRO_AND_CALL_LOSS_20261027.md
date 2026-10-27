# Empire AI — PPC Call-Quality Integration and Live Roofing CRO Finding
Date: 27 October 2026
Scope: Original parked PPC adapter and competitor CRO research. No website/SEO or live Ringba mutations.

## 1. Verified real-world storefront observation
A no-credentials, read-only HTTP GET to https://empire-ai.co.uk/roofing returned **200** and a 69,308-byte HTML body. Parsed visible text confirmed all of the following on the deployed page:
- "Review only · Traffic disabled"
- "Check ZIP & request a roofing call"
- "Calls are not currently enabled on this preview."
- "Roof replacement or reroofing enquiry"
- "Roof leak repair or water entry"
- "Storm-damaged roof inspection"
- "Buyer-confirmed operating hours"

Source inspection of existing apps/empire-public-site/src/app/roofing/page.tsx and coverage-check.tsx confirms that ZIP guidance is informational, call authorisation is conditional on original server verification, and no call option bypasses the existing controls. This is a **live copy consistency and lead-quality hypothesis**, not observed conversion loss or an instruction to activate calls.

**Owner-specific request:** Original website/CRO owner should align the hero CTA with the genuinely disabled call state, while retaining useful ZIP guidance. Original Lead Smart commercial owner should confirm which of replacement, installation, leak repair and storm inspection are actually eligible for payment; the page includes all four while the buyer's exact service-acceptance rules have not been independently established by this workstream. Only the original website and SEO owners may edit, approve and deploy page copy. Do not auto-generate many roofing city pages or imitate local businesses.

## 2. Original call-loss measurement now joined to source-to-cash review
Changed ONLY existing empire_os/ppc_switchboard_adapter.py. The existing review_pay_per_call_source_to_cash now optionally consumes the original, approved, aggregate-only evaluation from empire_os/competitor_call_loss_readiness.py for the identical source_id and cohort_ref.

For an independently original-owner-asserted, strictly monotonic, deduplicated sample it can distinguish:
- Provider inbound calls that never connect to a target.
- Provider-target-connected calls that never reach a human (IVR/queue abandonment or agent no answer).
- Human-answered calls that fail written payable criteria.
- Final accepted and independently settled calls, still requiring the original Finance proof.

The join rejects source/cohort mismatch, non-monotonic counts, inconsistent CRO versus call-loss versus Finance stage totals, unbalanced reason taxonomies, target-attempt inflation, unsolicited fields such as caller ANI, and unapproved original-owner aggregates. Missing or unverified data produces null, not artificial zeros. Test fixtures contain synthetic amounts only and are NEVER real company financial performance.

**No separate analytics database or call routing service.** Existing first-party Analytics remains offline, the present Ringba publisher token cannot read Number Pools (HTTP 403), and shared static DID attribution is not a permitted exact browser-to-call identity. Do not spend on pools or try to bypass provider roles.

## 3. Next execution priorities by original owner
1. **Website/SEO/CRO owner:** review exact deployed hero/disabled-call language and service scope in one bounded original release. Approval of copy does not approve route activation.
2. **First-party Analytics/privacy owner:** design lawful source and consent provenance on the existing Empire Analytics ledger and a permitted first-party source-to-call correlation method; no collector activation from this research.
3. **Ringba/Lead Smart commercial owner:** provide one deduplicated unique-call aggregate with original commercial acceptance, human answer evidence and reason buckets. The Oct 27 API's zero matches cover only a limited query window, not all historic calls; number-pool inventory remains UNKNOWN.
4. **Finance/CRU owner:** reconcile actual buyer acceptance with bank-confirmed receipts, reversals and verified costs for one identical cohort before publishing any conversion/profitability claims.
5. **Existing Predictive Revenue owner:** ingest only independently authorised source/cohort outcomes, never assumed vendor case-study ROI.

## 4. Controls
All website deployment, SEO edits, network purchases, new agents, timers, live calls, routing, payment actions and customer data collection remain OFF/unchanged. Neither a 200 response nor a locally simulated test is evidence of genuine visitor counts or real payable calls.
