# EmpireOS Muse — native social publisher and historical syndication recovery

**20 October 2026. Existing Muse owner, isolated branch** `feature/meta-social-intel-research-20261020`. No live social channel, Meta business asset, marketing spend or CRM outcome was changed.

## Recovered original implementation

- Greg Isenberg, *Meta Muse Will Create 1,000 Millionaires* (19 Oct 2026): `https://www.youtube.com/watch?v=tpZOU1ugODQ`.
- Existing source memo: `docs/research/META_MARKET_VALIDATION_AGENT_PILOT_PROTOCOL_20261020.md`.
- Historical EmpireOS Social Syndication: `83cf4ecd` (July 2026) created `social_syndication.py` and `social_youtube.py`; `81a9f7f6` (13 Oct) recovered only **governed repurposing structure**, not live uploader/legacy credentials. Historical memo: `docs/media/EMPIRE_YOUTUBE_SOCIAL_SYNDICATION_RECOVERY_20261013.md` (in that old media commit). Legacy `/root/empire_os` paths, obsolete OAuth, credential-triggered publishing and external paid-model calls must never be restored.
- The current Muse worktree already has `empire_os.media_repurposing.content_fingerprint` and `duplication_guard`. We reuse canonical Media OS fingerprints and content lineage, **not a second social publishing daemon**.

## This update makes Muse much more useful

- `empire_os/agents/meta_market_priority_intelligence_v1.py` connects read-only canonical Exchange inventory to the Muse research queue, ranking **non-solar** market/corridor blockers. The founder's separate solar owner keeps UK solar (9 records). These are workload priorities, not demand probabilities. The current 176 row snapshot produced 87 non-solar market groupings, with 15 non-solar selections missing usable routing fields. No customer promotion.
- The six **Empire-authored**, non-verbatim video-derived prompts cover niche/city qualification, explicitly researching relevant Facebook Group topics under permission, Marketplace/Instagram business-source research, source cleaning, owned audience and eventually vertical product economics.
- `empire_os/agents/meta_muse_social_operations_v1.py` produces 14 days of Facebook posts, Instagram Stories, carousel copy, four Instagram Reel **storyboards** (not video files), keywords and hashtags, a Page/IG professional account setup checklist, a starter metrics contract and a separate $0-approved Meta ads brief.
- `empire_os/agents/meta_muse_social_syndicate_v1.py` is **our own social poster outbox preview**: 14 original post drafts become 28 Facebook/Instagram variants. Original source IDs and content fingerprints are carried across; per-platform/day deterministic idempotency keys, historical duplicate holds, rights/QC, account verification and explicit editorial approval gates are required before any MCP write. Media lineage references are not proofs of an existing rendered/licensed asset.
- `empire_os/agents/meta_muse_mcp_handoff_v1.py` describes the exact owned publisher → MCP provider boundary. It deliberately **does not invent executable Metricool MCP tool names** or treat a ChatGPT plugin installation as evidence an authorised Meta account is connected. This is not an installed EmpireOS MCP connector or live remote action.

## Existing-platform integration, not provider lock-in

The content calendar, original source lineage, asset fingerprints, scheduling intentions, duplicate/rejection checks and performance data should stay with the native EmpireOS publisher. The **authorised MCP backend** is a swappable adapter:

1. Obtain connected provider/brand identity and scope through actual provider tool discovery, including Facebook Page and Instagram Professional identities. A Facebook/Instagram Page must first be created/linked through separately approved Meta business-asset setup where the connected provider does not support such actions.
2. Fetch existing scheduled/published content and aggregate analytics read-only before preparing any new provider post; dedupe the exact destination/platform and media/content digest.
3. Create finished owned image/video assets through existing Media OS production and independent rights/QC checks (the Reel scripts alone are **not** actual Reels).
4. Obtain explicit release approval for exact account, media, copy, date/timezone and post; call only the discovered, account-authorised provider MCP action.
5. Reconcile actual provider-created/scheduled/published IDs and handle partial errors without blind retry. Never infer success from submission.
6. Use real provider metrics and first-party consented attribution to learn; views/clicks/hashtags are not accepted customer orders or actual subscription MRR.
7. Keep **Meta Ads off** until a separate founder approval with genuine account/billing authority, tracking consent, positive unit economics and a concrete spending cap. No paid traffic in the current organic programme.

### Current CLI: read-only run + private owner outbox

```bash
cd /home/ubuntu/empire_worktrees/meta_social_intelligence_research_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.run_meta_market_validation_agent \
  --exchange-snapshot /srv/empire_os/runtime/commercial_exchange/latest.json \
  --video-prompt-pack \
  --social-draft-niche roofing \
  --social-draft-market 'tampa, fl' \
  --social-syndicate-preview --mcp-handoff
```

The command writes only its own isolated runtime files, including a private `0600` `runtime/meta_market_research_agent/owned_social_poster_queue.json`. No external request or social publishing. Append `--report-only` to avoid file writes; prints the draft review instead. Do not commit the private runtime file.

## Not complete/next owner gates

The following are **not** activated or proved: actual Facebook Page creation, Instagram business linking, branded finished visual/video files, connected Metricool brand accounts, executable MCP provider write transport, live schedules/publications, validated source rights from social networks, advertisements or real funnel conversion. Dedicated connector write-adapter acceptance requires a verified provider manifest and an authorised account; production deployment remains held.

Keep the separate solar agent assignment, original Buyer Scout/A2A rights boundaries, no paid traffic, email-first customer preference and canonical EmpireDB identity/finance truth.
