#!/usr/bin/env python3
"""geometric.py — geometric reasoning layer for the agentic factory.

Two engines:
  Tree-of-Thoughts (ToT): branch candidate solution paths, score each via
    LLM judge, keep top-k, expand, backtrack on dead-ends. Search over the
    space of change-sets instead of one-shot guessing.
  Graph-of-Thoughts (GoT): thoughts are nodes; edges = dependency/merge.
    Aggregate partial diffs, resolve conflicts between them, produce a merged
    plan. Lets parallel workers compose without clobbering.

Why geometric: flat prompt chains can't backtrack or merge. A graph of
thoughts is the shape of real engineering work — branches, merges, acycles.

Reuses: llm_gateway (single brain), context.repo_map/scope_files.
"""
from __future__ import annotations
import sys, json
sys.path.insert(0, "/root/empire_os")
import context as ctx


def _llm(tier: str, prompt: str) -> str:
    import llm_gateway
    return llm_gateway.llm(tier, prompt)


def _extract_json(raw: str) -> dict:
    try:
        s = raw[raw.index("{"):raw.rindex("}") + 1]
        return json.loads(s)
    except Exception:
        return {}


# ---------- Tree-of-Thoughts ----------

def tot_plan(task: str, branch: int = 3, depth: int = 2) -> dict:
    """Return best change-set path as a scored tree search.

    Returns {"path": [plan0, plan1, ...], "score": float, "leaves": int}
    """
    map_ = ctx.repo_map()

    def expand(parent_plan: str, level: int) -> dict:
        prompt = (
            f"Task: {task}\nRepo map:\n{map_}\n"
            f"Parent plan so far: {parent_plan or '(none)'}\n\n"
            f"Propose {branch} distinct NEXT steps (different approaches/files). "
            f"For each return {{\"step\": str, \"files\": [paths], \"rationale\": str}}. "
            f"Output JSON: {{\"steps\": [ ... ]}}"
        )
        data = _extract_json(_llm("reason", prompt))
        steps = data.get("steps", [])
        best = None
        for st in steps:
            sc = _score_step(task, st.get("step", ""), st.get("rationale", ""))
            if best is None or sc > best[1]:
                best = (st, sc)
        if best is None or level >= depth:
            return {"plan": (best[0].get("step", "") if best else ""), "score": (best[1] if best else 0.0), "leaves": 1}
        child = expand(parent_plan + " -> " + best[0].get("step", ""), level + 1)
        return {"plan": best[0].get("step", "") + " -> " + child["plan"], "score": best[1] + child["score"], "leaves": child["leaves"] + 1}

    root = expand("", 0)
    return {"path": root["plan"], "score": round(root["score"], 2), "leaves": root["leaves"]}


def _score_step(task: str, step: str, rationale: str) -> float:
    prompt = (
        f"Task: {task}\nCandidate step: {step}\nRationale: {rationale}\n\n"
        f"Score feasibility+correctness 0.0-1.0. JSON: {{\"score\": float, \"why\": str}}"
    )
    d = _extract_json(_llm("reason", prompt))
    try:
        return float(d.get("score", 0.0))
    except Exception:
        return 0.0


# ---------- Graph-of-Thoughts ----------

def got_merge(diffs: list[str], task: str) -> dict:
    """Merge N partial diffs into one coherent plan graph.

    Returns {"merged": str (unified plan text), "conflicts": [..], "nodes": int}
    """
    prompt = (
        f"Task: {task}\n\n{len(diffs)} partial solutions (from parallel workers):\n"
        + "\n\n---\n\n".join(f"[worker {i}]\n{d}" for i, d in enumerate(diffs))
        + "\n\nMerge into ONE coherent change set. List conflicts and how resolved. "
        f"JSON: {{\"merged\": str, \"conflicts\": [str], \"nodes\": int}}"
    )
    d = _extract_json(_llm("reason", prompt))
    return {
        "merged": d.get("merged", ""),
        "conflicts": d.get("conflicts", []),
        "nodes": d.get("nodes", len(diffs)),
    }


def got_aggregate(thoughts: list[str]) -> str:
    """Aggregate (reduce) a set of thought nodes into a summary plan."""
    prompt = (
        "Aggregate these thought nodes into a single ordered plan:\n"
        + "\n".join(f"- {t}" for t in thoughts)
        + "\nOutput the merged plan as plain text."
    )
    return _llm("bulk", prompt)


if __name__ == "__main__":
    print("geometric module loaded; ToT/GotT ready")
    sys.exit(0)
