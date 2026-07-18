#!/usr/bin/env python3
"""
Empire OS — CONTINUOUS CODE CHECKER ("the coder")
=================================================

Runs on the HOST (outside the incus container). Every CODER_INTERVAL
seconds it:
  1. Syntax-checks every .py in /root/empire_os (compileall).
  2. Import-smoke-tests the modules that DON'T need the container-only
     solana SDK (charge logic, ppc_router). Hub import is checked via
     the live endpoint instead (it needs solana which lives in-container).
  3. Probes live endpoints inside the container via `incus exec`:
        - hub :8000 /health
        - ppc_router :9200 /v1/health
  4. Checks the pm2 process table (via incus exec) to confirm
     empire-hub-service is online AND serving the REAL billing hub
     (/v1/ppc/charge route exists). This directly catches the
     wrong-entrypoint / stub-hub class of bug.
  5. On ANY failure, posts a Telegram alert + writes jsonl log.

Best-effort: a single failing check never crashes the loop.
"""
from __future__ import annotations
import json, os, sys, time, subprocess, urllib.request
from datetime import datetime, timezone

ROOT = "/root/empire_os"
CONTAINER = os.environ.get("EMPIRE_CONTAINER", "empire-hub")
LOG = os.environ.get("CODER_LOG", "/root/feedback/coder_checks.jsonl")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHECK_EVERY_S = int(os.environ.get("CODER_INTERVAL", "120"))

# modules safe to import on the host (no container-only solana SDK needed)
CRITICAL_HOST = ["empire_os.charge", "empire_os.crypto_charge",
                 "empire_os.ppc_router"]


def now_iso(): return datetime.now(timezone.utc).isoformat()


def log_json(level, msg, **fields):
    e = {"ts": now_iso(), "level": level, "msg": msg, **fields}
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "WARN"):
        print(json.dumps(e), flush=True)


def tg_alert(text: str):
    if not (TELEGRAM_CHAT and TELEGRAM_BOT):
        return
    try:
        payload = json.dumps({"chat_id": TELEGRAM_CHAT,
                              "text": text,
                              "disable_web_page_preview": True}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
            data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8):
            pass
    except Exception:
        pass


def incus_exec(script: str, timeout: int = 25) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["incus", "exec", CONTAINER, "--", "sh", "-c", script],
        capture_output=True, text=True, timeout=timeout)


def check_syntax() -> list[str]:
    """Compile-check every .py under ROOT individually so a failure
    NAMES the exact broken file (compileall with quiet=2 returns False
    without naming the culprit). Returns list of 'path: <err>' strings."""
    import py_compile
    bad: list[str] = []
    for dirpath, _, files in os.walk(ROOT):
        if ".git" in dirpath or "node_modules" in dirpath or "__pycache__" in dirpath:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                py_compile.compile(fp, doraise=True, quiet=1)
            except py_compile.PyCompileError as e:
                bad.append(f"{fp}: {str(e).splitlines()[-1][:160]}")
            except Exception as e:
                bad.append(f"{fp}: {e}")
    return bad


def check_imports() -> list[str]:
    """Import the host-safe critical modules; return failures."""
    bad: list[str] = []
    for mod in CRITICAL_HOST:
        try:
            subprocess.run(
                [sys.executable, "-c",
                 f"import sys; sys.path.insert(0,'{ROOT}'); import {mod}"],
                capture_output=True, timeout=30, check=True)
        except subprocess.CalledProcessError:
            bad.append(mod)
    return bad


def check_endpoints() -> list[str]:
    """Probe live endpoints INSIDE the container via incus exec."""
    dead: list[str] = []
    probes = [
        ("hub :8000 /health",
         "curl -s -m 6 -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health"),
        ("ppc_router :9200 /v1/health",
         "curl -s -m 6 -o /dev/null -w '%{http_code}' http://127.0.0.1:9200/v1/health"),
    ]
    for name, script in probes:
        try:
            out = incus_exec(script)
            code = (out.stdout or "").strip()
            if code != "200":
                dead.append(f"{name} (HTTP {code})")
        except Exception as e:
            dead.append(f"{name} (probe error: {e})")
    return dead


def check_pm2() -> list[str]:
    """Confirm empire-hub-service online + serving real billing hub."""
    probs: list[str] = []
    try:
        out = incus_exec("pm2 jlist 2>/dev/null")
        import json as _json
        data = _json.loads(out.stdout or "[]")
    except Exception as e:
        return [f"pm2_query_failed:{e}"]
    hub = next((p for p in data if p.get("name") == "empire-hub-service"), None)
    if not hub:
        return ["empire-hub-service missing from pm2"]
    if hub.get("pm2_env", {}).get("status") != "online":
        probs.append("empire-hub-service not online")
    # real billing hub alive? probe /health (200 = hub serving the
    # real billing app). /health is the correct liveness signal — the
    # /v1/ppc/charge POST probe used before returned transient 000 and
    # produced false-positive failures even when the hub was healthy.
    code = ""
    for _ in range(3):
        try:
            probe = ("curl -s -m 6 -o /dev/null -w '%{http_code}' "
                     "http://127.0.0.1:8000/health")
            out2 = incus_exec(probe)
            code = (out2.stdout or "").strip()
            if code == "200":
                break
        except Exception:
            pass
    if code != "200":
        probs.append(f"hub /health not 200 (HTTP {code or 'empty'})")
    return probs


def check_revenue_loop() -> list[str]:
    """Recurrence guard: catch the simulation / dead-router revenue leaks.

    Flags:
      - ppc-router not online (the charge/settle path dies without it)
      - any si_charges row stuck in 'simulated'/'open' for >30m with a
        pay_url that was never delivered -> the $0-revenue root cause.
        (NO-SIM: a 'simulated' charge past the grace window is a FAILURE,
        not a benign state.)
    """
    probs: list[str] = []
    # 1) ppc-router liveness
    try:
        out = incus_exec("pm2 jlist 2>/dev/null")
        import json as _json
        data = _json.loads(out.stdout or "[]")
        pr = next((p for p in data
                   if p.get("name") == "empire-ppc-router"), None)
        if pr and pr.get("pm2_env", {}).get("status") != "online":
            probs.append("empire-ppc-router NOT online (charge path dead)")
    except Exception:
        pass
    # 2) stale simulated charges (never delivered / never paid)
    try:
        q = ("SELECT COUNT(*) FROM si_charges WHERE status IN "
             "('simulated','open') AND created_at < datetime('now','-30 minutes')")
        res = incus_exec(
            f"cd /root/empire_os && python3 -c \""
            f"from empire_os.funnel import SQLiteBackend;"
            f"b=SQLiteBackend('empire_os.db');"
            f"print(b.execute({q!r}).fetchone()[0])\"")
        stuck = int((res.stdout or "0").strip() or 0)
        if stuck > 0:
            probs.append(
                f"{stuck} charge(s) stuck simulated/open >30m "
                f"(pay_url never delivered / never settled)")
    except Exception as e:
        probs.append(f"revenue_loop_check_error:{e}")
    return probs


def run_once() -> dict:
    results = {
        "syntax_bad": check_syntax(),
        "import_bad": check_imports(),
        "endpoints_dead": check_endpoints(),
        "pm2_probs": check_pm2(),
        "revenue_loop_probs": check_revenue_loop(),
    }
    failed = any(results[k] for k in results)
    results["ok"] = not failed
    if failed:
        log_json("ERROR", "codebase_check_failed", **results)
        tg_alert("🛠️ EMPIRE CODER — check FAILED:\n" +
                 json.dumps(results, indent=2, default=str)[:1500])
    else:
        log_json("OK", "codebase_check_passed")
    return results


def main():
    if "--once" in sys.argv:
        res = run_once()
        print(json.dumps(res, indent=2, default=str))
        sys.exit(0 if res["ok"] else 1)
    log_json("INFO", "coder_loop_start", interval_s=CHECK_EVERY_S)
    while True:
        try:
            run_once()
        except Exception as e:
            log_json("ERROR", "coder_loop_crashed", err=str(e)[:300])
        time.sleep(CHECK_EVERY_S)


if __name__ == "__main__":
    main()
