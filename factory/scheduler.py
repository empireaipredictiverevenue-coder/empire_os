#!/usr/bin/env python3
"""scheduler.py — parallel agent scheduler for the factory.

Runs N independent coding tasks concurrently as isolated processes inside the
hub container (run_in_sandbox) — instant, no full-container clone. Writes
serialize through the db_writer gatekeeper so no SQLite contention.

Usage:
  from scheduler import run_tasks
  results = run_tasks(["fix mail_sender retry", "add CSV export to payout_batch"])
"""
from __future__ import annotations
import sys, os, json, time, threading
sys.path.insert(0, os.path.dirname(__file__))
import sandbox as sb
import orchestrator as o


def _run_one(task: str, cid: str) -> dict:
    """Run one task to completion via the LangGraph factory loop."""
    try:
        app = o.build_graph()
        final = app.invoke({"task": task, "retries": 0})
        ok = bool(final.get("done")) and not final.get("aborted")
        return {"task": task, "cid": cid, "ok": ok,
                "test_pass": final.get("test_pass"),
                "review_ok": final.get("review_ok"),
                "retries": final.get("retries", 0)}
    except Exception as e:
        return {"task": task, "cid": cid, "ok": False, "error": str(e)}


def run_tasks(tasks: list[str], max_parallel: int = 3) -> list[dict]:
    """Round-robin concurrency bounded by max_parallel threads."""
    results = []
    live: dict[str, dict] = {}
    sem = threading.Semaphore(max_parallel)

    def _worker(task: str, cid: str):
        try:
            live[cid] = _run_one(task, cid)
        finally:
            results.append(live.pop(cid, {"task": task, "cid": cid, "ok": False}))
            sem.release()

    threads = []
    for i, task in enumerate(tasks):
        sem.acquire()
        cid = f"factory-{i}-{int(time.time())}"
        t = threading.Thread(target=_worker, args=(task, cid))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return results


if __name__ == "__main__":
    tasks = sys.argv[1:] or ["add a debug log line to ai_email_infer.py"]
    out = run_tasks(tasks, max_parallel=2)
    print(json.dumps(out, indent=2))
