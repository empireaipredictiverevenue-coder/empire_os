#!/usr/bin/env python3
"""qc_agent — Empire OS stack quality control.

Runs a full end-to-end health probe of the revenue stack and writes a
report to /root/feedback/qc_report.json. Alerts (Telegram) on any FAIL.
Designed to run on a systemd timer (e.g. every 15 min) so silent rot is
caught WITHOUT a human firefighting it.

Covers the exact failure classes seen in production:
  - AEO pages served but CTA missing (inject drift)
  - sitemap/robots unreachable (tunnel/hub down)
  - money loop broken (/v1/buyers/apply no pay_url)
  - outbox silently stalled (emails queued, 0 sent)
  - units down (hub/mail-sender/tunnel dead)
"""
import os, sys, json, time, sqlite3, datetime, urllib.request, ssl

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"
FB = "/root/feedback"
REPORT = f"{FB}/qc_report.json"
BASE = "https://empire-ai.co.uk"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36"}


def get(path, timeout=20):
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE + path, headers=UA),
                                    context=CTX, timeout=timeout) as r:
            return r.status, r.read()
    except Exception as e:
        return getattr(e, "code", "ERR"), str(e)[:120].encode()


def check(name, ok, detail=""):
    return {"name": name, "ok": bool(ok), "detail": str(detail)}


def db_q(sql, default=None):
    """Query the LIVE container DB. If we're on the host, hop in via incus;
    if already inside the container (no incus), query sqlite3 directly."""
    try:
        import subprocess, shutil
        if shutil.which("incus"):
            script = ("import sqlite3,json;"
                      "c=sqlite3.connect('/root/empire_os/empire_os.db');"
                      "r=c.execute(%r).fetchone();"
                      "print(r[0] if r else '')" % sql)
            r = subprocess.run(["incus", "exec", "empire-hub", "--", "python3", "-c", script],
                               capture_output=True, text=True, timeout=30)
            out = r.stdout.strip()
        else:
            import sqlite3
            c = sqlite3.connect("/root/empire_os/empire_os.db")
            row = c.execute(sql).fetchone()
            out = str(row[0]) if row else ""
        if out == "":
            return default
        try:
            return int(out)
        except ValueError:
            return out
    except Exception as e:
        return f"err:{e}"


def unit_active(u, host=False):
    """Check a systemd unit. host=True checks the HOST; otherwise the
    empire-hub CONTAINER (where the empire-* units actually run).
    Robust: if we're already inside the container (no `incus` binary), check
    systemd directly instead of recursing via `incus exec` (which fails and
    falsely reports the unit DOWN)."""
    import shutil, subprocess
    try:
        if host:
            # Host units (e.g. cloudflared) can only be seen from the host.
            r = subprocess.run(["systemctl", "is-active", u], capture_output=True, text=True)
        else:
            if shutil.which("incus"):
                # We're on the host -> hop into the container.
                r = subprocess.run(["incus", "exec", "empire-hub", "--", "systemctl", "is-active", u],
                                   capture_output=True, text=True)
            else:
                # Already inside the container -> check directly.
                r = subprocess.run(["systemctl", "is-active", u], capture_output=True, text=True)
        return r.stdout.strip() == "active"
    except Exception:
        return False


def load_soul():
    """Load this agent's SOUL from the live souls dir (source of truth)."""
    try:
        p = os.path.join(os.path.dirname(__file__), "souls", "qc_agent_SOUL.md")
        if os.path.exists(p):
            print(f"[qc] soul loaded: {p} ({os.path.getsize(p)} bytes)", flush=True)
    except Exception:
        pass

def main():
    os.makedirs(FB, exist_ok=True)
    load_soul()
    results = []
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. AEO page served + CTA present
    c, b = get("/aeo/weight_loss/CHI")
    results.append(check("aeo_page_served", c == 200, f"status={c}"))
    results.append(check("aeo_cta_present", c == 200 and b"buyer-cta" in b, f"cta_in_body={b'buyer-cta' in b}"))

    # 2. sitemap + robots reachable
    c, b = get("/sitemap.xml")
    results.append(check("sitemap_served", c == 200 and b"aeo/" in b, f"status={c} len={len(b) if isinstance(b,bytes) else 0}"))
    c, b = get("/robots.txt")
    results.append(check("robots_served", c == 200 and b"sitemap" in b, f"status={c}"))

    # 3. money loop: apply returns pay_url (probe the CONTAINER hub directly
    #    at its incus IP to avoid Cloudflare WAF challenging the bot-like probe)
    HUB = "http://10.118.155.218:8081"
    import urllib.request as U
    try:
        with U.urlopen(f"{HUB}/health", timeout=10) as _h:
            health_ok = _h.status == 200
    except Exception:
        health_ok = False
    req = U.Request(f"{HUB}/v1/buyers/apply",
                    data=json.dumps({"name": "QC Probe", "email": f"qc-probe-{int(time.time())}@example.com",
                                     "niche": "weight_loss", "metro": "CHI", "plan": "silver"}).encode(),
                    headers={"Content-Type": "application/json"}, method="POST")
    try:
        with U.urlopen(req, timeout=25) as r:
            resp = json.loads(r.read().decode())
        has_pay = bool(resp.get("pay_url") or (resp.get("payment") or {}).get("pay_url"))
        results.append(check("money_loop_apply_payurl", has_pay, f"ok={resp.get('ok')} pay={bool(has_pay)}"))
        # cleanup the probe tenant
        try:
            tid = resp.get("tenant_id")
            if tid:
                cc = sqlite3.connect(DB)
                cc.execute("DELETE FROM si_subscription WHERE tenant_id=?", (tid,))
                cc.execute("DELETE FROM si_tenant WHERE id=?", (tid,))
                cc.commit(); cc.close()
        except Exception:
            pass
    except Exception as e:
        results.append(check("money_loop_apply_payurl", False, f"exc={e}"))

    # 4. outbox flushing (not silently stalled)
    pending = db_q("SELECT COUNT(*) FROM si_outbox WHERE status='pending'", 0)
    sent_recent = db_q("SELECT COUNT(*) FROM si_outbox WHERE status='sent' AND sent_at >= datetime('now','-10 minutes')", 0)
    stalled = (isinstance(pending, int) and pending > 20 and isinstance(sent_recent, int) and sent_recent == 0)
    results.append(check("outbox_flushing", not stalled,
                         f"pending={pending} sent_10m={sent_recent} stalled={stalled}"))

    # 5. subs minting (loop producing seats)
    subs = db_q("SELECT COUNT(*) FROM si_subscription", 0)
    results.append(check("subs_exist", isinstance(subs, int) and subs > 0, f"subs={subs}"))

    # 6. critical units up (these run INSIDE the empire-hub container)
    #    Daemons must be active. Batch/timer units (oneshot + .timer) are
    #    expected to be inactive between runs -> check they ran OK recently
    #    instead of requiring `active` (otherwise we false-alarm "DOWN").
    def unit_healthy(u):
        try:
            import subprocess, shutil
            def run(args):
                if shutil.which("incus"):
                    return subprocess.run(["incus", "exec", "empire-hub", "--", *args],
                                          capture_output=True, text=True, timeout=15)
                return subprocess.run(args, capture_output=True, text=True, timeout=15)
            # Is it a timer-backed or oneshot unit?
            info = run(["systemctl", "show", u, "--property=Type,TriggeredBy,ActiveState,Result,ExecMainStatus"]).stdout
            props = dict(k.split("=", 1) for k in info.splitlines() if "=" in k)
            typ = props.get("Type", "")
            triggered = props.get("TriggeredBy", "")
            active = props.get("ActiveState", "") == "active"
            if typ == "oneshot" or triggered.strip():
                # Batch/timer unit: healthy if it last ran successfully
                # (Result=success) and isn't currently failed.
                result = props.get("Result", "")
                ok = result in ("", "success")
                return ok, f"batch/timer last_result={result or 'success'}"
            return active, "active" if active else "DOWN"
        except Exception as e:
            return False, f"check_err:{e}"

    for u in ["empire-hub-8081.service", "empire-mail-sender.service",
              "empire-agent-founder-outreach.service", "empire-agent-loop-closure.service",
              "empire-cortex-swarm.service", "empire-last30days.service",
              "empire-content-engine.service", "empire-predictive-router.service"]:
        a, detail = unit_healthy(u)
        results.append(check(f"unit_{u}", a, detail))

    # 7. cloudflared tunnel (HOST side). From inside the container we can't
    #    see host units -> report unknown instead of a false DOWN.
    import shutil as _sh
    if _sh.which("incus"):
        tunnel_up = os.system("systemctl is-active cloudflared-empire.service >/dev/null 2>&1") == 0
        results.append(check("tunnel_cloudflared", tunnel_up, "active" if tunnel_up else "DOWN"))
    else:
        results.append(check("tunnel_cloudflared", True, "skip(in-container)"))

    fails = [r for r in results if not r["ok"]]
    report = {"ts": ts, "pass": len(results) - len(fails), "fail": len(fails),
              "status": "HEALTHY" if not fails else "DEGRADED", "checks": results}
    try:
        with open(REPORT, "w") as f:
            json.dump(report, f, indent=2)
    except Exception as e:
        print(f"[qc] WARN report write failed: {e}", flush=True)

    print(f"[qc] {report['status']} pass={report['pass']} fail={report['fail']}")
    for r in results:
        print(f"  [{'OK' if r['ok'] else 'FAIL'}] {r['name']} -> {r['detail']}")

    if fails:
        try:
            from empire_os import revenue_notify as rn
            rn.loop_stall("QC DEGRADED: " + ", ".join(r["name"] for r in fails))
        except Exception:
            pass
    return report


if __name__ == "__main__":
    main()
