# Empire AI YouTube Research v1 — Inside Existing Media OS
Date: 2026-10-17. OBSERVE-only. No vidIQ credits, payments, publishing or new service.

## Verified first-party capabilities
- Existing: `empire_os/youtube_intelligence.py` (video normalization, observed outliers), `empire_os/youtube_read_adapter.py` (official Data API/owned Analytics), `empire_os/media_youtube_growth_command_centre.py` (owned channel).
- Added: strict parsing of standard video/live/Shorts links, read-only YouTube oEmbed title/creator/thumbnail without an API key, documented creator chapter extraction, bounded one-page official topic search, and a single CLI `scripts/review_youtube_video_readonly.py`.
- Direct public metadata requires no third-party service credits. There is no general transcript download, no full-video scene recognition and no competitor private analytics.
- `--query` requires an existing YouTube Data API key and explicit `--allow-one-search-call`. Official Oct 2026 docs say `search.list` has a separate default 100 calls/day quota bucket, cost one unit in that bucket; check actual GCP project quotas before operationalising.
- The current `/etc/empire_os.env` did not expose a configured YouTube API key / access token to this inspector during the test; tool gracefully reports unavailable rather than hallucinating results.
- The official YouTube Data API `captions.download` requires permission to edit the video; it is not a universal competitor transcript service.

## Verified user example
Link: https://www.youtube.com/watch?v=j6JlWhDw-2w
Title (via official oEmbed): Make LONG AI Videos FREE & UNLIMITED (No Watermark)
Creator: Paul Ponna Official
Video length from current public metadata observation: 4734 seconds (78m54s).
Description supplied by creator includes 24 chapter markers; the active new CLI parsed all 24.
Captions endpoint returned an empty response to this environment, so DO NOT claim to have reviewed speech or visual content. Only chapter titles were inspected. Video may promote paid VideoExpress/TalkingPhotos etc, and 'free/unlimited' is a title claim, not something Empire has independently verified.

## Practical production-operator prompt stages (reusable inside existing Media OS)

**1. Research + provenance**
> Use this video title and creator-provided chapters as inspiration, not proof of what the entire video shows. Identify candidate production methods. Mark every content claim as verified, inferred from chapter label, or unknown. Do not reproduce copyrighted footage or assume that vendor services are free.

**2. Reference-led design**
> Compare the proposed Empire AI scene to the founder-approved reference style (deep navy/black, electric blue, controlled warm gold, official globe brand mark). Avoid website screen recordings, slideshow treatment, false data visualizations and generic AI visuals. Specify genuine shot action and timing. Reject unattributed external media.

**3. Script-to-presenter contract**
> Draft 20–30 seconds of specific, grounded spoken words. The presenter must say those exact words. Do not misrepresent the original founder's earlier footage as a newly spoken script. Use the authentic face/voice source only with permission and a validated real talking-avatar generator; until compute is funded, request a fresh exact script recording or use voice-only narration with no synthetic lip claims.

**4. Multi-pass motion design**
> Pass 1: story beats, presenter placements and permitted source footage. Pass 2: kinetic camera, credible 3D spatial animations (not still slides), source-linked data cues. Pass 3: soundtrack, readable typography, VO ducking, deliberate transitions and correct 9:16/16:9 safe areas. The final cut must be demonstrably different from the rejected V1/V2 promos.

**5. QC and founder approval**
> Decode all frames, sample the timeline at every transition and critical caption, verify face/logo identity, audio sync, clipping, pacing and screen-recording absence. Compare the result against the reference, list concrete failures, fix and re-test before sharing. No YouTube upload without specific founder approval.

## Existing infrastructure only
- Research: YouTube Data API adapter + `youtube_intelligence`.
- Planning: ASTRA + Media OS timeline.
- Graphics and edit: existing FFmpeg/HyperFrames/OpenMontage editor capability (OpenMontage still review-gated).
- Measurement: existing YouTube Growth Command Centre and canonical channel binding.
- Deferred: GPU facial/avatar synthesis until funded by verified revenue.

## Commands
```bash
cd /srv/empire_os
./.venv/bin/python scripts/review_youtube_video_readonly.py --url 'https://www.youtube.com/live/j6JlWhDw-2w'
# To add creator-supplied chapter labels without claiming a transcript:
./.venv/bin/python scripts/review_youtube_video_readonly.py --url 'https://www.youtube.com/watch?v=j6JlWhDw-2w' --description-file /path/to/creator_description.txt
# Official topic discovery after configuring the read-only key:
./.venv/bin/python scripts/review_youtube_video_readonly.py --query 'cinematic AI business explainers' --allow-one-search-call
```

No scheduled scraper, competitor surveillance, paid API, download or new runtime is authorised by this v1.
