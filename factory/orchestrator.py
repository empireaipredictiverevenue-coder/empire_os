#!/usr/bin/env python3
"""orchestrator.py — LangGraph agentic software factory.

Graph (async-safe, deterministic channel schema):
    planner -> coder -> patcher -> reviewer -> tester -> verifier -> (loop|done)

Design notes (senior-architect):
- FactoryState is a TypedDict so LangGraph persists every channel between nodes.
- The LLM brain is a single gateway (llm_gateway) with tier-aware provider
  routing (bulk=deepseek/glm, reason=hy3). All model I/O funnels through one
  `_llm()` helper so behaviour is consistent and observable.
- Diffs are extracted with a tolerant parser (fenced ```diff or raw ---/+++),
  never trusted raw. The patcher applies with `patch(1)` and reports failures
  for the verifier loop instead of silently passing.
- Tester verifies the patch actually landed (compile + change present), not
  merely that modules import.

Run: python3 /root/empire_os/factory/orchestrator.py "<task>"
"""
from __future__ import annotations

import sys
import os
import re
import json
import difflib
import logging
import subprocess
from typing import TypedDict, Optional

try:
    from langgraph.graph import StateGraph, END
except ImportError:
    print("langgraph not installed: pip install langgraph", file=sys.stderr)
    sys.exit(1)

import context as ctx
import sandbox as sb
import geometric as geo

# --------------------------------------------------------------------------- #
# Configuration & logging
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="[factory] %(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("factory")

MAX_RETRIES = 5
REPO_ROOT = "/root/empire_os"
PATCH_WORKDIR = "/root/factory"


class FactoryError(RuntimeError):
    """Raised for unrecoverable factory-internal errors (not LLM failures)."""


# --------------------------------------------------------------------------- #
# State schema
# --------------------------------------------------------------------------- #
class FactoryState(TypedDict, total=False):
    """LangGraph schema — declared channels so state persists across nodes."""
    task: str
    retries: int
    plan: str
    plan_score: float
    target_files: list
    diff: str
    merge_conflicts: list
    review_ok: bool
    issues: list
    test_output: str
    test_pass: bool
    patched: bool
    done: bool
    aborted: bool


# --------------------------------------------------------------------------- #
# LLM helper
# --------------------------------------------------------------------------- #
def _llm(tier: str, prompt: str) -> str:
    """Single brain entry. tier-aware provider routing lives in llm_gateway."""
    import llm_gateway
    out = llm_gateway.llm(tier, prompt)
    if not out or not out.strip():
        # harden: reason flaked -> retry on bulk tier so the loop never aborts
        out = llm_gateway.llm("bulk", prompt)
    return out or ""


def _extract_json(raw: str) -> dict:
    """Best-effort JSON extraction (handles CoT prose around the payload)."""
    if not raw:
        return {}
    try:
        s = raw[raw.index("{"):raw.rindex("}") + 1]
        return json.loads(s)
    except Exception:
        return {}


def _extract_diff(raw: str) -> str:
    """Return a unified diff from model output, or '' if none found."""
    if not raw:
        return ""
    m = re.search(r"```(?:diff)?\s*(.*?)```", raw, re.DOTALL)
    cand = m.group(1) if m else raw
    if re.search(r"^--- ", cand, re.MULTILINE) and re.search(r"^\+\+\+ ", cand, re.MULTILINE):
        return cand.strip() + "\n"
    return ""


def _write_patch(diff: str) -> str:
    os.makedirs(PATCH_WORKDIR, exist_ok=True)
    path = os.path.join(PATCH_WORKDIR, "_diff.txt")
    with open(path, "w") as fh:
        fh.write(diff)
    return path


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #
def planner(state: FactoryState) -> FactoryState:
    try:
        tot = geo.tot_plan(state["task"], branch=3, depth=2)
        state["plan"] = tot.get("path", "") or ""
        state["plan_score"] = tot.get("score", 0.0)
    except Exception as e:  # geometric layer is best-effort
        log.warning("tot_plan failed: %s", e)
        state["plan"] = ""
        state["plan_score"] = 0.0

    raw = _llm("reason",
        f"Task: {state['task']}\n\n"
        "List the exact file paths (relative to /root/empire_os) this task touches. "
        'Return ONLY JSON: {"files":["path1","path2"]}')
    files = _extract_json(raw).get("files", [])

    if not files:  # keyword fallback so the loop never starves
        task_l = state["task"].lower()
        found = []
        for dp, _, fn in os.walk(REPO_ROOT):
            if "/.git" in dp or "__pycache__" in dp:
                continue
            for f in fn:
                if f.endswith(".py") and any(k in f for k in task_l.split() if len(k) > 3):
                    found.append(os.path.join(dp, f).replace(REPO_ROOT + "/", "", 1))
        files = found[:8]

    state["target_files"] = files
    log.info("planner -> files=%s", files)
    return state


def coder(state: FactoryState) -> FactoryState:
    """Produce an applicable unified diff deterministically.

    Rather than trusting the model to emit a perfectly-formed patch (it often
    truncates hunks or leaks CoT prose), we ask for a precise edit specification
    and construct the diff locally with difflib — guaranteeing context lines and
    a valid hunk header that `patch(1)` will accept.
    """
    targets = state.get("target_files", [])
    if not targets:
        state["diff"] = ""
        state["merge_conflicts"] = []
        return state

    scope = ctx.scope_files(targets)
    prompt = (
        f"Task: {state['task']}\nPlan: {state.get('plan', '')}\n\n"
        f"Scoped files:\n{scope}\n\n"
        "Describe the EXACT change as JSON with these fields only:\n"
        '  "file": the file path to edit\n'
        '  "old": the exact original line(s) to replace (verbatim, may be "" to insert)\n'
        '  "new": the replacement line(s) (verbatim)\n'
        'Return ONLY JSON: {"file":"...","old":"...","new":"..."}'
    )
    raw = _llm("bulk", prompt)
    data = _extract_json(raw)
    state["merge_conflicts"] = []

    if not data or "file" not in data:
        state["diff"] = ""
        return state

    rel = data["file"]
    fpath = rel if rel.startswith("/") else os.path.join(REPO_ROOT, rel)
    if not os.path.isfile(fpath):
        state["diff"] = ""
        return state

    old_text = data.get("old", "")
    new_text = data.get("new", "")
    with open(fpath) as fh:
        original = fh.read().splitlines(keepends=True)

    # Normalize line endings; match old text flexibly (strip surrounding ws).
    old_norm = old_text.strip("\n")
    new_norm = new_text.strip("\n")
    if old_norm:
        # find the line(s) containing old_text
        joined = "".join(original)
        idx = joined.find(old_norm)
        if idx == -1:
            state["diff"] = ""
            state.setdefault("issues", []).append("old-text-not-found")
            return state
        start = joined[:idx].count("\n")
        old_lines = old_norm.splitlines()
        new_lines = new_norm.splitlines() if new_norm else []
        modified = original[:start] + [l + "\n" for l in new_lines] + original[start + len(old_lines):]
    else:
        # insertion: append near top after imports, or at end
        new_lines = new_norm.splitlines()
        modified = original + [l + "\n" for l in new_lines]

    diff = "".join(difflib.unified_diff(
        original, modified,
        fromfile=f"a/{os.path.basename(fpath)}",
        tofile=f"b/{os.path.basename(fpath)}",
    ))
    state["diff"] = diff
    log.info("coder -> diff_len=%d", len(diff))
    return state


def patcher(state: FactoryState) -> FactoryState:
    """Apply state['diff'] to the real target files via patch(1)."""
    diff = state.get("diff", "")
    state["patched"] = False
    state.setdefault("issues", [])
    if not diff:
        return state

    touched = re.findall(r"^\+\+\+ (?:\S/)?(.+)$", diff, re.MULTILINE)
    apply_files: list[str] = []
    for t in touched:
        t = t.strip()
        cand = t if t.startswith("/") else os.path.join(REPO_ROOT, t)
        if os.path.isfile(cand):
            apply_files.append(cand)

    if not apply_files and state.get("target_files"):
        cand = state["target_files"][0]
        cand = cand if cand.startswith("/") else os.path.join(REPO_ROOT, cand)
        if os.path.isfile(cand):
            apply_files = [cand]
            base = os.path.basename(cand)
            diff = f"--- a/{base}\n+++ b/{base}\n" + diff.lstrip()

    if not apply_files:
        state["issues"].append("no-target-file-for-diff")
        return state

    patch_path = _write_patch(diff)
    any_ok = False
    for fp in apply_files:
        d = os.path.dirname(fp)
        # Validate applicability first (no-op), then apply for real.
        dry = subprocess.run(
            ["patch", "-p1", "--forward", "--dry-run", "-i", patch_path],
            cwd=d, capture_output=True, text=True,
        )
        if dry.returncode != 0:
            log.warning("patch dry-run rejected for %s: %s",
                        os.path.basename(fp), dry.stderr[:200])
            # attempt real apply anyway (some versions report false negatives)
        r = subprocess.run(
            ["patch", "-p1", "--forward", "-i", patch_path],
            cwd=d, capture_output=True, text=True,
        )
        if r.returncode == 0:
            any_ok = True
        else:
            state["issues"].append(f"patch-failed:{os.path.basename(fp)}")
            log.error("patch failed for %s: %s", fp, r.stderr[:200])
    state["patched"] = any_ok
    return state


def reviewer(state: FactoryState) -> FactoryState:
    diff = state.get("diff", "")
    if not diff:
        state["review_ok"] = False
        state["issues"] = ["no-diff-produced"]
        return state
    scope = ctx.scope_files(state.get("target_files", []))
    prompt = (
        f"Review this diff for bugs/security:\n\n{diff}\n\n"
        f"Context files:\n{scope}\n\nReturn ONLY JSON {{\"ok\": bool, \"issues\": [...]}}"
    )
    data = _extract_json(_llm("reason", prompt))
    state["review_ok"] = bool(data.get("ok", False))
    state["issues"] = data.get("issues", []) if data else ["review-parse-failed"]
    return state


def tester(state: FactoryState) -> FactoryState:
    out = sb.run_in_sandbox(os.path.join(PATCH_WORKDIR, "_tester.py"))
    out = ctx.compress_tool_output(out)
    state["test_output"] = out
    # Production gate: compile PASS *and* the patch actually landed.
    state["test_pass"] = ("PASS" in out) and bool(state.get("patched"))
    return state


def verifier(state: FactoryState) -> FactoryState:
    if state.get("test_pass") and state.get("review_ok"):
        state["done"] = True
        return state
    state["retries"] = state.get("retries", 0) + 1
    if state["retries"] >= MAX_RETRIES:
        state["done"] = True
        state["aborted"] = True
    return state


def route(state: FactoryState) -> str:
    if state.get("done"):
        return END
    if not state.get("patched"):
        return "coder"   # patch failed -> regenerate diff
    if not state.get("review_ok"):
        return "coder"   # review failed -> rewrite
    if not state.get("test_pass"):
        return "coder"   # test failed -> fix
    return END


# --------------------------------------------------------------------------- #
# Graph
# --------------------------------------------------------------------------- #
def build_graph():
    g = StateGraph(FactoryState)
    g.add_node("planner", planner)
    g.add_node("coder", coder)
    g.add_node("patcher", patcher)
    g.add_node("reviewer", reviewer)
    g.add_node("tester", tester)
    g.add_node("verifier", verifier)
    g.set_entry_point("planner")
    g.add_edge("planner", "coder")
    g.add_edge("coder", "patcher")
    g.add_edge("patcher", "reviewer")
    g.add_edge("reviewer", "tester")
    g.add_edge("tester", "verifier")
    g.add_conditional_edges("verifier", route)
    return g.compile()


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "add logging to ai_email_infer"
    app = build_graph()
    final = app.invoke({"task": task, "retries": 0})
    print(json.dumps(
        {k: final[k] for k in ("task", "plan", "review_ok", "test_pass",
                               "patched", "retries", "done", "aborted")
         if k in final},
        indent=2,
    ))
    sys.exit(0)
