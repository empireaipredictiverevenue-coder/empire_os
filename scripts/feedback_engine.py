#!/usr/bin/env python3
"""
Empire OS v3 — Agent Feedback Engine
Watches every agent's logs + outputs, builds a unified daily brief.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

FEEDBACK_ROOT = Path("/root/feedback")
FEEDBACK_ROOT.mkdir(parents=True, exist_ok=True)
FEEDBACK_LOG = FEEDBACK_ROOT / "feedback.log"
REGISTRY_PATH = Path("/root/empire_os/config/agent_registry.json")


def load_agents():
    """Load agents from registry — single source of truth."""
    if not REGISTRY_PATH.exists():
        return {}
    try:
        reg = json.loads(REGISTRY_PATH.read_text())
        return reg.get("agents", {})
    except Exception:
        return {}


def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).isoformat()
    line = "[%s] [%s] %s\n" % (ts, level, msg)
    FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
    with FEEDBACK_LOG.open("a") as f:
        f.write(line)
    print(line.strip())


def run_incus(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except Exception as e:
        return -2, str(e)


def check_agent_health(name, info):
    container = info.get("container", name)
    status = {"container": container, "role": info.get("role", "?"), "running": False, "healthy": False, "last_log_line": None}

    rc, out = run_incus(f"incus exec {container} -- echo alive", timeout=5)
    if rc == 0 and "alive" in out:
        status["running"] = True

    log_path = info.get("log_path")
    if log_path and status["running"]:
        rc, out = run_incus(f"incus exec {container} -- tail -n 1 {log_path} 2>/dev/null", timeout=5)
        if rc == 0 and out:
            status["last_log_line"] = out.strip()[:200]
            status["healthy"] = True

    url = info.get("health_url")
    if url and status["running"]:
        rc, out = run_incus(f"incus exec {container} -- curl -s --connect-timeout 3 {url} 2>/dev/null", timeout=5)
        if rc == 0 and ("online" in out.lower() or "{" in out):
            status["healthy"] = True
            status["health_response"] = out.strip()[:200]

    return status


def collect_agent_activity(name, info):
    container = info.get("container", name)
    log_path = info.get("log_path", "")
    activity = {"container": container, "role": info.get("role", "?"), "actions": [], "errors": [], "outputs_count": 0}

    if not log_path:
        return activity

    rc, out = run_incus(f"incus exec {container} -- wc -l < {log_path} 2>/dev/null", timeout=5)
    activity["outputs_count"] = int(out.strip()) if rc == 0 and out.strip().isdigit() else 0

    rc, out = run_incus(
        f"incus exec {container} -- grep -iE 'error|fail|exception|traceback' {log_path} 2>/dev/null | tail -n 10",
        timeout=5
    )
    if rc == 0 and out:
        for line in out.split("\n"):
            if line.strip():
                activity["errors"].append(line.strip()[:200])

    rc, out = run_incus(
        f"incus exec {container} -- grep -iE 'completed|finished|done|generated|published|deployed|audited|scored|tick|registered' {log_path} 2>/dev/null | tail -n 15",
        timeout=5
    )
    if rc == 0 and out:
        for line in out.split("\n"):
            if line.strip():
                activity["actions"].append(line.strip()[:200])

    return activity


def get_hub_metrics():
    metrics = {}
    rc, out = run_incus("incus exec empire-hub -- curl -s --connect-timeout 3 http://localhost:8081/health", timeout=5)
    metrics["hub_healthy"] = (rc == 0 and "online" in out.lower())

    rc, out = run_incus("incus exec empire-hub -- curl -s --connect-timeout 3 http://localhost:8081/v1/lanes", timeout=10)
    if rc == 0 and out:
        try:
            d = json.loads(out)
            metrics["lanes_total"] = d.get("total", 0)
        except Exception:
            pass

    rc, out = run_incus("incus exec empire-hub -- curl -s --connect-timeout 3 http://localhost:8081/v1/leads/counts", timeout=5)
    if rc == 0 and out:
        try:
            d = json.loads(out)
            metrics["leads_total"] = d.get("total", 0)
        except Exception:
            pass

    rc, out = run_incus("incus exec empire-hub -- curl -s --connect-timeout 3 http://localhost:8081/v1/funnel/counts", timeout=5)
    if rc == 0 and out:
        try:
            d = json.loads(out)
            metrics["funnel"] = d
        except Exception:
            pass

    return metrics


def collect_all():
    log("Starting feedback collection")
    agents = load_agents()
    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hub_metrics": {},
        "agents": {},
        "summary": {},
    }

    snapshot["hub_metrics"] = get_hub_metrics()

    for name, info in agents.items():
        try:
            health = check_agent_health(name, info)
            activity = collect_agent_activity(name, info)
            snapshot["agents"][name] = {
                "role": info.get("role", "?"),
                "health": health,
                "activity": activity,
            }
        except Exception as e:
            snapshot["agents"][name] = {"role": info.get("role", "?"), "error": str(e)}

    healthy = sum(1 for a in snapshot["agents"].values() if a.get("health", {}).get("healthy"))
    total = len(agents)
    errors = sum(len(a.get("activity", {}).get("errors", [])) for a in snapshot["agents"].values())
    actions = sum(len(a.get("activity", {}).get("actions", [])) for a in snapshot["agents"].values())

    snapshot["summary"] = {
        "agents_total": total,
        "agents_healthy": healthy,
        "agents_down": total - healthy,
        "total_actions_24h": actions,
        "total_errors_24h": errors,
    }
    log("Collection complete: %d/%d healthy, %d actions, %d errors" % (healthy, total, actions, errors))
    return snapshot


def save_brief(snapshot):
    """Save daily brief in JSON + Markdown."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    json_path = FEEDBACK_ROOT / ("daily_brief_%s.json" % today)
    json_path.write_text(json.dumps(snapshot, indent=2))

    md_lines = [
        "# Empire OS v3 — Daily Agent Brief",
        "",
        "**Date:** %s  " % today,
        "**Generated:** %s  " % snapshot["timestamp"],
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        "| Agents healthy | %d / %d |" % (snapshot["summary"]["agents_healthy"], snapshot["summary"]["agents_total"]),
        "| Agents down | %d |" % snapshot["summary"]["agents_down"],
        "| Actions (24h) | %d |" % snapshot["summary"]["total_actions_24h"],
        "| Errors (24h) | %d |" % snapshot["summary"]["total_errors_24h"],
        "| Lanes total | %s |" % snapshot["hub_metrics"].get("lanes_total", "?"),
        "| Leads total | %s |" % snapshot["hub_metrics"].get("leads_total", "?"),
        "| Hub healthy | %s |" % snapshot["hub_metrics"].get("hub_healthy", False),
        "",
        "## Agent Status",
        "",
    ]

    for name, info in snapshot["agents"].items():
        h = info.get("health", {})
        a = info.get("activity", {})
        md_lines.append("### %s (%s)" % (name, info.get("role", "?")))
        md_lines.append("")
        md_lines.append("- Running: %s" % h.get("running", False))
        md_lines.append("- Healthy: %s" % h.get("healthy", False))
        md_lines.append("- Log lines: %d" % a.get("outputs_count", 0))
        if h.get("last_log_line"):
            md_lines.append("- Last log: `%s`" % h["last_log_line"][:120])
        if a.get("actions"):
            md_lines.append("- Recent actions: %d" % len(a["actions"]))
        if a.get("errors"):
            md_lines.append("- Recent errors: %d" % len(a["errors"]))
            for err in a["errors"][:3]:
                md_lines.append("  - `%s`" % err[:150])
        md_lines.append("")

    md_path = FEEDBACK_ROOT / ("daily_brief_%s.md" % today)
    md_path.write_text("\n".join(md_lines))
    log("Brief saved: %s + %s" % (json_path.name, md_path.name))
    return md_path


def main():
    p = argparse.ArgumentParser(description="Empire OS v3 Agent Feedback Engine")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect", help="One-shot collection")
    w = sub.add_parser("watch", help="Continuous monitoring")
    w.add_argument("--interval", type=int, default=300, help="Seconds between collections")
    sub.add_parser("brief", help="Show latest brief")

    args = p.parse_args()

    if args.cmd == "collect":
        snap = collect_all()
        save_brief(snap)
    elif args.cmd == "watch":
        log("Watch mode: interval=%ds" % args.interval)
        while True:
            try:
                snap = collect_all()
                save_brief(snap)
            except KeyboardInterrupt:
                break
            except Exception as e:
                log("Watch error: %s" % e, "ERROR")
            import time as _t
            _t.sleep(args.interval)
    elif args.cmd == "brief":
        files = sorted(FEEDBACK_ROOT.glob("daily_brief_*.md"), reverse=True)
        if files:
            print(files[0].read_text())
        else:
            print("No briefs yet — run: feedback_engine.py collect")


if __name__ == "__main__":
    main()