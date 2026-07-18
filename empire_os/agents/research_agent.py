"""
research_agent.py — slim MindSearch-style deep researcher for Empire OS.

Pattern (from InternLM/MindSearch, arxiv 2407.20183):
  1. Decompose a question into parallel sub-queries (Solver/Planner).
  2. Fan out web searches concurrently (keyless DuckDuckGo lite — free).
  3. Synthesize a cited answer from the gathered snippets (Solver).

Slimmed vs upstream: no Gradio/FastAPI/lagent. Headless daemon. Uses the
free OpenRouter model for decompose+solve, keyless DDG for search. Writes
guarded artifacts only (artifact guardrail, same as North-mini/last30days).

Run: python3 empire_os/agents/research_agent.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
from empire_os.agent_core import OpenRouterClient
from empire_os.agents.guardrails import scrub_secrets, safe_write

FEED = Path("/root/feedback")
OUT = FEED / "research_runs.jsonl"
MODEL = "cohere/north-mini-code:free"
TICK = 1800  # 30 min
DECOMPOSE_TIMEOUT = 40
SOLVE_TIMEOUT = 60
SEARCH_TIMEOUT = (4, 90)  # (min, max) — wigolo cold-start can be slow first call
MAX_SUBQUERIES = 5

# Questions Empire OS wants answered (edit freely).
QUESTIONS = [
    "competitive landscape for open-source B2B lead generation in 2026",
    "what are the cheapest ways to accept crypto payments for SaaS in 2026",
    "market gap for AI agent marketplaces targeting small business",
]


import logging
log = logging.getLogger("research")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_client = None


def client() -> OpenRouterClient:
    global _client
    if _client is None:
        _client = OpenRouterClient()
    return _client


def decompose(question: str) -> list[str]:
    """Planner: split into 3-5 parallel sub-queries (free LLM)."""
    sys_p = ("You are a research planner. Given a question, output 3-5 short "
             "parallel web-search sub-queries that together answer it. "
             "Strict JSON: {\"subqueries\": [\"...\", \"...\"]}. No prose.")
    raw = client().chat(
        [{"role": "user", "content": f"Question: {question}"}],
        system=sys_p, temperature=0.2, max_tokens=400)
    if not raw:
        return [question]
    try:
        d = json.loads(raw)
        subs = d.get("subqueries", [])
        if isinstance(subs, list) and subs:
            return [str(s) for s in subs[:MAX_SUBQUERIES]]
    except (json.JSONDecodeError, TypeError):
        pass
    return [question]


def wigolo_search(query: str) -> list[dict]:
    """Keyless local web search via wigolo MCP CLI (no API key, cached).

    Shells out to `npx wigolo search --json` — replaces the fragile DDG
    HTML scrape. Returns snippets with query/title/url/snippet.
    """
    try:
        proc = subprocess.run(
            ["npx", "-y", "wigolo@latest", "search", query,
             "--json", "--max-results", "5", "--no-content"],
            capture_output=True, text=True, timeout=SEARCH_TIMEOUT[1])
        if proc.returncode != 0:
            return []
        # stdout is a JSON object (possibly prefixed by stray log lines);
        # extract the first balanced {...} block.
        out = proc.stdout
        start = out.find("{")
        if start == -1:
            return []
        depth = 0
        end = -1
        for i in range(start, len(out)):
            if out[i] == "{":
                depth += 1
            elif out[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end == -1:
            return []
        data = json.loads(out[start:end + 1])
        results = []
        for r in data.get("results", []):
            results.append({
                "query": query,
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("excerpt", "") or r.get("snippet", ""),
            })
        return results[:5]
    except (subprocess.SubprocessError, json.JSONDecodeError, KeyError,
            ValueError, OSError):
        return []


def fanout(subqueries: list[str]) -> list[dict]:
    """Run all sub-queries concurrently (MindSearch parallel search)."""
    results: list[dict] = []
    lock = threading.Lock()

    def worker(q: str):
        r = wigolo_search(q)
        with lock:
            results.extend(r)

    threads = [threading.Thread(target=worker, args=(q,), daemon=True)
               for q in subqueries]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=SEARCH_TIMEOUT[1] + 2)
    return results


def solve(question: str, subqueries: list[str], results: list[dict]) -> str:
    """Solver: synthesize a cited answer from gathered snippets (free LLM)."""
    if not results:
        # No sources gathered — honest answer, skip the LLM round-trip
        # (avoids burning free-tier capacity on an unanswerable query).
        return ("No web sources were gathered for this question, so I cannot "
                "synthesize a cited answer. Try again later or check search "
                "connectivity.")
    ctx = "\n".join(
        f"[{i+1}] ({r.get('query','')}) {r.get('title','')} "
        f"{r.get('url','')}\n   {r.get('snippet','')}"
        for i, r in enumerate(results[:20]))
    sys_p = ("You are a research synthesizer (MindSearch-style). Given a "
             "question, the sub-queries used, and gathered web snippets, write "
             "a concise answer with inline citations like [1], [2]. Cite only "
             "from the provided snippets. If snippets are thin, say so. No "
             "invented sources.")
    user = (f"Question: {question}\nSub-queries: {subqueries}\n\n"
            f"Gathered snippets:\n{ctx}\n\nAnswer with citations:")
    raw = client().chat([{"role": "user", "content": user}],
                         system=sys_p, temperature=0.3, max_tokens=900)
    return raw or "(solver returned no answer)"


def research(question: str) -> dict:
    subs = decompose(question)
    log.info("decomposed into %s sub-queries", len(subs))
    results = fanout(subs)
    log.info("gathered %s snippets", len(results))
    answer = solve(question, subs, results)
    return {
        "question": question,
        "subqueries": subs,
        "num_sources": len(results),
        "answer": scrub_secrets(answer),
        "sources": [{"title": r.get("title", ""), "url": r.get("url", "")}
                    for r in results[:10]],
    }


def cycle_once() -> None:
    for q in QUESTIONS:
        try:
            rec = {"ts": time.time(), "engine": "research", "question": q,
                   **research(q)}
            safe_write(OUT, json.dumps(rec) + "\n", "artifact", "research")
            log.info("wrote research artifact q=%s", q[:50])
        except Exception as e:
            log.exception("research error q=%s: %s", q, e)


def main() -> None:
    log.info("research agent start — %s questions, tick=%ss", len(QUESTIONS), TICK)
    while True:
        try:
            cycle_once()
        except Exception as e:
            log.exception("cycle error: %s", e)
        time.sleep(TICK)


if __name__ == "__main__":
    main()
