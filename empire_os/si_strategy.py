#!/usr/bin/env python3
"""
Empire OS SI Brain — Strategy Evolution Engine (si_strategy.py)
===============================================================
Continuous learning + optimization of campaign strategies.
Manages strategy genomes, scores by outcomes, evolves every 5 min
via mutation/deactivation. Writes to si_strategies / si_evolution_events.

No external LLM required — deterministic evolution + optional Ollama hook.
"""

import sqlite3
import json
import os
import random
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")


def _db():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def load_strategies():
    c = _db()
    rows = c.execute("SELECT * FROM si_strategies").fetchall()
    c.close()
    return [dict(r) for r in rows]


def record_outcome(strategy_id, calls_generated=0, revenue_captured=0.0, win=0, meta=None):
    c = _db()
    c.execute(
        "INSERT INTO si_outcomes (strategy_id, calls_generated, revenue_captured, win, meta) "
        "VALUES (?,?,?,?,?)",
        (strategy_id, calls_generated, revenue_captured, win, json.dumps(meta or {})),
    )
    # roll up into strategy
    row = c.execute(
        "SELECT COUNT(*) n, COALESCE(SUM(win),0) w, "
        "COALESCE(SUM(revenue_captured),0) rev "
        "FROM si_outcomes WHERE strategy_id=?", (strategy_id,)).fetchone()
    n = row["n"] or 1
    win_rate = (row["w"] or 0) / n if n else 0.0
    rev = row["rev"] or 0.0
    conf = min(1.0, n / 20.0)
    c.execute(
        "UPDATE si_strategies SET win_rate=?, revenue_generated=?, confidence=? "
        "WHERE id=?", (win_rate, rev, conf, strategy_id))
    c.commit()
    c.close()
    return {"strategy_id": strategy_id, "win_rate": win_rate, "revenue": rev}


def mutate_genome(genome: dict, intensity=0.15):
    g = dict(genome)
    for k, v in g.items():
        if isinstance(v, (int, float)):
            delta = v * intensity * random.choice([-1, 1])
            g[k] = round(max(0, v + delta), 4)
    return g


def evolve(verbose=True):
    """One evolution pass. Promote winners, mutate, deactivate losers."""
    c = _db()
    rows = c.execute("SELECT * FROM si_strategies ORDER BY revenue_generated DESC").fetchall()
    events = []
    for r in rows:
        s = dict(r)
        if not s["active"]:
            continue
        genome = json.loads(s["genome"])
        # winner: clone + mutate into new variant
        if s["win_rate"] >= 0.4 and s["confidence"] >= 0.3:
            new_genome = mutate_genome(genome)
            new_name = f"{s['archetype'].lower()}_g{s['generations']+1}_{int(datetime.now().timestamp())%10000}"
            cur = c.execute(
                "INSERT INTO si_strategies (name, archetype, genome, active, generations) "
                "VALUES (?,?,?,1,1)", (new_name, s["archetype"], json.dumps(new_genome)))
            new_id = cur.lastrowid
            c.execute("INSERT INTO si_evolution_events (strategy_id, event_type, detail) VALUES (?,?,?)",
                      (s["id"], "promote_mutate", json.dumps({"child": new_name, "child_id": new_id})))
            events.append(f"promote {s['name']} -> {new_name}")
            c.execute("UPDATE si_strategies SET generations=generations+1 WHERE id=?", (s["id"],))
        # loser: deactivate if low confidence + negative
        elif s["win_rate"] < 0.1 and s["confidence"] >= 0.5:
            c.execute("UPDATE si_strategies SET active=0 WHERE id=?", (s["id"],))
            c.execute("INSERT INTO si_evolution_events (strategy_id, event_type, detail) VALUES (?,?,?)",
                      (s["id"], "deactivate", json.dumps({"reason": "low_win_rate"})))
            events.append(f"deactivate {s['name']}")
    # survival cap
    active = c.execute("SELECT COUNT(*) FROM si_strategies WHERE active=1").fetchone()[0]
    if active > 24:
        excess = c.execute(
            "SELECT id FROM si_strategies WHERE active=1 ORDER BY revenue_generated ASC "
            "LIMIT ?", (active - 24,)).fetchall()
        for e in excess:
            c.execute("UPDATE si_strategies SET active=0 WHERE id=?", (e["id"],))
    c.commit()
    c.close()
    if verbose:
        print("[si_strategy] evolution:", events or "no change")
    return events


if __name__ == "__main__":
    print("[si_strategy] active:", len([s for s in load_strategies() if s["active"]]))
    evolve()
