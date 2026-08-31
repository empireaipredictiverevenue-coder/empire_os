#!/usr/bin/env python3
"""context.py — context engineering for the agentic software factory.

Pattern (learned from Empire OS agent debugging 2026-08):
- Never dump whole repo into a worker prompt.
- Give worker ONLY the file + function signature it needs (subagent scoping).
- Lazy-load via repo map. RAG-ready: plug Pinecone embeddings for retrieve().
- Compress tool output before re-inject (summarize, truncate old turns).
"""
from __future__ import annotations
import os, subprocess, json

REPO_ROOT = "/root/empire_os"


def repo_map(root: str = REPO_ROOT, max_files: int = 60) -> str:
    """Aider-style tree: directories + top files, no body."""
    out = []
    for dp, dn, fn in os.walk(root):
        if any(seg in dp for seg in ("/.git", "/__pycache__", "/node_modules", "/.venv", "/venv")):
            dn[:] = []
            continue
        depth = dp[len(root):].count(os.sep)
        if depth > 3:
            dn[:] = []
            continue
        out.append(f"{'  '*depth}{os.path.basename(dp)}/")
        for f in sorted(fn)[:max_files]:
            if f.endswith((".pyc", ".pyo")):
                continue
            out.append(f"{'  '*(depth+1)}{f}")
    return "\n".join(out)


def scope_files(target_paths: list[str], root: str = REPO_ROOT) -> str:
    """Pull ONLY the exact files a worker needs into its context. No more."""
    chunks = []
    for p in target_paths:
        full = p if p.startswith("/") else os.path.join(root, p)
        if os.path.isfile(full):
            with open(full) as fh:
                body = fh.read()
            chunks.append(f"### FILE: {p}\n{body}\n### END {p}")
    return "\n\n".join(chunks)


def compress_tool_output(raw: str, max_chars: int = 2000) -> str:
    """Summarize/truncate before re-injecting into agent context."""
    if len(raw) <= max_chars:
        return raw
    head = raw[:max_chars // 2]
    tail = raw[-max_chars // 2:]
    return f"{head}\n...[{len(raw)-max_chars} chars truncated]...\n{tail}"


def retrieve(query: str, top_k: int = 5) -> list[str]:
    """RAG hook. Stub: plug Pinecone/embeddings here. Returns file paths."""
    # TODO: embed query, query Pinecone index "empire-code", return top_k paths.
    return []


if __name__ == "__main__":
    print(repo_map())
    sys.exit(0)
