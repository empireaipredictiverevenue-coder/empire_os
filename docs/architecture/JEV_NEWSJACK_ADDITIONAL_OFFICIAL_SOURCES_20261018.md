# Additional Public Sources — Empire JEV Traffic

18 October 2026. Feature worktree only. No production activation.

## Verified new sources

**US Federal Register**: https://www.federalregister.gov/developers/documentation/api/v1

The documented API is keyless. Added a manual search adapter that maps dated government records into the existing JEV research review. Publication dates have day-only precision, so a date is not converted to an invented UTC hour. Generic combined filing notices are filtered before review.

**GOV.UK Content API**: https://content-api.publishing.service.gov.uk/

Added metadata verification for an exact, already-discovered GOV.UK page. First publication and last update remain distinct. Withdrawn or redirecting pages do not become editorial evidence.

Implementation: `empire_os/jev_newsjack_official_sources.py`
CLI: `scripts/review_jev_official_news_sources.py`
Tests: `tests/test_jev_newsjack_official_sources.py`

Examples (explicit, manual, non-publishing):

```sh
cd /home/ubuntu/empire_worktrees/jev_newsjack_traffic_20261018
/srv/empire_os/.venv/bin/python -m scripts.review_jev_official_news_sources --federal-register-term solar --sector solar --as-of 2026-10-18T18:00:00+00:00 --limit 10
/srv/empire_os/.venv/bin/python -m scripts.review_jev_official_news_sources --govuk-url https://www.gov.uk/guidance/approved-document-l-energy-and-greenhouse-gas-emissions-frequently-asked-questions --sector solar --as-of 2026-10-18T18:00:00+00:00
```

18 October live verification: both official endpoints responded. The US solar search returned a sector-specific record older than the seven-day news window, and the GOV.UK article was originally published in September. Both were correctly held as stale rather than marketed as breaking news.

## Wider source roadmap

Reuse existing last30days (Techmeme, Reddit RSS, Hacker News, YouTube), first-party Search Intelligence and GSC. Consider GDELT DOC 2.0 only after retesting its connectivity: the EmpireOS test timed out. Google Trends API is an access-limited alpha; do not assume working access. Later official datasets could include Ofgem, ONS and US EIA where directly relevant to verified offers.

No paid API, new feed daemon, scheduled crawler, outbound messages, publications, checkout action, or live site mutation.

Remaining: source corroboration, real current event discovery, relevant existing landing page live proof, editorial brief acceptance, and observed attributed enquiries.
