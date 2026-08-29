#!/usr/bin/env python3
"""empire_strategist_to_cos — pipe the latest empire_strategist plan into
the chief-of-staff task queue.

Empire Strategist emits to /root/feedback/empire_strategist_plans.jsonl.
Chief of Staff consumes /root/feedback/cos_tasks.jsonl. Each cycle we
read the newest plan, summarize it as a task, and append.

Idempotent. Always exit 0. Run from cron or systemd timer.
"""
from __future__ import annotations
import json
import os
import sys
import time

SOURCE = "/root/feedback/empire_strategist_plans.jsonl"
TARGET = "/root/feedback/cos_tasks.jsonl"
STATE = "/root/feedback/empire_strategist_to_cos.state.json"


def _read_last_plan() -> dict | None:
    if not os.path.exists(SOURCE):
        return None
    last = None
    with open(SOURCE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            last = row
    return last


def _load_state() -> dict:
    if not os.path.exists(STATE):
        return {"last_seen_ts": ""}
    try:
        return json.loads(open(STATE).read())
    except Exception:
        return {"last_seen_ts": ""}


def main() -> int:
    plan = _read_last_plan()
    if not plan:
        print("no empire_strategist plan to forward", flush=True)
        return 0

    ts = plan.get("ts", "")
    state = _load_state()
    if ts and ts == state.get("last_seen_ts", ""):
        print(f"plan at {ts} already forwarded; nothing to do", flush=True)
        return 0

    doc = plan.get("doc") or {}
    ptype = doc.get("type", "")
    thesis = doc.get("thesis", "")[:400] or doc.get("decision", "")[:400] or \
             doc.get("product", "")[:400] or json.dumps(doc)[:400]
    plays = doc.get("plays", []) or doc.get("features", []) or \
            doc.get("next_actions", []) or []
    play_summary = ""
    for p in plays[:3]:
        if isinstance(p, dict):
            play_summary += " | " + str(p.get("name", p.get("step", "")))[:80]
        else:
            play_summary += " | " + str(p)[:80]

    next_3 = doc.get("next_3") or doc.get("next_actions") or \
             doc.get("mvp_steps", [])
    next_3_text = ""
    for n in next_3[:3]:
        next_3_text += " / " + str(n)[:90]

    task = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        "source_agent": "empire_strategist",
        "plan_ts": ts,
        "plan_type": ptype,
        "task_type": "strategic_play",
        "title": f"Empire Strategist {ptype}: {thesis[:120]}",
        "body": f"{thesis}{play_summary}",
        "next_3": next_3_text.strip(" /"),
        "status": "queued",
        "owner_agent": "cos",
    }

    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    with open(TARGET, "a") as f:
        f.write(json.dumps(task) + "\n")

    state["last_seen_ts"] = ts
    open(STATE, "w").write(json.dumps(state))
    print(f"forwarded plan {ts} (type={ptype}) to {TARGET}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
