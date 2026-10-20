"""Portable opt-in Graphify enhancement for an existing EmpireCoder instance.

Avoid replacing or patching the owner Coder's orchestrator.py/context.py.
Use explicit one-time attachment after construction; default Coder remains
unchanged. Graph context is source-attested and re-read via RepoIntelligence.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable

from .context import ContextPack
from .graphify_context import GraphifyContextSource


class GraphifyContextOverlay:
    def __init__(self, delegate, source: GraphifyContextSource):
        if not callable(getattr(delegate, "build", None)):
            raise TypeError("existing context builder required")
        if not callable(getattr(delegate, "set_active_knowledge_paths", None)):
            raise TypeError("existing Coder knowledge-guard interface required")
        if not isinstance(source, GraphifyContextSource):
            raise TypeError("source-attested Graphify context required")
        repo = getattr(delegate, "repo", None)
        if repo is None or Path(repo.root).resolve() != source.workspace:
            raise ValueError("Coder and Graphify workspace mismatch")
        if not callable(getattr(delegate, "_knowledge_allowed", None)):
            raise TypeError("Coder knowledge-path policy required")
        self.delegate = delegate
        self.source = source
        self.repo = repo

    def set_active_knowledge_paths(self, paths: Iterable[str]) -> None:
        self.delegate.set_active_knowledge_paths(paths)

    def build(
        self, task, *, terms: Iterable[str] = (),
        symbol_terms: Iterable[str] = (), budget_chars: int = 24_000,
    ) -> ContextPack:
        # Base Coder remains responsible for blueprint, permissions, task
        # documents, token budgeting, and Knowledge Garden.
        terms = tuple(terms)
        symbol_terms = tuple(symbol_terms)
        result = self.delegate.build(
            task, terms=terms, symbol_terms=symbol_terms,
            budget_chars=budget_chars,
        )
        if not terms and not symbol_terms:
            return result
        # The underlying graph fails closed if its source has changed.
        graph_docs = self.source.documents(
            terms=terms + symbol_terms,
            repo=self.repo,
            max_docs=3,
            max_chars=min(2200, max(500, budget_chars // 8)),
        )
        documents = list(result.documents)
        existing_paths = {doc.path for doc in documents}
        # Preserve the base Coder's budget by restricting supplementary
        # excerpts to the approved Graphify budget and respecting duplicates.
        remaining = max(
            0, result.token_budget_chars
            - sum(len(doc.excerpt) for doc in documents)
        )
        for item in graph_docs:
            if not self.delegate._knowledge_allowed(item.path):
                continue
            if item.path in existing_paths:
                # Keep the original source excerpt, avoid duplicate context,
                # and record that a fresh Graphify relation also selected it.
                for idx, document in enumerate(documents):
                    if (document.path == item.path and
                            "attested Graphify" not in document.reason):
                        documents[idx] = replace(
                            document,
                            reason=document.reason + "; attested Graphify code relationship",
                        )
                        break
                continue
            if len(item.excerpt) > remaining:
                continue
            documents.append(item)
            existing_paths.add(item.path)
            remaining -= len(item.excerpt)
        return ContextPack(
            objective=result.objective,
            task_state=result.task_state,
            documents=tuple(documents),
            symbols=result.symbols,
            token_budget_chars=result.token_budget_chars,
        )


def attach_graphify_context(coder, source: GraphifyContextSource) -> None:
    """Attach to an existing caller-owned Coder; no patches or workers.

    The authorized Coder owner chooses whether to call this function. No
    global state is set; no production auto-install is performed.
    """
    original = getattr(coder, "context", None)
    if isinstance(original, GraphifyContextOverlay):
        raise ValueError("Graphify code context is already attached")
    if not isinstance(source, GraphifyContextSource):
        raise TypeError("invalid Graphify source")
    workspace = getattr(coder, "workspace", None)
    if workspace is None or Path(workspace).resolve() != source.workspace:
        raise ValueError("Coder and Graphify workspace mismatch")
    enhanced = GraphifyContextOverlay(original, source)
    coder.context = enhanced
