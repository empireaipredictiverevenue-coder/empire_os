# TAM solar — source-first RECC acquisition review

Date: 10 October 2026. Engineering release prepared; production root-only source-first packet not yet created.

## Live evidence and reason to avoid legacy matching

The previous saved first-party discovery packet was diagnosed without any new requests: three selected legacy solar entities gave two with no unique independent candidate website and one retrieved site whose company name differed from the stored canonical entity. The old cohort comprises 83 unresolved exact-sector solar entities with 869 active prospect links, 71 entities all using one shared host, and zero explicit GB provenance. These records remain unchanged.

A separate real public RECC test examined two member details and two corresponding candidate websites. One site produced a same-host page and a positive existing Search Fabric identity-guard review verdict. One member contained RECC public postcode evidence. This is a source-first review candidate, NOT a verified buyer, DB acquisition or contact authority.

## Built into the existing source-acquisition connector

Files: empire_os/tam_source_acquisition_connector.py; scripts/run_tam_source_acquisition_connector.py; tests/test_tam_recc_source_first.py.

The source-first preview has hard limits: at most two public site probes and five RECC member details. It checks HTTPS RECC member source provenance, name, solar niche, GB source locale, public RECC website/phone/postcode, and uses canonical prospect_ingest.prepare_candidate only in memory. It ensures the RECC source URL remains acquisition evidence and is never a prospect business-website field.

Before first-party checking it rejects shared/reused websites in the bounded source sample, directory hosts and IP/local/invalid URLs. For first-party checks it uses existing Search Fabric site_probe with public_only=True, max_pages=1, request_timeout=4.0 and time_budget_seconds=8.0. The existing Search Fabric identity guard must accept to create a positive evidence REVIEW state; it cannot promote identity or country or purchase intent.

Original RECC evidence URLs, public contact details, provisional ingest fingerprint and review states are held in root-owned 0600 private review JSON. Aggregate stdout does not print private leads or contact data.

Source-first mode does not read EmpireDB, does not merge one of the 869 links, does not create prospects or acquisitions, and does not send outbound, accept terms, pay, set timers or verify revenue. A canonical duplicate/tenant/read check must be designed before any separately authorised ledger attachment.

## One bounded authorised live-source preview

cd /srv/empire_os && sudo -n bash scripts/run_tam_source_acquisition_connector.sh --observe --source recc_source_first --sector solar --country GB --max-source 2 --max-site-probes 2

The aggregate receipt shows members_listed, canonical_acquisition_previews, public_sites_probed, first_party_identity_supported_review_count, member_postcodes_present and the protected private review file. All write/outbound counts must be zero. This is not a promise of two successful matches. Do not retry blindly on a negative result.

## Next gate to a genuine CRM/TAM acquisition

Independently review and identify one exact company from member page plus first-party website and official registry where available; verify jurisdiction; establish no unsafe canonical duplicate or tenancy conflict; bind exactly one correct prospect, not a random member of the old 869-link graph; then implement and obtain separate founder approval for append-only, idempotent source acquisition ledger write. TAM reader, outreach and revenue authority remain unchanged.