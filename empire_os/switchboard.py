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
DEFAULT_FRM = os.environ.get("DEFAULT_FROM", "+18885550100")
OLLAMA_URL  = os.environ.get("OLLAMA_URL", "http://10.218.156.211:11434")
LLM_MODEL   = os.environ.get("LLM_MODEL", "qwen2.5:7b")
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "180"))

ACTIVE     = {}      # call_id -> dict
BIDS       = {}      # lane_key -> highest bid
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
            return self.send_json({"active": list(ACTIVE.values())}, 200)
        if self.path.startswith("/v1/bids/top"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            lk = q.get("lane_key", [None])[0]
            return self.send_json({"lane_key": lk, "top": BIDS.get(lk)}, 200)
        if self.path.startswith("/v1/agi/last"):
            n = int(self.path.split("n=")[-1]) if "n=" in self.path else 10
            return self.send_json({"decisions": list(DEC_HIST)[:n]}, 200)
        if self.path.startswith("/v1/health"):
            return self.send_json({"ok": True, "calls": len(ACTIVE),
                                   "bids": len(BIDS), "ts": now_iso()}, 200)
        return self.send_json({"error": "not found"}, 404)

    def log_message(self, *a, **k): pass

    # ── routes ──
    def place(self, body):
        to       = body.get("to", "")
        frm      = body.get("from", DEFAULT_FRM)
        lane_key = body.get("lane_key", "")
        lead_id  = body.get("lead_id", "")
        if not to or not lane_key:
            return self.send_json({"error": "to + lane_key required"}, 400)

        state    = {"to": to, "from": frm, "lane_key": lane_key,
                    "lead_id": lead_id, "bids_in_lane": len(
                        [b for k, b in BIDS.items() if k == lane_key]),
                    "active_calls": len(ACTIVE)}
        decision = {"action": "place_call",
                    "winner_bid": BIDS.get(lane_key)}
        agi_out  = agi_decide(state, decision)

        call_id = "call_" + secrets.token_hex(8)
        rec = {"call_id": call_id, "to": to, "from": frm,
               "lane_key": lane_key, "lead_id": lead_id,
               "status": "ringing", "placed_at": now_iso(),
               "winner_bid": BIDS.get(lane_key),
               "agi_decision_id": agi_out.get("ts")}
        ACTIVE[call_id] = rec
        log(CALLS_LOG, "PLACE", "call placed",
            call_id=call_id, to=to, lane=lane_key,
            agi=agi_out.get("agi", {}).get("ok"))
        return self.send_json(rec, 200)

    def hangup(self, body):
        cid = body.get("call_id", "")
        reason = body.get("reason", "completed")
        if cid not in ACTIVE:
            return self.send_json({"error": "unknown call_id"}, 404)
        ACTIVE[cid]["status"]    = reason
        ACTIVE[cid]["ended_at"]  = now_iso()
        if ACTIVE[cid].get("winner_bid"):
            cost_cents = (ACTIVE[cid].get("duration_s", 30) / 60.0
                          * ACTIVE[cid]["winner_bid"]["cpm_cents"])
            ACTIVE[cid]["settled_cents"] = int(cost_cents)
        log(CALLS_LOG, "HANGUP", "call ended",
            call_id=cid, reason=reason,
            settled=ACTIVE[cid].get("settled_cents"))
        return self.send_json(ACTIVE[cid], 200)

    def record(self, body):
        cid = body.get("call_id", "")
        if cid not in ACTIVE:
            return self.send_json({"error": "unknown call_id"}, 404)
        ACTIVE[cid]["rec_url"]    = body.get("rec_url", "")
        ACTIVE[cid]["duration_s"] = body.get("duration_s", 0)
        log(CALLS_LOG, "RECORD", "call recorded",
            call_id=cid, dur=body.get("duration_s"),
            rec=body.get("rec_url"))
        return self.send_json({"ok": True}, 200)

    def bid(self, body):
        lk    = body.get("lane_key", "")
        cpm   = int(body.get("cpm_cents", "0"))
        cb    = body.get("callback_url", "")
        if not lk or cpm <= 0:
            return self.send_json({"error": "lane_key + cpm_cents>0"}, 400)

        cur = BIDS.get(lk)
        state    = {"lane_key": lk, "incoming_cpm": cpm,
                    "current_top_cpm": cur["cpm_cents"] if cur else 0}
        decision = {"action": "place_bid", "new_cpm": cpm}
        agi_out  = agi_decide(state, decision)

        bid = {"lane_key": lk, "cpm_cents": cpm, "callback_url": cb,
               "bid_id": "bid_" + secrets.token_hex(6), "set_at": now_iso(),
               "replaces": cur["bid_id"] if cur else None}
        if not cur or cpm > cur["cpm_cents"]:
            BIDS[lk] = bid
        log(BIDS_LOG, "BID", "bid placed",
            lane=lk, cpm=cpm,
            winner=(BIDS[lk]["bid_id"] == bid["bid_id"]),
            agi=agi_out.get("agi", {}).get("ok"))
        return self.send_json(bid, 200)

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
