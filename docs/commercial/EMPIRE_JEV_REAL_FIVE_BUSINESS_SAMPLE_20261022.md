# EmpireOS Jev — Five real business website QA cases

**22 October 2026 · Isolated, read-only research · No delivery, contact or deployment**

## Original official dataset

Source: [San Francisco Registered Business Locations](https://data.sfgov.org/Economy-and-Community/Registered-Business-Locations-San-Francisco/g8m3-pdis), a daily-updated Treasurer-Tax Collector public source (dataset g8m3-pdis). Public API: https://data.sfgov.org/resource/g8m3-pdis.json.

Official metadata lists an Open Data Commons Public Domain Dedication and License (PDDL). This permits research use of the published public business records but is not a grant of personal contact marketing consent or rights to redistribute other websites. Self-reported NAICS codes are not independently certified industry categories.

The bounded API query projected ONLY: unique business location ID, DBA business name, self-reported NAICS, city, state, location/DBA end flags, administrative closed indicator, and data timestamp. **No postal or mailing addresses, ownership names, contacts, emails, phones or person attributes** were requested, exported or persisted.

## Five business cases from seven source location rows

| Registered business | Current location rows in dataset | NAICS | Website check |
|---|---:|---|---|
| Lutz Plumbing Inc | 1 | 238220 | https://lutzplumbingsf.com/ — branded homepage directly returned HTTP 200 |
| Anatra Fire Protection Inc. | 2 | 238220 | https://anatra-fire.myshopify.com/ — branded page independently observed; later server retry HTTP 429 |
| Vitality Remodeling LLC | 1 | 236118 | https://vitality-remodeling.com/ — branded homepage directly returned HTTP 200 |
| J & K Pro Plumbing Inc | 1 | 238220 | No attributable first-party website confirmed in checked sources |
| Odonovan Plumbing Inc | 1 | 238220 | No attributable first-party website confirmed in checked sources |

The official source returned seven location rows: **two location records for Anatra**, and Odonovan has **one older ended row** in addition to a current location row. Those do not constitute seven separate businesses; the deduplicated research sample is five.

A current location row is not current confirmation of contractor licensure, corporate good standing or purchasing authority. Failing to identify a site is NOT proof that the business lacks a website. Anatra's 429 response is a source rate-limit, not a website absence; the runner reuses the prior bounded observations and does not retry that site.

## Commercial eligibility result

- **5** genuine public registration business cases.
- **2** directly confirmed HTTP 200 company-branded websites.
- **1** site with public company branding and an HTTP 429 latest origin recheck.
- **2** website attributions unresolved.
- **0** confirmed absent/outdated websites; **0** buyer demand confirmed.
- **0** business contact details, accepted lead deliveries, revenue receipts, CRM/database writes, paid traffic or outbound.

The June US web-agency post has **not** been reconfirmed; its stated $150 per fully accepted 50-record batch is not a contract, sale or payable order. This research should not be presented as a ready-to-deliver sample.

## Engineering evidence

The production independent Research/Buyer Scout contracts remain unchanged. The new module in this feature branch validates a known set of five original public company names, requires actual official source location-ID matches, deduplicates business identities and tracks company website observations separately from buyer acceptance or contact rights.

The one-shot review script uses the official public API and a pinned read-only website-observation receipt. It avoids further Shopify requests following HTTP 429, refuses source or receipt changes, and does not create any CRM record.

**Next Research owner gate:** identify an explicit business-authored web-design need; verify its company and lawful provenance; obtain the web agency's current legal identity, agreed purpose and acceptance/payment terms, then consider a separately approved five-business commercial sample. No personal contact enrichment, old EmpireDB resale or outbound now.

Government contractor tenders remain entirely separate. The Tennessee roofing commission concept requires appointment-quality and closed-job evidence rather than this website research.
