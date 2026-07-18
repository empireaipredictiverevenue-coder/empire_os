"""
Empire OS v3 - Deep Research Agent

Uses Ollama qwen2.5:7b to do multi-stage research against any
user-supplied or innovator-supplied question:

  1. decompose the question into 3-5 sub-questions
  2. gather free public data (Wikipedia, OSM, court listener,
     Reddit JSON, our internal leads corpus)
  3. reason over the data via the LLM
  4. write the answer to /root/feedback/research_log.jsonl +
     POST to /v1/swarm/audit-log as a "research" event

Cadence: weekly Monday 04:00 UTC (consumer of innovator proposals).
"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests

HUB  = os.environ.get("HUB_URL", "http://127.0.0.1:8000")
OLLAMA = os.environ.get("OLLAMA_URL", "http://10.218.156.211:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen2.5:7b")
FB   = Path("/root/feedback")
LOG  = FB / "research_log.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(7 * 24 * 3600)))


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(),
         "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)


def llm_think(prompt: str, max_chars: int = 6000) -> str:
    try:
        r = requests.post(f"{OLLAMA}/api/generate",
                          json={"model": LLM_MODEL, "prompt": prompt,
                                "stream": False},
                          timeout=180).json()
        return r.get("response", "")[:max_chars]
    except Exception as e:
        log("ERROR", "ollama_fail", err=str(e)[:200])
        return ""


def cycle():
    log("CYCLE_START", "deep-research cycle")
    log("INFO", "research_cycle_ready",
        note="waiting for innovator proposal input")
    # When innovator emits a proposal that needs deeper research,
    # call llm_think with the proposal text. v1 just emits a heartbeat.


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] deep-research online — {INTERVAL}s",
          flush=True)
    while True:
        try:
            cycle()
        except Exception as e:
            log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
