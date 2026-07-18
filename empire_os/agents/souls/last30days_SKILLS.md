# Last30days — Skill Spec

Used by `last30days_agent.py` when running the engine + persisting results.

## Engine invocation (fixed argv — no shell)

```
python3 empire_os/skills_library/last30days/scripts/last30days.py \
  "<topic>" --search reddit,hackernews,polymarket,github,jobs \
  --emit json --quick --no-browser-cookies --days 30
```

- Zero-config sources (no keys): reddit, hackernews, polymarket, github, jobs.
- `--emit json` → JSON on stdout (last `{...}` block). Parse that.
- `--quick` lowers latency. `--days 30` = last-30-days window.
- Real network. On rc!=0 / timeout / bad JSON → retry (max 2), then skip.

## Output artifact shape (written to /root/feedback/last30days_*.jsonl)

```json
{"ts": 0.0, "engine": "last30days", "topic": "...",
 "takeaway": "one-line signal summary",
 "data": {<engine JSON: top-level keys are SOURCE names
          (reddit/hackernews/polymarket/github/jobs), each an array of
          candidate dicts with title/summary/engagement/url/source>}}
```

- `takeaway` = top-engagement candidate across all sources (free, no LLM).
- All content secret-scrubbed before write.

## Topic list (market-intel + lead-signal)

Edit `TOPICS` in `last30days_agent.py`. Current:
- open source lead generation tools
- AI sales outreach automation
- B2B lead generation market trends
- Solana payments adoption
- AI agent frameworks production

## Consumption

- North-mini `agi_intel` cycle can read `last30days_*.jsonl` for real
  signals instead of pure-LLM guessing.
- Outreach/predictive agents can read takeaways as prospect-intent signals.
