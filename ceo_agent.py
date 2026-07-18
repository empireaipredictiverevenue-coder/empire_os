#!/usr/bin/env python3
"""
Empire OS — CEO Agent (C-suite).
Owns the OKF growth vision + machine-earning strategy. Reads okf.json,
sets direction, writes directives to /root/feedback/ceo_directives.jsonl.
Core mandate: REPUTATION + EXPONENTIAL GROWTH via the A2A/MCP supply layer.

Runs as a persistent loop (no cron). Tick 1h.
"""
import json, time, os, subprocess, sys

FEEDBACK = "/root/feedback"
OKF = f"{FEEDBACK}/okf.json"
DIRECTIVES = f"{FEEDBACK}/ceo_directives.jsonl"
TICK = 3600
SOUL = "/root/empire_os/empire_os/agents/souls/ceo_SOUL.md"
sys.path.insert(0, "/root/empire_os")
try:
    import habit_memory as hm
    _HABIT = True
except Exception:
    _HABIT = False


def load_soul():
    try:
        return open(SOUL).read()
    except Exception:
        return ""


def observe():
    try:
        return json.load(open(OKF))
    except Exception:
        return {}


def reason(state):
    """CEO logic: lowest-progress Objective -> 1-2 directives. SOUL-loaded.
    Habit: kill a directive repeated 3 ticks with <5% movement."""
    soul = load_soul()
    directives = []
    overall = state.get("overall_progress", 0)
    metrics = state.get("metrics", {})
    # lowest-progress objective = the lever
    objs = state.get("objectives", [])
    objs_sorted = sorted(objs, key=lambda o: o.get("progress", 1))
    if objs_sorted:
        low = objs_sorted[0]
        if low["id"] == "O1":
            directives.append({"type": "scale_triggers",
                "msg": "O1 lowest (%.1f%%): expand 6-source verticals 43->100 + add Yandex/Marginalia." % (low["progress"]*100),
                "priority": "high"})
        elif low["id"] == "O3":
            directives.append({"type": "machine_earning",
                "msg": "O3 lowest (%.1f%%): publish MCP endpoint to agent dirs + pitch 3 agent networks (USDC)." % (low["progress"]*100),
                "priority": "high"})
        elif low["id"] == "O2":
            directives.append({"type": "reputation",
                "msg": "O2 lowest (%.1f%%): deepen buyer connections, build referral edges." % (low["progress"]*100),
                "priority": "med"})
        elif low["id"] == "O4":
            directives.append({"type": "self_influence",
                "msg": "O4 lowest (%.1f%%): build AEO checker + get external agents to pull self_influence." % (low["progress"]*100),
                "priority": "med"})
    # habit: if same directive 3 ticks running, kill + pick different lever
    if _HABIT:
        for d in list(directives):
            n = hm.repeat_count("ceo", "directive", key="type", value=d["type"], window=3)
            if n >= 3:
                directives = [{"type": "pivot",
                              "msg": "Directive '%s' stalled 3 ticks (<5%% move) — pivoting to different lever." % d["type"],
                              "priority": "high"}]
                break
    if not directives:
        directives.append({"type": "hold", "msg": "On track — maintain cadence.", "priority": "low"})
    return directives


def act(directives):
    for d in directives:
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "role": "CEO", **d}
        with open(DIRECTIVES, "a") as f:
            f.write(json.dumps(rec) + "\n")
        if _HABIT:
            hm.record("ceo", "directive", {"type": d.get("type"), "msg": d.get("msg", "")[:60]})
        print(f"[ceo] -> {d['type']}: {d['msg'][:60]}")


def loop():
    os.makedirs(FEEDBACK, exist_ok=True)
    soul = load_soul()
    print(f"[ceo] agent live — reputation + exponential growth | soul {len(soul)}c loaded")
    if _HABIT:
        print(f"[ceo] habit memory ON ({len(hm.load('ceo'))} prior ticks)")
    while True:
        try:
            act(reason(observe()))
        except Exception as e:
            print(f"[ceo] err: {e}")
        time.sleep(TICK)


if __name__ == "__main__":
    loop()
