"""
North-mini Agent — free-tier growth / ops / product engine.

Wired as pm2: empire-north-mini. Uses FREE OpenRouter model
cohere/north-mini-code:free (rate-limit safe via OpenRouterClient backoff).

Per founder directive: NOT a coding LLM. It is the strategy + execution
brain for business growth, management, and product design. Each cycle:
  1. read REAL live state (funnel/CRM/revenue/A2A) — no simulation
  2. produce plans: 90-day growth, product design specs, management/ops
     decisions, grounded in g-brain strategy + live data
  3. EXECUTE safe artifacts only (mode A): write specs / copy / pricing
     recs / OKF updates to g-brain + feedback, queue code stubs for the
     coder→reviewer pipeline. NEVER mutate live system, NEVER simulate.
  4. mirror outputs so Hermes can read on demand.

Hard per-cycle cap ~40s, few retries, never hang (free tier flaky).
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
from empire_os.agent_core import OpenRouterClient
from empire_os.agents.guardrails import scrub_secrets, safe_write

DB = os.environ.get("EMPIRE_DB", "/root/empire_os/empire_os.db")
FEED = Path("/root/feedback")
GBRAIN = Path("/root/g-brain")
OUT_PLAN = FEED / "north_mini_plans.jsonl"
OUT_LOG = FEED / "north_mini_actions.jsonl"
TICK = int(os.environ.get("NORTH_MINI_TICK", "1800"))  # 30 min
MODEL = os.environ.get("NORTH_MINI_MODEL", "tencent/hy3:free")
CYCLE_CAP = float(os.environ.get("NORTH_MINI_CAP", "40"))  # hard wall (s)

SYSTEM = (
    "You are North-mini, free co-founder assistant for Empire OS v3 — an "
    "open-source lead-gen + marketplace business. You own business GROWTH, "
    "MANAGEMENT/OPS, and PRODUCT DESIGN. Work ONLY from the real state JSON "
    "given. Never invent numbers. Output STRICT JSON, one of these shapes:\n"
    "{\"type\":\"growth_plan\",\"horizon_days\":90,\"thesis\":str,"
    "\"plays\":[{\"name\":str,\"why\":str,\"steps\":[str],\"kpi\":str}],"
    "\"next_3\":[str,str,str]}\n"
    "{\"type\":\"product_design\",\"product\":str,\"problem\":str,"
    "\"users\":str,\"features\":[str],\"spec_path\":str,\"mvp_steps\":[str]}\n"
    "{\"type\":\"management\",\"decision\":str,\"rationale\":str,"
    "\"owner\":str,\"deadline\":str}\n"
    "{\"type\":\"agi_intel\",\"signal\":str,\"source\":str,"
    "\"gap\":str,\"opp_for_empire\":str,\"next_actions\":[str,str,str]}\n"
    "{\"type\":\"projection\",\"projected_mrr_usd\":int,\"confidence_0_1\":float,"
    "\"top_leak\":str,\"next_actions\":[str,str,str]}\n"
    "Keep each field tight. No markdown in values."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_state() -> dict:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    s = {}
    try:
        q = {
            "leads": "SELECT COUNT(*) c FROM si_ppl_leads",
            "leads_new": "SELECT COUNT(*) c FROM si_ppl_leads WHERE status='new'",
            "charges_sim": "SELECT COUNT(*) c FROM si_charges WHERE status='simulated'",
            "charges_open": "SELECT COUNT(*) c FROM si_charges WHERE status='open'",
            "charges_paid": "SELECT COUNT(*) c FROM si_charges WHERE status='succeeded'",
            "charges_total": "SELECT COUNT(*) c FROM si_charges",
            "tenants": "SELECT COUNT(*) c FROM si_tenant",
            "subs": "SELECT COUNT(*) c FROM si_tenant WHERE status='subscribed'",
            "seats": "SELECT COUNT(*) c FROM si_seat",
            "ppc_inv_open": "SELECT COUNT(*) c FROM si_ppc_invoices WHERE status='open'",
            "ppc_inv_paid": "SELECT COUNT(*) c FROM si_ppc_invoices WHERE status='paid'",
            "settlements": "SELECT COUNT(*) c FROM si_settlements",
            "funnel_events": "SELECT COUNT(*) c FROM si_funnel_event",
        }
        for k, sql in q.items():
            row = con.execute(sql).fetchone()
            s[k] = dict(row).get("c", 0) if row else 0
        s["leads_by_status"] = {
            r["status"]: r["c"]
            for r in con.execute(
                "SELECT status, COUNT(*) c FROM si_ppl_leads GROUP BY status").fetchall()
        }
        # g-brain strategy snapshot (what founder already saved)
        gpath = GBRAIN / "revenue" / "pricing.md"
        if gpath.exists():
            s["strategy_note"] = "pricing.md present (12 SKU tiers)"
    except Exception as e:
        s["_read_error"] = str(e)[:200]
    finally:
        con.close()
    return s


def _last(kind: str) -> dict:
    if not OUT_PLAN.exists():
        return {}
    try:
        for ln in reversed(OUT_PLAN.read_text().splitlines()):
            if ln.strip():
                d = json.loads(ln)
                if d.get("doc", {}).get("type") == kind:
                    return d
    except Exception:
        pass
    return {}


def _last30days_signals() -> str:
    """Read latest last30days artifacts for real public signal.

    Returns a compact text block for the agi_intel prompt, or '' if none
    yet. Reads only /root/feedback/last30days_<topic>.jsonl (per-topic
    files), skipping the _runs aggregate.
    """
    signals = []
    try:
        for p in FEED.glob("last30days_*.jsonl"):
            if p.name == "last30days_runs.jsonl":
                continue
            for ln in reversed(p.read_text().splitlines()):
                if ln.strip():
                    d = json.loads(ln)
                    signals.append(f"- {d.get('topic','?')}: {d.get('takeaway','')}")
                    break  # latest per file only
    except Exception:
        pass
    if not signals:
        return ""
    return ("REAL last30days public signals (last 30d, keyless sources):\n"
            + "\n".join(signals) + "\n")


def _write(kind: str, doc: dict, state: dict) -> None:
    # GUARDRAIL: artifact mode — only /root/feedback + /root/g-brain, with
    # secret scrubbing. safe_write() enforces the path allow-list.
    record = {"ts": _now(), "model": MODEL, "type": kind, "doc": doc,
              "state_sig": {k: state.get(k) for k in
                            ("leads", "charges_sim", "subs", "seats")}}
    ok = safe_write(OUT_PLAN, json.dumps(record) + "\n", "artifact",
                   "north-mini")
    # mirror human-readable into g-brain
    try:
        tgt = {
            "growth_plan": GBRAIN / "build" / "growth_plan_northmini.md",
            "product_design": GBRAIN / "build" / "product_design_northmini.md",
            "management": GBRAIN / "build" / "management_northmini.md",
            "agi_intel": GBRAIN / "research" / "agi_intel_northmini.md",
            "projection": GBRAIN / "revenue" / "projections.md",
        }.get(kind)
        if tgt:
            safe_write(tgt, f"\n## {record['ts']}\n{json.dumps(doc, indent=2)}\n",
                       "artifact", "north-mini")
    except Exception:
        pass


def _log_action(action: str, detail: str) -> None:
    safe_write(OUT_LOG, json.dumps({"ts": _now(), "action": action,
                                    "detail": scrub_secrets(detail)}) + "\n",
               "artifact", "north-mini")


def _prompt(kind: str, state: dict) -> str:
    prev = _last(kind).get("doc", {})
    base = (f"REAL state (no simulation): {json.dumps(state)}\n"
            f"Previous {kind}: {json.dumps(prev)}\n")
    if kind == "growth_plan":
        return base + ("Produce a 90-day growth plan to close the revenue loop "
                      "(known leak: charges sit 'simulated' — pay_url never "
                      "delivered to buyers; 0 subscribers; 10 simulated charges). "
                      "Output growth_plan JSON.")
    if kind == "product_design":
        return base + ("Design ONE product to build next from the 12-SKU pricing "
                      "tiers in g-brain/revenue/pricing.md. Output product_design "
                      "JSON with spec_path like 'g-brain/build/specs/<name>.md'.")
    if kind == "management":
        return base + ("Make ONE management/ops decision to unblock revenue. "
                      "Output management JSON.")
    if kind == "agi_intel":
        sig = _last30days_signals()
        sig_block = sig if sig else "(no last30days signal captured yet — run empire-last30days first)\n"
        return base + (f"Act as AGI market-intel scout. From REAL public signals "
                       f"below (not guesses) identify ONE market gap + how Empire OS "
                       f"exploits it. Output agi_intel JSON.\n{sig_block}")
    return base + "Produce a revenue projection. Output projection JSON."


def run_cycle(client: OpenRouterClient) -> dict:
    t0 = time.time()
    state = read_state()
    # rotate through plan types so each cycle covers a facet
    cycle_no = int((time.time() // TICK) % 5)
    kinds = ["growth_plan", "product_design", "management",
              "agi_intel", "projection"]
    kind = kinds[cycle_no]
    raw = client.chat([{"role": "user", "content": _prompt(kind, state)}],
                      system=SYSTEM, temperature=0.3, max_tokens=1100)
    if raw is None:
        raw = json.dumps({"error": "empty_response"})
    try:
        doc = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        doc = {"error": "parse_failed", "raw": raw[:300]}
    if "error" in doc:
        return {"ts": _now(), "kind": kind, "skipped": True, "err": doc["error"]}
    _write(kind, doc, state)
    # MODE A execution: queue a code stub for coder→reviewer if product design
    if kind == "product_design" and doc.get("spec_path"):
        spec = GBRAIN / "build" / "specs" / Path(doc["spec_path"]).name
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(
            f"# {doc.get('product','?')}\n\nProblem: {doc.get('problem','')}\n"
            f"Users: {doc.get('users','')}\nFeatures:\n"
            + "\n".join(f"- {x}" for x in doc.get("features", []))
            + f"\n\nMVP steps:\n"
            + "\n".join(f"{i+1}. {s}" for i, s in enumerate(doc.get("mvp_steps", [])))
            + "\n\n(generated by North-mini, queued for coder→reviewer)\n")
        _log_action("queued_product_spec", str(spec))
    else:
        _log_action("wrote_plan", kind)
    return {"ts": _now(), "kind": kind, "doc": doc,
            "elapsed": round(time.time() - t0, 1)}


def main():
    client = OpenRouterClient(model=MODEL)
    if not client.api_key:
        print(json.dumps({"error": "no_openrouter_key",
                          "hint": "/root/.empire_secrets/openrouter.env"}),
              flush=True)
        sys.exit(2)
    if "--once" in sys.argv:
        rec = run_cycle(client)
        print(json.dumps(rec, indent=2, default=str)[:2000])
        sys.exit(0)
    print(f"[north-mini] loop start model={MODEL} tick={TICK}s cap={CYCLE_CAP}s",
          flush=True)
    while True:
        try:
            # hard wall: never let one flaky free-tier call hang the loop
            import threading
            res = [None]
            def _go():
                res[0] = run_cycle(client)
            th = threading.Thread(target=_go, daemon=True)
            th.start()
            th.join(CYCLE_CAP)
            if th.is_alive():
                print("[north-mini] cycle hit cap, skipping", flush=True)
            else:
                r = res[0] or {}
                if r.get("skipped"):
                    print(f"[north-mini] {r.get('kind')} skipped ({r.get('err')})",
                          flush=True)
                else:
                    print(f"[north-mini] {r.get('kind')} ok "
                          f"({r.get('elapsed','?')}s)", flush=True)
        except Exception as e:
            print(f"[north-mini] cycle crashed: {e!r}", flush=True)
        time.sleep(TICK)


if __name__ == "__main__":
    main()
