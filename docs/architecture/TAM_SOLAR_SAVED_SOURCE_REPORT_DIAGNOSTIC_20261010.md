# TAM Solar — inspect saved first-party search failure without repeating discovery

Date: 2026-10-10. Status: root-private aggregate inspector prepared; the protected production report has NOT been read by Remote Commander.

## Live production evidence to date

User executed one first_party_search OBSERVE run for GB research focus, selecting three of 83 canonical solar entities. It produced:
- 1 independent Search Fabric website candidate;
- 1 bounded public site probe;
- 0 verified company-site review candidates;
- zero source acquisition ledger inserts, outbound, and country proofs.

The protected original report was written to:
`/var/lib/empire/source-acquisition-review/20261010T200046Z-3e7726d663ba.json`.

Live results do **not** show why the single probe failed. Possibilities include inaccessible/redirecting site, missing identity-bearing business name, mismatch between company name and website, or existing Search Fabric identity guard rejection. The report already contains enough private evidence to distinguish these, so do not repeat queries or probes.

## New aggregate-only reporter

`scripts/summarize_tam_source_review_readonly.py` accepts ONLY one root-private, root-owned 0600 JSON report in the existing `/var/lib/empire/source-acquisition-review/` directory, with the exact timestamp/randomized basename. It refuses other paths, directories, symlinks, unsafe mode/owner, excessive file size, unexpected JSON schema, missing OBSERVE authority or >5 findings. It uses no database connection, no web/network request, and no process mutation.

The reporter checks the stored source URL and captured business names **in memory**, and reports **only aggregate reason counts**:
- `PUBLIC_SITE_OR_SAME_HOST_UNVERIFIED`
- `SITE_RETRIEVED_BUT_NO_BUSINESS_NAME_EVIDENCE`
- `SITE_BUSINESS_NAME_DOES_NOT_EXACTLY_MATCH`
- `SEARCH_FABRIC_IDENTITY_GUARD_REJECTED`
- `NO_UNIQUE_INDEPENDENT_CANDIDATE_HOST`
- `REVIEW_CANDIDATE_NOT_LEDGER_APPROVED`.

No business names, UUIDs, domains, page content, source URLs, contacts, user credentials or other protected data are printed. This reporter does not alter the original report.

## Single direct authorized command

```bash
cd /srv/empire_os && sudo -n /srv/empire_os/.venv/bin/python -m scripts.summarize_tam_source_review_readonly --report /var/lib/empire/source-acquisition-review/20261010T200046Z-3e7726d663ba.json
```

Remote Commander does not permit privileged reading of this protected file. The user must execute the authorized command directly in the existing SSH session and provide the aggregate JSON only.

## Decision after reading the saved report

- Failed HTTPS/host capture: inspect Search Fabric site probe (redirect, denial, timeout), **not** canonical company ownership.
- Site loaded but name absent: treat as unverified. Do not guess equivalence from generic solar category or location.
- Name mismatch: investigate trading/legal-name relationship using independently verifiable records, **not** fuzzy auto-merging.
- Name matches but identity guard rejects: examine existing Search Fabric identity verdict and aggregators; do not weaken its safeguards merely to pass.
- Even if a real business website is corroborated: separately verify the **correct existing prospect link**, explicit country provenance, source ledger idempotency and founder authorization before any acquisition INSERT or new TAM market claim.

The 83 solar canonical entities remain unresolved candidates with zero GB source provenance. Seventy-one share one original website host; this is not company identity evidence. The original source acquisition, CRM, Market GPS and TAM runtime are unchanged.
