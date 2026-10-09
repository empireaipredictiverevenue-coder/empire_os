# DFW contractor contact-history evidence — 10 October 2026

This is an **OBSERVE-only** audit note for the **existing** EmpireOS Revenue Strike, not a new lead list, sender queue, or delivery approval.

## Sources checked

1. Existing `runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json`, generated 2026-10-09T22:58:51Z, contains **185** commercial relationship records. Exact-domain reconciliation against the eight contractor-company domains found **zero exact matches**. That registry principally tracks buyer-network and connected-email relationships; it does not cover every external email account or all EmpireDB outbound/suppression records.
2. The connected Gmail read-only search was checked on **2026-10-10** using `in:anywhere` plus both directions `{from:<domain> to:<domain>}`. The eight exact company domains each returned **zero matching message IDs**, no pagination indicated:
   - maxexteriors.com
   - 180roofing.com
   - spcroofs.com
   - poweredgetx.com
   - labaroof.com
   - riseroofingconstruction.com
   - topnotchroofingrr.com
   - mastercraftroof.com
3. Second-pass `in:anywhere` quoted-name searches also returned **zero matching message IDs**, no pagination indicated:
   - "Max Exteriors"
   - "180 Roofing"
   - "SPC Construction"
   - "PowerEdge Roofing"
   - "LABA Roofing"
   - "Rise Roofing"
   - "Top Notch Roofing"
   - "Mastercraft Roofing"

**Limitations:** These search results are scoped only to the Gmail account connected to the assistant at the time of lookup. Searches can miss names/aliases, different sending domains, forwarded messages, spelling differences, or conversations stored exclusively in the owned Empire AI mailbox or EmpireDB. The assistant did not search the production owned mailbox, or authenticate a canonical EmpireDB suppression read. No negative search result can clear a recipient. No emails were sent, drafted, archived, or changed.

## Consequence for the existing revenue workflow

Keep all eight contractors as **RESEARCH_ONLY** until a real company identity, an authorised marketing owner, current purchasing interest, verified contact permissions and **recipient-specific EmpireDB suppression/history** checks are obtained. The three identity discrepancies remain held separately. A possible fixed-fee $1,500/14-day contractor pilot is only a review hypothesis, never a binding offer, payment or settlement percentage.

The existing commercial Deal Room must use Documenso after terms are legally and founder approved. Zero contracts, zero outbound and zero revenue have been demonstrated from this cohort.

For formal Texas identity checks:
- https://comptroller.texas.gov/taxes/franchise/account-status/search.php (public state Comptroller lookup)
- https://www.sos.texas.gov/corp/business-law.shtml (SOSPortal; formal business-entity records; fees may apply)

No paid record search, purchases, or provider activations were performed.
