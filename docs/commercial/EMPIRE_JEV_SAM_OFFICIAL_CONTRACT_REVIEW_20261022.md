# Empire Research — original SAM.gov public notices: commercial-fit review

**22 October 2026 · SAM.gov public notice fields checked · isolated OBSERVE feature branch**

## Official public listing cross-check

All three previously surfaced identifiers resolve to official SAM.gov pages
with the notice IDs, work categories, published agency, dates, NAICS and
set-asides shown below. Pages were checked via public official-source search
on 22 October; the local server's direct HTML fetch had previously returned
generic JavaScript shell pages, **not separately verified full notice bodies
or attachments**. No SAM API key was used. The JSON research packet
`config/jev_sam_procurement_public_review_20261022.json` records those
manually checked original-site fields, and the immutable output
`JEV_SAM_OFFICIAL_NOTICE_TRIAGE_20261022.json` pins their SHA-256.

| Notice | Official SAM.gov page | Observed latest public details | Official deadline |
|---|---|---|---|
| **W9127826RA089** | https://sam.gov/opp/9c89a95ffe824dc3badb12b63e0109b2/view | USACE Mobile District; vertical construction MATOC; NAICS 238990; *total small-business set-aside*; AL, FL, GA, MS | **5 Nov 2026, 2:00 pm CST** |
| **36C25727Q0022** | https://sam.gov/opp/ec71e534432b474abf888a7c9eb2c89c/view | VA Network Contract Office 17; North Texas VA comprehensive roof maintenance; NAICS 238160; *service-disabled veteran-owned small business set-aside*. Updated 9 Oct | **28 Oct 2026, 3:00 pm CDT** |
| **140L4326Q0127** | https://sam.gov/opp/12d361c6fdc7478f9a8e1406cd054fcb/view | Bureau of Land Management, Oregon State Office; heat pump, condenser and air-handler replacement; NAICS 238220; *total small-business set-aside*. Updated 15 Oct | **23 Oct 2026, 5:00 pm MDT** |

**Source limits:** The current public pages are marked `Active`; this
describes the observed SAM.gov listing status, **not** a real-time booked or
qualified bidding slot, a guarantee the closing date hasn't been amended, or
the eligibility of any company. For active decision-making a contractor
must verify the latest original attachments, amendments and registration
process with SAM.gov (and PIEE where required). The VA SDVOSB restriction is
not satisfied by merely being a small business; independent vendor
eligibility requires verification. We did not inspect the full solicitation
PDFs, submit questions, sign in, express interest or contact contracting staff.

## Correct commercial interpretation

The contracting agencies are buying construction, roofing maintenance
and heating/air-conditioning *work*. **None of the three** is established
to be buying Empire AI's lead-generation, conversion technology, software,
marketing services, public-record brokerage or AI subscriptions.

The released research triage therefore records:

- **3 original-site public listing references / field-level checks**,
  **0 reviewed original notice attachments**, **0 verified eligible bidders**.
- **0 direct Empire AI SaaS or lead-generation sales opportunities**,
  **0 qualified subcontract/brokerage agreements**, **0 licensed contact
  lists**, **0 verified buyer-capacity matches**, **0 outreach**.
- One notice within 48 hours, one within seven days and one later as of
  22 October. This is a bounded time-sensitive owner review, not automated
  bidding or a reminder.

These public bids could belong in a **separate public-procurement or
contractor-network Research product** if a correctly qualified contractor
requests support and procurement rules/terms permit that role. They do not
belong in the existing SaaS/lead-gen demand pipeline or as alleged
"homeowner buyers". In particular, do not source private contractor
contacts from government notice pages or create unsolicited messages.

## Engineering increment

`empire_os/jev_sam_procurement_review.py` validates the notice ID,
exact SAM.gov path, known work category, NAICS, published set-aside and
date/US timezone fields against an explicit pinned review. It classifies
deadlines from a timezone-aware clock and **never** upgrades eligibility or
commercial fit. After the close of a bid deadline it becomes
`PAST_DEADLINE_NO_BID_INFERENCE`. A manually observed status always stays
`live_sam_notice_api_state_confirmed=False`; if the review ages beyond
a day, the snapshot is flagged stale for new action.

`scripts/review_jev_sam_procurement_20261022.py` cross-checks the
shortlist against the previously published Jev demand-gap owner report,
creates a single immutable private-safe aggregate receipt and refuses
to overwrite it. A new observation requires a newly dated, independently
reviewed source packet. The dataset contains no public contact details,
emails, private profile links, person records, bid submissions or
customer-payment actions.

**Owner next action:** decide whether any *independently qualified US
contractor partner* actually wants permitted bid-support/market-intelligence
research. Separately continue first-party UK/US research for companies
**explicitly requesting B2B lead generation, appointment conversion or
SaaS**. Before proposals or outreach, existing Buyer Scout/CRM checks must
prove source rights, canonical identity, actual buyer needs, valid current
terms, consent, tenant ownership and suppression clearance.

**Production unchanged. No emails, DB writes, money, new agents, API
credentials, tender submissions or commercial approvals.**
