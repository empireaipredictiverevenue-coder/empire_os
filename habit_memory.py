#!/usr/bin/env python3
"""
Empire OS — Agent Habit Memory (persistent across ticks/restarts).
Operational habit layer: each agent reads its habit log on boot, appends on tick.
This is what makes "everlasting good habits" real — not a markdown doc.

No external deps. One JSONL per agent at /root/feedback/habits/<role>.jsonl
"""
import json, os, time

HABIT_DIR = "/root/feedback/habits"


def _path(role):
    os.makedirs(HABIT_DIR, exist_ok=True)
    return os.path.join(HABIT_DIR, f"{role}.jsonl")


def load(role, limit=50):
    """Read recent habit records for a role (most-recent first)."""
    p = _path(role)
    if not os.path.exists(p):
        return []
    try:
        lines = [l for l in open(p).read().splitlines() if l.strip()]
        return [json.loads(l) for l in lines[-limit:]]
    except Exception:
        return []


def record(role, event, meta=None):
    """Append a habit event. event = 'directive'|'task'|'scan'|'asset'|'exec' etc."""
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "role": role, "event": event, "meta": meta or {}}
    with open(_path(role), "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def repeat_count(role, event, key=None, value=None, window=5):
    """How many of the last `window` events of type `event` match key==value.
    Used to detect 'same directive 3 ticks running' -> kill it."""
    hist = load(role, limit=window)
    n = 0
    for h in hist:
        if h.get("event") != event:
            continue
        if key is None:
            n += 1
        else:
            m = h.get("meta", {})
            if m.get(key) == value:
                n += 1
    return n


if __name__ == "__main__":
    record("ceo", "directive", {"type": "scale_triggers", "progress": 0.197})
    print("habit recorded. recent:", load("ceo", 3))
