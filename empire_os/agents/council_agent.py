#!/usr/bin/env python3
"""
Empire OS v3 - Council agent (v4 with vote + ship_action execution).

Reads innovator's proposals, votes 3-up (engineer/finance/customer),
and on majority approve executes ship_action via hub /v1/innovator/ship.

Cadence: weekly (Sunday 23:00 UTC).
"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests

HUB = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
FB  = Path("/root/feedback")
LOG = FB / "council_decisions.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(7 * 24 * 3600)))


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level,
         "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    print(json.dumps(e), flush=True)


def read_proposals() -> list:
    p = Path("/root/feedback/innovator_proposals.jsonl")
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        if not line.strip(): continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("msg") == "emitted" and isinstance(e.get("scores"), dict):
            out.append(e)
    return out


def judge(proposal: dict) -> dict:
    """3 voters, weighted. Each scores ship/no-ship based on a heuristic."""
    voters = []
    # Engineer: prefers low build cost, high defensibility
    eng = (proposal["scores"]["build"] * 0.4
           + proposal["scores"]["defensibility"] * 0.4
           + proposal["scores"]["infra_cost"] * 0.2)
    # Finance: prefers high fy_money, low infra_cost
    fin = (proposal["scores"]["fy_money"] * 0.5
           + proposal["scores"]["infra_cost"] * 0.3
           + proposal["scores"]["market"] * 0.2)
    # Customer: prefers high market + build (i.e. fast to ship)
    cus = (proposal["scores"]["market"] * 0.5
           + proposal["scores"]["build"] * 0.3
           + proposal["scores"]["fy_money"] * 0.2)

    voters.append(("engineer", eng, 0.35))
    voters.append(("finance",  fin, 0.35))
    voters.append(("customer", cus, 0.30))

    weighted = sum(score * w for _, score, w in voters)
    votes = [(name, score, score >= 4.0) for name, score, _ in voters]
    return {
        "weighted_score": round(weighted, 3),
        "votes": [{"voter": v[0], "score": round(v[1], 2),
                   "ship": v[2]} for v in votes],
    }


def execute_ship(proposal: dict):
    try:
        r = requests.post(f"{HUB}/v1/innovator/ship",
                           json={"id": proposal["id"],
                                 "name": proposal["name"],
                                 "ship_action": proposal["ship_action"]},
                           timeout=10).json()
        return r
    except Exception as e:
        return {"error": str(e)[:200]}


def cycle():
    proposals = read_proposals()
    # only last week's
    week_ago = datetime.now(timezone.utc).timestamp() - 7 * 86400
    recent = [p for p in proposals
              if datetime.fromisoformat(p["ts"].replace('Z','+00:00')).timestamp() > week_ago]

    if not recent:
        log("CYCLE", "no_proposals_to_judge")
        return

    summary = {"shipped": [], "parked": [], "errors": []}
    for prop in recent:
        verdict = judge(prop)
        ship_count = sum(1 for v in verdict["votes"] if v["ship"])
        decision = "ship" if ship_count >= 2 else "park"
        log("DECISION", "council_vote",
            proposal=prop["name"], score=verdict["weighted_score"],
            votes=verdict["votes"], decision=decision)
        if decision == "ship":
            ship_result = execute_ship(prop)
            summary["shipped"].append({"name": prop["name"], "result": ship_result})
        else:
            summary["parked"].append(prop["name"])
    log("CYCLE", "council_summary",
        total=len(recent),
        shipped=len(summary["shipped"]),
        parked=len(summary["parked"]))


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] council v4 online - weekly cadence",
          flush=True)
    while True:
        try:
            cycle()
        except Exception as e:
            with open("/root/feedback/council_decisions.jsonl", "a") as f:
                f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                                    "level": "ERROR",
                                    "msg": "cycle_failed",
                                    "err": str(e)[:200]}) + "\n")
        time.sleep(INTERVAL)
