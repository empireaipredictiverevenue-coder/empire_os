# EmpireOS Brave Search API — live verification and safeguards
Date: 20 October 2026

## Verified live provider evidence

The founder invoked the single Brave Search preflight through systemd with
EnvironmentFile=/etc/empire_os.env, and got HTTP200, 3 relevance-gated source
URLs, and a successful systemd exit. This confirms a working Search API key
and real provider access. No buyer, enquiry, opt-in, sale or CRM record
was established by that request. API key value was never included in output.

## External contractual and cost constraints

Brave Search API's standard September 2026 Terms of Use restrict storage,
caching, creation of databases and derivatives of Search Results except
transient use required for operation. Brave's October 2026 help documents
state that storage requires separate rights. Brave Search offers a $5
monthly credit and charges $5 per 1,000 requests; this is not an unlimited
free service. The dashboard supports usage caps.

Sources:
https://api-dashboard.search.brave.com/documentation/resources/terms-of-service
https://api-dashboard.search.brave.com/documentation/resources/help-feedback
https://brave.com/search/api/

Existing /srv/empire_os/empire_os/search_fabric/search.py writes search
results into CACHE_DIR. Existing canonical Buyer Scout persists public
research seeds into runtime/buyer_acquisition/public_research_seeds.json.

The system buyer-acquisition Scout runs every ~30 minutes with 12 discovery
queries per job; search_domains_parallel explicitly bypasses its cache.
At this cadence there may be at least 17,280 query attempts per 30-day
month before query broadening and other departments. At $5/1,000 this
would correspond to $86.40 before the recurring $5 credit, if every
attempt incurred a billed Search API request. Actual billing must be
checked in the Brave dashboard and the user should set a hard usage cap.

## Temporary safeguard, NOT YET INSTALLED by this branch

This worktree includes:
ops/systemd/system/empire-buyer-acquisition-scout.service.d/
  90-brave-search-rights-budget-hold.conf

The root operator must install this drop-in to the identical
/etc/systemd/system/... path and run systemctl daemon-reload.
It applies UnsetEnvironment=BRAVE_API_KEY to the existing canonical
Buyer Scout service, without disabling the service/timer or changing
its other CRM and public-research workflows.

This temporary hold does not affect the verified one-shot preflight's
explicit EnvironmentFile, so the key remains available for controlled
testing.

Review status via:
  systemctl show empire-buyer-acquisition-scout.service -p UnsetEnvironment
  systemctl cat empire-buyer-acquisition-scout.service

Do not run a bulk Scout search using the global Brave key until a
source-results storage/retention permission or compliant transient process
and an enforced per-department usage cap have been reviewed.

## Next build

Search Fabric owner should implement:
- Provider-specific response and entitlement health, no secret disclosure.
- Brave-only bounded no-cache ephemeral search with one-token budget ledger,
  no persistent Brave result records, no result training or sale.
- If direct company site inspection is independently authorised, use
  first-party robots-checked independent source evidence, not a cached
  Brave search response.
- Licence clarification for any stored Brave-derived discovery data.
- Canonical Buyer Scout owner receipt verification, no automatic promotion
  and no permissionless contact extraction.
