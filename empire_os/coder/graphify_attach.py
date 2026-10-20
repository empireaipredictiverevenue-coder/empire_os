"""Portable opt-in Graphify enhancement for an existing EmpireCoder instance.

Avoid replacing or patching the owner Coder's orchestrator.py/context.py.
Use explicit one-time attachment after construction; default Coder remains
unchanged. Graph context is source-attested and re-read via RepoIntelligence.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re
from typing import Iterable

from .context import ContextPack
from .graphify_context import GraphifyContextSource


_CAMEL_SYMBOL = re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b")
_SNAKE_SYMBOL = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_PYTHON_MODULE = re.compile(
    r"(?<![A-Za-z0-9/])(?:[A-Za-z_][A-Za-z0-9_]*/){0,5}"
    r"[A-Za-z_][A-Za-z0-9_]*\.py\b"
)


def explicit_code_hints(objective: str) -> tuple[str, ...]:
    """Recognise only overt CODE identifiers, never invent semantic terms."""
    if not isinstance(objective, str):
        return ()
    text = objective[:2048]
    found: list[str] = []
    for expression in (_PYTHON_MODULE, _CAMEL_SYMBOL, _SNAKE_SYMBOL):
        for match in expression.finditer(text):
            value = match.group(0)
            if 3 <= len(value) <= 128 and value not in found:
                found.append(value)
            if len(found) >= 8:
                return tuple(found)
    return tuple(found)


class GraphifyContextOverlay:
    def __init__(
        self, delegate, source: GraphifyContextSource, *,
        unavailable: str = "raise",
    ):
        if not callable(getattr(delegate, "build", None)):
            raise TypeError("existing context builder required")
        if not callable(getattr(delegate, "set_active_knowledge_paths", None)):
            raise TypeError("existing Coder knowledge-guard interface required")
        if not isinstance(source, GraphifyContextSource):
            raise TypeError("source-attested Graphify context required")
        if unavailable not in {"raise", "skip"}:
            raise ValueError("Graphify unavailability policy must be raise or skip")
        repo = getattr(delegate, "repo", None)
        if repo is None or Path(repo.root).resolve() != source.workspace:
            raise ValueError("Coder and Graphify workspace mismatch")
        if not callable(getattr(delegate, "_knowledge_allowed", None)):
            raise TypeError("Coder knowledge-path policy required")
        self.delegate = delegate
        self.source = source
        self.repo = repo
        self.unavailable = unavailable
        self.last_graph_status = "NOT_QUERIED"
        self._usage = {
            "query_attempts": 0,
            "objective_code_hint_queries": 0,
            "attested_queries": 0,
            "stale_or_invalid_queries": 0,
            "graph_candidate_files": 0,
            "already_in_base_context": 0,
            "new_context_files": 0,
            "new_context_characters": 0,
        }

    def metrics_snapshot(self) -> dict[str, int | str]:
        """Aggregate COUNTS only. No prompt text, paths, tenant IDs or revenue."""
        return {
            "schema_version": "empire.graphify.context_usage.v1",
            "status": self.last_graph_status,
            **self._usage,
        }

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
            # Only explicit Python identifiers in an existing task objective;
            # do not mine free-form business language or create fake signals.
            discovered = explicit_code_hints(getattr(task, "objective", ""))
            if not discovered:
                return result
            terms = discovered
            self._usage["objective_code_hint_queries"] += 1
        self._usage["query_attempts"] += 1
        # The underlying graph fails closed if its source has changed.
        try:
            graph_docs = self.source.documents(
                terms=terms + symbol_terms,
                repo=self.repo,
                max_docs=3,
                max_chars=min(2200, max(500, budget_chars // 8)),
            )
        except (ValueError, OSError, UnicodeError) as exc:
            self.last_graph_status = "UNAVAILABLE_" + exc.__class__.__name__
            self._usage["stale_or_invalid_queries"] += 1
            if self.unavailable == "skip":
                return result
            raise
        self.last_graph_status = "ATTESTED_CODE_CONTEXT_READ"
        self._usage["attested_queries"] += 1
        self._usage["graph_candidate_files"] += len(graph_docs)
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
                self._usage["already_in_base_context"] += 1
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
            self._usage["new_context_files"] += 1
            self._usage["new_context_characters"] += len(item.excerpt)
            existing_paths.add(item.path)
            remaining -= len(item.excerpt)
        return ContextPack(
            objective=result.objective,
            task_state=result.task_state,
            documents=tuple(documents),
            symbols=result.symbols,
            token_budget_chars=result.token_budget_chars,
        )


def attach_graphify_context(
    coder, source: GraphifyContextSource, *, unavailable: str = "raise",
) -> None:
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
    enhanced = GraphifyContextOverlay(
        original, source, unavailable=unavailable,
    )
    coder.context = enhanced
