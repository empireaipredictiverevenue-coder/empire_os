#!/usr/bin/env python3
"""
Empire OS SI Brain — Adaptive Engine (si_adaptive.py)
======================================================
Real-time parameter adaptation layer.
Registers subsystems, pulls learned SI parameters, applies to live config.
Adoption every ~60s. Writes si_parameters + si_adaptation_log.

Subsystems: brain, switchboard, matching, corridor, outreach, scout.
"""

import sqlite3
import json
import time
import os
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"

# live config store (in-process; mirrors what hub.py would consume)
LIVE_PARAMS = {}

SUBSYSTEMS = ["brain", "switchboard", "matching", "corridor", "outreach", "scout"]


def _db():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def register_subsystem(subsystem, defaults=None):
    c = _db()
    defaults = defaults or {}
    for key, val in defaults.items():
        c.execute(
            "INSERT INTO si_parameters (subsystem, param_key, param_value, source) "
            "VALUES (?,?,?,?) ON CONFLICT(subsystem,param_key) DO NOTHING",
            (subsystem, key, float(val), "default"))
    c.commit()
    c.close()


def set_parameter(subsystem, param_key, value, reason="si_adapt"):
    c = _db()
    old = c.execute(
        "SELECT param_value FROM si_parameters WHERE subsystem=? AND param_key=?",
        (subsystem, param_key)).fetchone()
    old_v = old["param_value"] if old else None
    c.execute(
        "INSERT INTO si_parameters (subsystem, param_key, param_value, source) "
        "VALUES (?,?,?,?) ON CONFLICT(subsystem,param_key) DO UPDATE SET "
        "param_value=excluded.param_value, adopted_at=datetime('now'), source='si'",
        (subsystem, param_key, float(value), "si"))
    c.execute(
        "INSERT INTO si_adaptation_log (subsystem, param_key, old_value, new_value, reason) "
        "VALUES (?,?,?,?,?)", (subsystem, param_key, old_v, float(value), reason))
    c.commit()
    c.close()
    LIVE_PARAMS[f"{subsystem}.{param_key}"] = value


def adopt_parameters():
    """Pull all SI params into LIVE_PARAMS. Returns applied dict."""
    c = _db()
    rows = c.execute("SELECT subsystem, param_key, param_value FROM si_parameters").fetchall()
    c.close()
    applied = {}
    for r in rows:
        key = f"{r['subsystem']}.{r['param_key']}"
        LIVE_PARAMS[key] = r["param_value"]
        applied[key] = r["param_value"]
    return applied


def derive_from_outcomes():
    """SI learns params from recent outcomes (deterministic, no LLM)."""
    c = _db()
    # global avg win rate across strategies
    g = c.execute("SELECT AVG(win_rate) awr, COUNT(*) n FROM si_strategies").fetchone()
    c.close()
    awr = g["awr"] or 0.0
    n = g["n"] or 0
    if n >= 3:
        # low win rate -> boost outreach intensity + widen radius
        radius = 15 + (0.4 - min(awr, 0.4)) * 50
        intensity = 0.5 + (0.4 - min(awr, 0.4)) * 1.0
        set_parameter("matching", "radius_mi", round(radius, 1), "outcome_learn")
        set_parameter("outreach", "intensity", round(min(1.0, intensity), 2), "outcome_learn")
    return adopt_parameters()


def loop(stop_event=None, interval=60):
    """Background adoption loop. Adopt params every interval seconds."""
    for s in SUBSYSTEMS:
        register_subsystem(s)
    while True:
        if stop_event and stop_event.is_set():
            break
        derive_from_outcomes()
        time.sleep(interval)


if __name__ == "__main__":
    applied = derive_from_outcomes()
    print("[si_adaptive] applied:", len(applied), "params")
    for k, v in list(applied.items())[:8]:
        print(f"  {k} = {v}")
