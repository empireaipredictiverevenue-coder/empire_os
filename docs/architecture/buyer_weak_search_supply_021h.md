# Buyer Scout 021H — bounded canonical supply when public search is weak

## Production diagnosis — 9 October 2026
The 20:01 UTC Scout run found one relevant primary Search Fabric domain
from twelve buyer research queries. Public search providers were degraded:
DuckDuckGo HTTP 202, Mojeek HTTP 403 and Bing frequently no relevant
results. Seven repeat public-research baseline seeds supplied most remaining
Scout candidates. Eight repeated companies gained no independently verified
purchasing claim, named person/email binding or canonical match. A bounded
eight-page first-party probe of two unknown companies found no additional
explicit purchasing statement. A larger repeat crawl is not justified.

## Recovery integrated into the existing Scout job
The existing `run_buyer_acquisition_scout.py` defaults to
`--low-yield-canonical-limit 3` and does not start a new worker or
scheduler. When primary Search Fabric yields **one or two** valid domains,
it reserves up to three additional first-party research slots from **our
existing canonical prospect seed reader**. Empty-search fallback is
unchanged; with three or more usable search domains this supplement is
inactive. Direct calls to `run_buyer_scout` default to the legacy no-
supplement behaviour for compatibility.

Each supplement requires an existing canonical UUID ID, non-generic company
name, supported ICP, and bounded, well-formed http(s) company website.
Malformed/credentialed URLs, unsupported ICPs, duplicate sites and
discovery-infrastructure sites are rejected. Opportunity- and intent-linked
seeds retain their special precedence. Search results receive priority
ahead of repeated public research baselines; canonical low-yield supplements
reserve explicit slots within the **existing max_domains/max_probes budget**,
not extra search/network tasks.

The regular first-party probe, identity/corroboration, review, suppression,
outbound, terms and payment gates remain mandatory. A canonical DB UUID or
company website is NOT direct purchasing evidence and is not proof of a
decision maker or consent. No claims of verified buyers are generated.

The Scout receipt adds `low_yield_canonical_supplement_count` and its
`_used` flag. The existing Revenue Flow Meter separately reports primary
search domain yield and low-yield canonical research seats, clearly marked
as research supply, NOT verified buying or monetary conversion.

## Operational validation
All processing remains in the existing 12-probe scheduled Scout service.
No new timer, DB write outside the pre-existing pipeline, remote sending
or paid search provider is added. The owner must verify the next scheduled
Scout cycle before reporting any increase in first-party/canonical
corroborated buyers. A successful unit test does not prove live
canonical seed availability or buyer advancement.
