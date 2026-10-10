# TAM source recovery: classify saved first-party search evidence (no rerun)

Date: 10 October 2026.

## Current live production truth

The authorised source=first_party_search run selected 3 canonical solar entities for search from 83 existing canonical entities. Search Fabric returned one website candidate, attempted one first-party probe, and verified zero company identities. No acquisition ledger rows were inserted, no outbound occurred, and no country was independently verified. The private root-owned 0600 evidence packet is:

/var/lib/empire/source-acquisition-review/20261010T200046Z-3e7726d663ba.json

All original prospect.website values across 71 of the 83 entities point to one common shared host, previously confirmed by read-only eligibility audit. This is not independently verified first-party website evidence for each company. Do not assign 845 repeated URLs to 71 companies; do not force an acquisition to one of the 869 linked prospects.

## Next step: consume the EXISTING private packet, not another search

scripts/summarize_saved_tam_source_review.py reads a single exact-named private packet and returns only classified aggregate counts. It performs NO network requests, public website scans, SQL queries, DB writes, runtime changes or new outbound. The file must be an exact protected 0600 regular file under the root-owned restricted source-acquisition review folder.

Authorised operator command:

    cd /srv/empire_os && sudo -n /srv/empire_os/.venv/bin/python scripts/summarize_saved_tam_source_review.py --packet 20261010T200046Z-3e7726d663ba.json

It prints only:
- no_unique_website_candidate
- site_not_verified_from_expected_host: an attempted site retrieval failed the HTTPS/same-host/page-receipt check (or probe unavailable)
- site_retrieved_but_identity_not_corroborated: same-host page observed, but original Search Fabric identity guard and/or exact business-name evidence did not support attribution
- company_name_supported_review_only: review state, still not a verified entity/prospect relationship

Do not interpret the summary as proving zero UK solar companies: the sample covered just three identities. Do not silently change the original source or disable the identity guard.

## Commercially useful routing after receipt

If the site cannot be retrieved, do not repeat the same URL. Prefer a verified independent company-specific source or official registry; keep the legacy polluted entity held.

If site retrieved but identity not corroborated, use the actual private name/identity evidence for **manual** review before considering any append-only acquisition. Only the founder-authorised separate attachment implementation can mutate prospect_acquisitions.

If no search candidate, avoid repeated broad SERP loops: use RECC original member records and official GB registry evidence to create a **source-first, provenance-rich qualified candidate** that does NOT automatically merge into polluted legacy entities. Identity resolution, explicit GB, provenance and duplicate checks remain mandatory. Revenue is not evidenced by source discovery alone.

No further migration, new timer, credentials, outbound, payments or permissive identity merge are authorised.
