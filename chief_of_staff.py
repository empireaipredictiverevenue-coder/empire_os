#!/usr/bin/env python3
"""
Empire OS — Chief of Staff Agent (C-suite).
Translates CEO directives + OKF into agent tasks. Owns REPUTATION mandate:
monitors relationship graph + interaction quality, routes deep-connection
tasks to Business Manager. Writes task queue to /root/feedback/cos_tasks.jsonl.

Runs as persistent loop. Tick 15m.
"""
import json, time, os, sys

FEEDBACK = "/root/feedback"
OKF = f"{FEEDBACK}/okf.json"
GRAPH = f"{FEEDBACK}/relationship_graph.json"
QUAL = f"{FEEDBACK}/quality.json"
TASKS = f"{FEEDBACK}/cos_tasks.jsonl"
DIRECTIVES = f"{FEEDBACK}/ceo_directives.jsonl"
TICK = 900
SOUL = "/root/empire_os/empire_os/agents/souls/chief_of_staff_SOUL.md"
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
    out = {}
    for p, k in [(OKF, "okf"), (GRAPH, "graph"), (QUAL, "quality")]:
        try:
            out[k] = json.load(open(p))
        except Exception:
            out[k] = {}
    return out


def reason(state):
    """CoS logic: turn CEO directives + reputation metrics into tasks."""
    tasks = []
    # reputation mandate: low interaction quality -> deepen relationships
    q = state.get("quality", {}).get("avg_quality", 1.0)
    if q < 0.8:
        tasks.append({"for": "business_manager", "type": "deepen_relationships",
                      "detail": f"Interaction quality {q} < 0.8 — prioritize "
                                f"personalized nurture to top-degree graph nodes.",
                      "priority": "high"})
    g = state.get("graph", {})
    if g.get("node_count", 0) < 5000:
        tasks.append({"for": "business_manager", "type": "grow_graph",
                      "detail": "Relationship graph under 5k nodes — mine CRM for "
                                "referral edges (shared email domains).",
                      "priority": "med"})
    # forward any open CEO directives as tasks
    try:
        for line in open(DIRECTIVES):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            tasks.append({"for": "business_manager", "type": d.get("type"),
                          "detail": d.get("msg"), "priority": d.get("priority", "med"),
                          "from": "CEO"})
    except Exception:
        pass
    if not tasks:
        tasks.append({"for": "business_manager", "type": "hold",
                      "detail": "All mandates on track.", "priority": "low"})
    return tasks


def act(tasks):
    for t in tasks:
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "role": "ChiefOfStaff", **t}
        with open(TASKS, "a") as f:
            f.write(json.dumps(rec) + "\n")
        if _HABIT:
            hm.record("cos", "task", {"type": t.get("type"), "for": t.get("for")})
        print(f"[cos] -> {t['for']}: {t['type']}")


def loop():
    os.makedirs(FEEDBACK, exist_ok=True)
    print("[cos] agent live — reputation orchestration")
    while True:
        try:
            act(reason(observe()))
        except Exception as e:
            print(f"[cos] err: {e}")
        time.sleep(TICK)


if __name__ == "__main__":
    loop()
