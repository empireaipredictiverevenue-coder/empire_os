# Empire AI YouTube Intelligence V2 — Commercial Opportunity Review

Date: 2026-10-17. Owner: existing Empire Media OS.

## Implemented
- `empire_os.youtube_intelligence.review_youtube_commercial_opportunities()`: ranks source-cited, recent, normalized public YouTube observations by sector relevance, baseline-relative outlier ratio, freshness and UK/USA textual cues.
- Sectors: roofing, solar, HVAC, dental, AI consultancy and enterprise AI. Sector/market cues are textual research signals only, not validated buyer interest or actual geography.
- Video comparisons require at least 3 comparable channel-baseline observations. Missing, stale and duplicate observations do not become priority candidates.
- Upstream commercial-capacity claims remain unverified in this module, even when input includes evidence references.
- `scripts/review_youtube_video_readonly.py --opportunities-file /path/to/packet.json` accepts the existing normalized Media OS observations, without another service or database.
- Output is OBSERVE only and contains no generated, sent or published media, inferred revenue, or activation authority.

## Verified
33 focused tests pass (YouTube reader, intelligence, Media workflow evolution and production contracts). No new GPU, paid API, third-party creator-data pipeline or video publication.

## Product limitations
This does **not** yet match or outperform vidIQ in breadth or measured outcomes.
- No authenticated full YouTube data feed active on current server; no API key was exposed at inspection time.
- Not video-age-normalized; a per-channel median is only an indicative comparison.
- No universal competitor transcript retrieval, video scene analysis, verified competitor retention, or fabricated private stats.
- No validated keyword search-volume or business-revenue estimation.
- No new cross-channel attribution; use the existing canonical YouTube -> CRM reconciliation for actual outcome evidence.

## Next milestone
Connect existing official YouTube Data API observations and Search Intelligence keyword evidence into a human-reviewed shortlist; compare against a stable set of competitors, and measure CTR, watch time, quality and qualified inquiries. Avoid new infrastructure; do not claim production-quality superiority until benchmarked.
