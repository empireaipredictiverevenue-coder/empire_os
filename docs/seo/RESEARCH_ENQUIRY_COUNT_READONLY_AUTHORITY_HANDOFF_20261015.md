# Empire SEO / Revenue — research enquiry visibility, owner handoff (15 October 2026)

## Why this read-only check exists

Five first-party `/research/campaign_*` pages publicly published under the existing immutable `owned_campaign_release` evidence. Their own enquiry form sends user-initiated submissions through `/api/research/enquiry` into `public.owned_campaign_enquiries` via approved `public.record_owned_campaign_enquiry(jsonb)`, while server submission events are stored in `public.owned_campaign_events`. The existing Founder CRM sales-acquisition aggregate counts `first_party_commercial_sales_enquiry` and `self_serve_predictive_revenue` only. **A zero result in those two sources does not mean the dedicated research form received zero enquiries.** The research and sales sources should not be silently combined or treated as consent to share/contact.

## One-shot operator prepared

`scripts/probe_owned_research_enquiry_aggregate_readonly.py` is a **source-only, one-hit local observer** modelled on the already-installed `scripts/probe_canonical_sales_intake_aggregate_readonly.py`. It contains a fixed SQL query:

- `BEGIN ... REPEATABLE READ READ ONLY`, local 7-second statement timeout, 2-second lock timeout and `ROLLBACK`.
- Returns only global counts: research enquiries, distinct campaigns with enquiries, outbound/marketing policy violation count, server-received submission events, aggregate anonymous browser observations and invalid submission-event count.
- No contact addresses, names, message content, campaign IDs, prospect identifiers or credentials are selected or printed. No per-campaign cohorts, dates or other small-group slices.
- Classifies absent enquiry rows, present interest separate from sales, inconsistent evidence, or unverified/boundary failure. It **never** authorises outreach, payment, buyer routing or CRM promotion.
- Invokes the *existing* local `runuser postgres /usr/bin/psql` pattern **only under explicitly privileged local operator execution**; unprivileged caller fails closed. No database role, function, grant, table or new service is installed.

**Verification:** 47 focused tests passed on 15 October, covering no-PII envelope, no-DB unprivileged denial, fixed read-only query, mismatched event counts, suppression/consent inconsistencies, bounded integers, table unavailable and failure-safe classification.

**Production read status: HELD.** The connected Remote Desktop tool refused a new privileged command attempting to invoke this operator, before it executed. **Do not work around the privilege restriction** by changing the invocation format, adding a helper/grant, borrowing a more powerful service identity or running unapproved SQL. No actual research enquiry counts are verified as of this handoff. The database owner can review, approve and independently run the script through their existing authorised privileged workflow; only then may the numeric results be reported. Until then, research intake is **UNKNOWN, not zero**.

## Commercial boundary

A consented research question is neither a verified sales opportunity, an accepted solar installation lead, a payable CPC, nor realised revenue. Even if rows are later found, reconcile with first-party commercial consent, fulfilment partner acceptance, source permissions and founder tenant authority before identity linking or outbound. The existing `/commercial` and `/predictive-revenue` intake authority is unchanged.

## Zero-spend UK solar shortlist additions

These are independently retrieved programme descriptions, **not executed partnerships**:

- **Newpower Advanced Ltd**, https://www.newpoweruk.co.uk/collaborate — residential solar referral/affiliate route for professionals with homeowner relationships; MCS-certified installation claimed; no publicly confirmed standard commission or publisher traffic permission. Contact shown by own site: `info@newpoweruk.co.uk`. Need direct written clarification of accepted first-party SEO referrals, affiliate/publisher intermediary, coverage, rate, verified MCS+RECC details, reversal and consent.
- **Geo Green Power, PowerShare Business**, https://www.geogreenpower.com/powershare-business/ — referral programme open to UK-registered businesses; publicly described 1% on the final ex-VAT, completed, invoiced and paid commercial solar project; noncommercial/everyday homeowner referrals must not be inferred eligible. Contact shown: `info@geogreenpower.com`. Need confirmation sole-trader/company eligibility, no existing customer relationship, SEO-generated business-introducer traffic, project coverage and written settlement.
- **HPO Homes**, https://www.hpohomes.com/terms-conditions/ — affiliate scheme publicly describes £300 per approved successfully completed residential solar installation using a unique referral link, with 28-working-day payment after installation and invoice. Requires written approval; acceptance section includes marketing emails. **Contact email could not be independently established as plain text from the available first-party page result; do not guess**. Application/review only; no referral link active.

Note: UEG and Integrity Solar had first-touch enquiries sent from `phil@empire-ai.co.uk` earlier 15 October; Solar Briton also already has a same-day reply. Do not duplicate. All new names were checked against both linked Gmail accounts for prior matching messages (none surfaced); founder domain holds and commercial holds for Newpower/Geo did not show a known block, but **the canonical recipient-level suppression database was not independently verified**, so this is not send clearance. No additional outbound sent.

**Recommended next owner decision:** approve two fresh, tailored, nonbinding messages only after exact-recipient suppression and the matching sender transport checks; secure one residential downstream buyer's approval before suggesting a 30-day Solar Briton publisher pilot. No promised payout, homeowner-data transfer, paid ads or signature.
