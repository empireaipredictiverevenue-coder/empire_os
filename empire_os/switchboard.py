"""
Empire OS — switchboard (AGI layer + SyntheticIntelligence)
============================================================

TwiML handles media. We handle routing+billing+AGI reasoning.

AGI layer:
  Before each call: Agent.observe(state) -> reason() -> act()
  SyntheticIntelligence.augment(state, decision) returns synthetic
  examples to prepend next prompt so the model improves over time.

  LLM endpoint: http://10.218.156.211:11434 (qwen2.5:7b on
  ornith-agent). 180s timeout — keep AGI moves small.

Endpoints:
  POST /v1/calls/place   {to, from, lane_key, lead_id}
  POST /v1/calls/hangup  {call_id, reason}
  POST /v1/calls/record  {call_id, rec_url, duration_s}
  POST /v1/calls/bid     {lane_key, cpm_cents, callback_url}
  GET  /v1/calls/active
  GET  /v1/bids/top?lane_key=
  GET  /v1/agi/last      last N AGI decisions
  GET  /v1/health

Run:  python3 /root/empire_os/empire_os/switchboard.py
"""
from __future__ import annotations
import json, os, secrets, sys, time
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core        import Agent, AgentContext
from empire_os.synthetic_intelligence import SyntheticIntelligence


# ── config ──
PORT        = int(os.environ.get("SWITCHBOARD_PORT", "9100"))
FEEDBACK    = Path("/root/feedback")
CALLS_LOG   = FEEDBACK / "calls.jsonl"
BIDS_LOG    = FEEDBACK / "bids.jsonl"
DECISIONS   = FEEDBACK / "agi_decisions.jsonl"
DEFAULT_FRM = os.environ.get("DEFAULT_FROM", "+188****0100")
OLLAMA_URL  = os.environ.get("OLLAMA_URL", "http://10.218.156.211:11434")
LLM_MODEL   = os.environ.get("LLM_MODEL", "qwen2.5:7b")
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "180"))

# ── persistence + auth + compliance ──
from empire_os.switchboard_db import (
    init_db, create_call, get_call, update_call_status, list_active_calls,
    place_bid, get_top_bid, list_bids, log_agi_decision, get_recent_decisions,
    get_tenant, is_scrubbed, add_scrub
)
init_db()

ACTIVE     = {}      # call_id -> dict (kept for in-flight only; source of truth is DB)
BIDS       = {}      # lane_key -> highest bid (cached from DB)
DEC_HIST   = deque(maxlen=200)


# ── AGI layer ──
def _agi():
    """Lazy AGI agent per call (each cycle is fresh — ~5s warm)."""
    ctx = AgentContext(state={"role": "switchboard", "level": "router"},
                       goal=("Maximize revenue per call by routing to the "
                             "highest-bidding buyer; never bid-shop; never "
                             "place a call when no buyer is in the lane."))
    return Agent(context=ctx, llm={"url": OLLAMA_URL, "model": LLM_MODEL,
                                   "timeout": LLM_TIMEOUT})

_synth = SyntheticIntelligence(llm={"url": OLLAMA_URL, "model": LLM_MODEL,
                                    "timeout": LLM_TIMEOUT},
                               n_synthetic=3)


def agi_decide(state: dict, decision: dict) -> dict:
    """Reason over state + decision. Returns augmented reasoning block.

    Agent API: act(decision: str) -> dict
    SyntheticIntelligence API: augment(state, decision) -> examples
    """
    decision_str = (f"{decision.get('action','?')}: "
                    f"{json.dumps(decision)[:160]}")
    try:
        agent = _agi()
        # first observe() to refresh internal state, then reason, then act
        agent.observe()
        agent.reason(state=state)
        raw = agent.act(decision=decision_str)
    except Exception as e:
        raw = {"ok": False, "error": str(e)[:160],
               "fallback": "use greedy: highest active bid wins"}
    try:
        examples = _synth.augment(state=state, decision=decision)
    except Exception as e:
        examples = {"error": str(e)[:160]}
    out = {"ts": now_iso(), "state": state, "decision": decision,
           "agi": raw, "synth": examples}
    DEC_HIST.appendleft(out)
    FEEDBACK.mkdir(parents=True, exist_ok=True)
    with open(DECISIONS, "a") as f:
        f.write(json.dumps(out) + "\n")
    return out


def now_iso(): return datetime.now(timezone.utc).isoformat()


def log(path, level, msg, **fields):
    e = {"ts": now_iso(), "level": level, "msg": msg, **fields}
    FEEDBACK.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f: f.write(json.dumps(e) + "\n")
    print(json.dumps(e), flush=True)


# ── HTTP ──
def _auth(req):
    key = req.headers.get("X-API-Key", "")
    t = get_tenant(key)
    if not t:
        return None
    return t

def _require_auth(handler, req):
    t = _auth(req)
    if not t:
        handler.send_json({"error": "invalid or missing X-API-Key"}, 401)
    return t

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self.send_json({"error": str(e)[:200]}, 400)
        r = self.path.split("?")[0]
        if r == "/v1/calls/place":  return self.place(body)
        if r == "/v1/calls/hangup": return self.hangup(body)
        if r == "/v1/calls/record": return self.record(body)
        if r == "/v1/calls/bid":    return self.bid(body)
        return self.send_json({"error": "not found", "path": r}, 404)

    def do_GET(self):
        if self.path.startswith("/v1/calls/active"):
            return self.send_json({"active": list_active_calls()}, 200)
        if self.path.startswith("/v1/bids/top"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            lk = q.get("lane_key", [None])[0]
            if not lk:
                return self.send_json({"error": "lane_key required"}, 400)
            bid = get_top_bid(lk)
            return self.send_json({"lane_key": lk, "top": bid}, 200)
        if self.path.startswith("/v1/agi/last"):
            n = int(self.path.split("n=")[-1]) if "n=" in self.path else 10
            return self.send_json({"decisions": get_recent_decisions(n)}, 200)
        if self.path.startswith("/v1/health"):
            return self.send_json({"ok": True, "calls": len(list_active_calls()),
                                   "bids": len(list_bids("")), "ts": now_iso()}, 200)
        return self.send_json({"error": "not found"}, 404)

    def log_message(self, *a, **k): pass

    # ── routes ──
    def place(self, body):
        # auth
        t = _require_auth(self, self)
        if not t: return
        to       = body.get("to", "")
        frm      = body.get("from", DEFAULT_FRM)
        lane_key = body.get("lane_key", "")
        lead_id  = body.get("lead_id", "")
        if not to or not lane_key:
            return self.send_json({"error": "to + lane_key required"}, 400)
        # TCPA scrub
        if is_scrubbed(to):
            return self.send_json({"error": "number on DNC list"}, 403)

        # DB create
        call_id = "call_" + secrets.token_hex(8)
        rec = create_call(call_id, lane_key, frm, to, lead_id)
        ACTIVE[call_id] = rec

        state    = {"to": to, "from": frm, "lane_key": lane_key,
                    "lead_id": lead_id, "bids_in_lane": len(list_bids(lane_key)),
                    "active_calls": len(list_active_calls()),
                    "tenant_id": t["tenant_id"]}
        decision = {"action": "place_call", "winner_bid": get_top_bid(lane_key)}
        agi_out  = agi_decide(state, decision)
        log_agi_decision(call_id, state, decision, agi_out.get("agi", {}), agi_out.get("synth", {}))

        rec["agi_decision_id"] = agi_out.get("ts")
        ACTIVE[call_id] = rec
        log(CALLS_LOG, "PLACE", "call placed",
            call_id=call_id, to=to, lane=lane_key,
            agi=agi_out.get("agi", {}).get("ok"))
        return self.send_json(rec, 200)

    def hangup(self, body):
        cid = body.get("call_id", "")
        reason = body.get("reason", "completed")
        rec = get_call(cid)
        if not rec:
            return self.send_json({"error": "unknown call_id"}, 404)
        update_call_status(cid, reason, ended_at=now_iso())
        if rec.get("winner_bid"):
            cost_cents = (rec.get("duration_s", 30) / 60.0
                          * rec["winner_bid"]["cpm_cents"])
            update_call_status(cid, reason, settled_cents=int(cost_cents))
            # G-1: meter to OpenMeter
            try:
                from empire_os.openmeter_client import meter_90s_sprint
                meter_90s_sprint(
                    cid, rec["winner_bid"]["buyer_id"],
                    rec["lane_key"], rec.get("duration_s", 0),
                    rec["winner_bid"]["cpm_cents"]
                )
            except Exception as e:
                log(CALLS_LOG, "METER_ERROR", "openmeter failed",
                    call_id=cid, error=str(e)[:160])
        log(CALLS_LOG, "HANGUP", "call ended",
            call_id=cid, reason=reason,
            settled=rec.get("settled_cents"))
        return self.send_json(get_call(cid), 200)

    def record(self, body):
        cid = body.get("call_id", "")
        if not get_call(cid):
            return self.send_json({"error": "unknown call_id"}, 404)
        update_call_status(cid, "recorded",
            rec_url=body.get("rec_url", ""),
            duration_s=body.get("duration_s", 0))
        log(CALLS_LOG, "RECORD", "call recorded",
            call_id=cid, dur=body.get("duration_s"),
            rec=body.get("rec_url"))
        return self.send_json({"ok": True}, 200)

    def bid(self, body):
        # auth for bid placement
        t = _require_auth(self, self)
        if not t: return
        lk    = body.get("lane_key", "")
        cpm   = int(body.get("cpm_cents", "0"))
        cb    = body.get("callback_url", "")
        if not lk or cpm <= 0:
            return self.send_json({"error": "lane_key + cpm_cents>0"}, 400)

        cur = get_top_bid(lk)
        state    = {"lane_key": lk, "incoming_cpm": cpm,
                    "current_top_cpm": cur["cpm_cents"] if cur else 0}
        decision = {"action": "place_bid", "new_cpm": cpm}
        agi_out  = agi_decide(state, decision)

        bid_rec = place_bid(lk, t["tenant_id"], cpm, cb)
        # update cache
        BIDS[lk] = bid_rec
        log(BIDS_LOG, "BID", "bid placed",
            lane=lk, cpm=cpm, buyer=t["tenant_id"],
            winner=(BIDS[lk]["buyer_id"] == t["tenant_id"]),
            agi=agi_out.get("agi", {}).get("ok"))
        return self.send_json(bid_rec, 200)

    def send_json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)


if __name__ == "__main__":
    FEEDBACK.mkdir(parents=True, exist_ok=True)
    print(f"[{now_iso()}] switchboard online :{PORT} agi={OLLAMA_URL}",
          flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
