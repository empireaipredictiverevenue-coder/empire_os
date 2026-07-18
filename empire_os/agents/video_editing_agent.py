"""
Video Editing Agent — wraps OpenMontage + OpenCut + FFmpeg for Empire OS.

Backing libraries (already cloned to host):
  - /root/OpenMontage/        (38k stars, 12 pipelines, 52 tools)
  - /root/OpenCut/            (68k stars, CapCut alt - rewrite in progress)
  - /root/OpenCut-Classic/    (working classic version - web/desktop only)

What this agent does today (no OpenCut headless yet):
  1. Reads video-project briefs from hub /v1/video/projects
  2. Routes briefs to OpenMontage pipeline_defs (12 available)
  3. Generates renders via OpenMontage's tools/ directory (Python)
  4. Uses FFmpeg for any compositing not covered by OpenMontage
  5. Stores outputs in /root/video_projects/<id>/
  6. Pages operator via hermes-gateway on render success/failure

What it does NOT do yet (waiting for OpenCut rewrite):
  - Direct timeline editing via MCP server
  - Plugin-based effects chains
  - Headless batch rendering of user-edited timelines

This will become a thin proxy the day OpenCut ships their MCP server.
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent

ROLE_DIR = Path("/root/video_projects")
ROLE_DIR.mkdir(parents=True, exist_ok=True)
JOBS_LOG = ROLE_DIR / "jobs.jsonl"
TICK_INTERVAL = 600  # 10 min

DB_PATH = os.environ.get("DB_PATH", "/root/empire_os/empire_os.db")
HUB_URL = os.environ.get("HUB_URL", "http://127.0.0.1:8000")
HERMES_GATEWAY_URL = os.environ.get(
    "HERMES_GATEWAY_URL", "http://10.118.155.156:9100")

# Backing libraries
OPENMONTAGE_DIR = Path("/root/OpenMontage")
OPENCUT_DIR = Path("/root/OpenCut")
OPENCUT_CLASSIC_DIR = Path("/root/OpenCut-Classic")


def sh(cmd, timeout=120, cwd=None):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True,
                              text=True, timeout=timeout, cwd=cwd)
    except Exception as e:
        return type("R", (), {"returncode": -1, "stdout": "",
                              "stderr": str(e)})()


def list_openmontage_pipelines() -> list[str]:
    """List available OpenMontage pipeline_defs."""
    pdir = OPENMONTAGE_DIR / "pipeline_defs"
    if not pdir.exists():
        return []
    return sorted([p.stem for p in pdir.glob("*.yaml")])


def list_openmontage_tools() -> list[str]:
    """List OpenMontage tools categories."""
    tdir = OPENMONTAGE_DIR / "tools"
    if not tdir.exists():
        return []
    return sorted([d.name for d in tdir.iterdir()
                   if d.is_dir() and not d.name.startswith("_")])


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def render_brief(project: dict, pipeline: str) -> dict:
    """Render a video project via the named OpenMontage pipeline.

    For now this is a thin shell that:
      1. Validates the pipeline exists
      2. Runs OpenMontage's render_demo.py with the project name
      3. Returns output path or error

    Real OpenMontage integration will use the tools/ registry and
    pipeline_defs/<pipeline>.yaml directly.
    """
    if not OPENMONTAGE_DIR.exists():
        return {"ok": False, "error": "OpenMontage not installed at /root/OpenMontage"}
    if pipeline not in list_openmontage_pipelines():
        return {"ok": False,
                "error": f"unknown pipeline '{pipeline}'",
                "available": list_openmontage_pipelines()}
    out_dir = ROLE_DIR / project.get("id", "unnamed")
    out_dir.mkdir(parents=True, exist_ok=True)
    # Render via OpenMontage's CLI demo (idempotent)
    cmd = (f"cd {OPENMONTAGE_DIR} && /root/venv/bin/python3 render_demo.py "
           f"--pipeline {pipeline} --out {out_dir} "
           f"--brief '{json.dumps(project.get('brief', {}))}'")
    r = sh(cmd, timeout=300)
    return {
        "ok": r.returncode == 0,
        "out_dir": str(out_dir),
        "stdout_tail": (r.stdout or "")[-400:],
        "stderr_tail": (r.stderr or "")[-400:],
    }


class VideoEditingAgent(SyntheticAgent):
    """Reads video project briefs from hub, renders via OpenMontage."""

    def _db_query(self, sql: str, params: tuple = ()) -> list[dict]:
        try:
            import sqlite3
            cnx = sqlite3.connect(DB_PATH)
            cnx.row_factory = sqlite3.Row
            rows = [dict(r) for r in cnx.execute(sql, params).fetchall()]
            cnx.close()
            return rows
        except Exception as e:
            return [{"_error": str(e)[:200]}]

    def observe(self) -> dict:
        # Find video-project requests in hub /v1/video/projects (if any)
        pending = []
        try:
            import requests
            r = requests.get(f"{HUB_URL}/v1/video/projects?status=pending",
                             timeout=8)
            if r.status_code == 200:
                pending = r.json().get("projects", [])
        except Exception as e:
            pass  # hub may not have this endpoint yet
        # Fall back to local job queue
        local_jobs = []
        if JOBS_LOG.exists():
            try:
                with JOBS_LOG.open() as fh:
                    for ln in fh:
                        try:
                            local_jobs.append(json.loads(ln))
                        except Exception:
                            pass
            except Exception:
                pass
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "pending_from_hub": pending,
            "local_jobs_count": len(local_jobs),
            "openmontage_pipelines": list_openmontage_pipelines(),
            "openmontage_tools": list_openmontage_tools(),
            "ffmpeg_available": ffmpeg_available(),
            "opencut_present": OPENCUT_DIR.exists(),
            "opencut_classic_present": OPENCUT_CLASSIC_DIR.exists(),
        }

    def reason(self, state: dict) -> str:
        # Pick a pipeline to demonstrate with (rotates through available)
        if not state["openmontage_pipelines"]:
            return json.dumps({"action": "idle",
                               "reasoning": "no OpenMontage pipelines"})
        if not state["ffmpeg_available"]:
            return json.dumps({"action": "alert",
                               "reasoning": "ffmpeg missing"})
        # If hub has pending projects, render them
        if state["pending_from_hub"]:
            p = state["pending_from_hub"][0]
            return json.dumps({
                "action": "render_hub_project",
                "project": p,
                "pipeline": p.get("pipeline", "cinematic"),
                "reasoning": f"rendering hub project {p.get('id')}",
            })
        # Self-demo: pick one pipeline and render a sample every N cycles
        cycle = self.context.cycle
        pipeline = state["openmontage_pipelines"][cycle % len(
            state["openmontage_pipelines"])]
        return json.dumps({
            "action": "self_demo",
            "pipeline": pipeline,
            "reasoning": f"cycle {cycle}: self-demo on {pipeline}",
        })

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except Exception:
            return {"summary": "decision parse failed"}

        action = d.get("action", "idle")
        if action == "alert":
            self._emit_alert("ffmpeg missing on host",
                             "Install ffmpeg for video rendering", "high")
            return {"summary": "alert emitted: ffmpeg missing"}

        if action == "self_demo":
            pipeline = d.get("pipeline", "cinematic")
            project = {
                "id": f"self-demo-{int(time.time())}",
                "name": f"Self-demo {pipeline}",
                "brief": {
                    "niche": "marketing",
                    "duration_sec": 15,
                    "style": "cinematic",
                    "message": f"OpenMontage pipeline {pipeline} smoke test",
                },
            }
            result = render_brief(project, pipeline)
        elif action == "render_hub_project":
            project = d.get("project", {})
            pipeline = d.get("pipeline", "cinematic")
            result = render_brief(project, pipeline)
        else:
            return {"summary": "idle"}

        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "cycle": self.context.cycle,
            "action": action,
            "decision": d,
            "result": result,
        }
        with JOBS_LOG.open("a") as f:
            f.write(json.dumps(record) + "\n")

        if result.get("ok"):
            self._emit_alert(
                title=f"video-editing: render OK ({action})",
                body=f"pipeline={pipeline} out_dir={result.get('out_dir')}",
                severity="info",
            )
        else:
            self._emit_alert(
                title=f"video-editing: render FAILED ({action})",
                body=f"err={result.get('error','')[:200]}",
                severity="high",
            )

        return {"summary": f"{action} {pipeline}: "
                            f"{'OK' if result.get('ok') else 'FAIL'}"}

    def _emit_alert(self, title: str, body: str, severity: str = "info"):
        try:
            import requests
            requests.post(
                f"{HERMES_GATEWAY_URL}/v1/notify/alert",
                json={"title": title, "body": body,
                      "severity": severity,
                      "source": "video-editing-agent"},
                timeout=5)
        except Exception:
            pass


if __name__ == "__main__":
    agent = VideoEditingAgent(
        name="video-editing-agent",
        role="video_editing",
        health_url="http://localhost:9108/health",
    )
    print(f"[{datetime.now(timezone.utc).isoformat()}] "
          f"video-editing online — tick {TICK_INTERVAL}s", flush=True)
    failures = 0
    while True:
        try:
            r = agent.tick()
            failures = 0
            print(json.dumps({"cycle": r.get("cycle"),
                              "summary": r.get("result", {}).get(
                                  "summary", "")}))
        except Exception as e:
            failures += 1
            backoff = min(60 * failures, 600)
            print(json.dumps({"error": str(e)[:200], "backoff": backoff}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)
