# Empire AI Search Traffic — GSC Landing-Page Status Findings

**Observed:** 18 October 2026. Read-only; no website deployment or redirects.

**Measurement source:** live Empire Search Intelligence loopback
`http://127.0.0.1:8771/v1/search/search-console/observations`,
property `sc-domain:empire-ai.co.uk`, window 8–16 October 2026.
All reported click/impression numbers are query+page measurements, not
visitor counts, buyer intent, attribution or sales.

## Exact measured scope

7 GSC query/page rows, 5 distinct search terms, 6 distinct URLs,
16 impressions and **0 clicks** in this bounded returned dataset.

- `https://empire-ai.co.uk/`: 200; 6 impressions, 0 clicks, branded `empire ai`.
- `https://www.empire-ai.co.uk/`: 200; 2 impressions, 0 clicks, `ai empire` and `empire ai`.
- `https://empire-ai.co.uk/aeo/accounting/TAM/`: 404; 1 impression, 0 clicks; long-form question about which TAM accounts are ready to buy.
- `https://empire-ai.co.uk/aeo/antenna-install/EUG/`: 404; 4 impressions, 0 clicks; `antenna approvals`.
- `https://empire-ai.co.uk/aeo/antenna-install/FAR/`: 404; 2 impressions, 0 clicks; `antenna approvals`.
- `https://empire-ai.co.uk/aeo/leak-detection/DAL/`: 404; 1 impression, 0 clicks; `empire leaks`.

All HTTP statuses were independently checked by GET requests to the specific
owned HTTPS URLs on 18 October. Four of six distinct URLs returned 404.
Their combined **8 impressions** represent half of the 16 impressions
in this sample. None generated recorded clicks in this period, so do not
claim diverted visitors or lost revenue.

## Existing owner and no-duplicate finding

Canonical `/srv/empire_os/empire_os/search_intelligence/seo_publication_impact_review.py`
already documents the legacy TAM route as a 404 and refers to newer,
original Commercial-page buyer guidance; consult website and SEO owners
before changing route behaviour. Other AEO routes may also have intentional
gating. `owned_indexability_review.py` already owns indexability evidence.
Do not create a competing scanner or directly rewrite route rules.

## Actionable handoff for ASTRA / website + Search owner

1. Cross-check the already-owned legacy AEO route inventory and the current
   approved canonical landing pages before planning any redirect.
2. For each query/page pairing, decide whether an original useful page exists
   and is in-scope; only then consider a topical, permanent redirect.
3. If a route is intentionally gone or disallowed, preserve its policy and
   allow the search engine to drop it; do not redirect irrelevant URLs to
   the homepage or publish thin filler for impressions.
4. Use existing Search Console indexing/inspection and existing site owner
   test pipeline to verify effects after an approved release.
5. Evaluate new GSC clicks, conversions, and qualified enquiries separately.
   A zero-click 16-impression sample cannot support revenue claims.

**Source claim:** confirmed observations only. **Execution:** none.
**Priority:** SEO / website indexability and existing landing-page relevance,
ahead of unattended NewsJack content publication.
