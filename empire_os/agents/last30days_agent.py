"""
last30days Agent — headless runner for the /last30days research engine.

Runs the engine (empire_os/skills_library/last30days/scripts/last30days.py)
per topic, captures its JSON, scrubs secrets, and writes artifacts to
/root/feedback/last30days_*.jsonl ONLY (artifact guardrail — same as
North-mini). Real public signals (Reddit/HN/Polymarket/GitHub are keyless)
feed Empire OS market-intel + lead-signal pipelines.

No external mutation, no charging, no secrets in output. Free-tier safe:
bounded timeout + retries, skip-on-fail (never hangs the daemon).
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
from empire_os.agents.guardrails import scrub_secrets, safe_write

ENGINE = Path("/root/empire_os/empire_os/skills_library/last30days/scripts/last30days.py")
FEED = Path("/root/feedback")
OUT = FEED / "last30days_runs.jsonl"
MODEL = "cohere/north-mini-code:free"
TICK = 1800  # 30 min
RUN_TIMEOUT = 120  # engine hard cap (real network)
MAX_RETRIES = 2

# Topics Empire OS cares about (market-intel + competitor + lead-signal).
TOPICS = [
    "open source lead generation tools",
    "AI sales outreach automation",
    "B2B lead generation market trends",
    "Solana payments adoption",
    "AI agent frameworks production",
]

import logging
log = logging.getLogger("last30days")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _slug(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", topic.lower()).strip("_")[:40]


def run_engine(topic: str) -> dict | None:
    """Run the engine headless (zero-config sources, real network)."""
    cmd = [
        sys.executable, str(ENGINE), topic,
        "--search", "reddit,hackernews,polymarket,github,jobs",
        "--emit", "json", "--quick", "--no-browser-cookies",
        "--days", "30",
    ]
    for attempt in range(MAX_RETRIES + 1):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=RUN_TIMEOUT, cwd=str(ENGINE.parent))
            if proc.returncode != 0:
                log.warning("engine rc=%s attempt=%s: %s", proc.returncode,
                            attempt, proc.stderr[:200])
                continue
            # Extract the outermost JSON object from stdout (engine prints
            # status lines before/after the JSON). Walk from the last '{'
            # using a brace counter so we grab the complete final object.
            out = proc.stdout
            start = out.rfind("{")
            if start == -1:
                log.warning("no JSON in engine output attempt=%s", attempt)
                continue
            depth = 0
            end = -1
            for i in range(start, len(out)):
                if out[i] == "{":
                    depth += 1
                elif out[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            if end == -1:
                log.warning("unbalanced JSON attempt=%s", attempt)
                continue
            return json.loads(out[start:end + 1])
        except subprocess.TimeoutExpired:
            log.warning("engine timeout topic=%s attempt=%s", topic, attempt)
        except json.JSONDecodeError as e:
            log.warning("engine json err topic=%s attempt=%s: %s", topic, attempt, e)
    return None


def synthesize(topic: str, data: dict) -> str:
    """One-line takeaway from the engine JSON (no LLM needed = free).

    Real engine shape: top-level keys are SOURCE names (reddit, hackernews,
    polymarket, github, jobs), each a list of candidate dicts with
    title/summary/engagement/{points,comments}/url/source.
    """
    items = []
    for src, rows in data.items():
        if isinstance(rows, list):
            for r in rows:
                if isinstance(r, dict):
                    eng = r.get("engagement", {})
                    if isinstance(eng, dict):
                        score = eng.get("points", 0) + eng.get("comments", 0)
                    else:
                        score = int(eng or 0)
                    items.append((score, r.get("source", src),
                                  r.get("title", "?"), r.get("summary", "")))
    if not items:
        return f"No signal for '{topic}' in last 30 days (sources quiet)."
    items.sort(key=lambda x: -x[0])
    top = items[0]
    return (f"'{topic}': {len(items)} signals across {len(set(i[1] for i in items))} "
            f"sources; top ({top[0]} eng, {top[1]})='{top[2]}' — {top[3][:120]}")


def cycle_once() -> None:
    for topic in TOPICS:
        data = run_engine(topic)
        if not data:
            log.warning("skip (no data) topic=%s", topic)
            continue
        clean = scrub_secrets(json.dumps(data))
        record = {
            "ts": time.time(),
            "engine": "last30days",
            "topic": topic,
            "takeaway": scrub_secrets(synthesize(topic, data)),
            "data": json.loads(clean),
        }
        safe_write(OUT, json.dumps(record) + "\n", "artifact", "last30days")
        # per-topic artifact for easy consumption by North-mini / outreach
        safe_write(FEED / f"last30days_{_slug(topic)}.jsonl",
                   json.dumps(record) + "\n", "artifact", "last30days")
        log.info("wrote artifact topic=%s", topic)


def main() -> None:
    log.info("last30days agent start — %s topics, tick=%ss", len(TOPICS), TICK)
    while True:
        try:
            cycle_once()
        except Exception as e:  # never die
            log.exception("cycle error: %s", e)
        time.sleep(TICK)


if __name__ == "__main__":
    main()
