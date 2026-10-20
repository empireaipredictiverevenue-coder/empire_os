"""Opt-in, non-blocking pre-patch code relationship observation.

Attaches to ONE existing Coder INSTANCE, never modifies a Coder class,
worker queue, provider, approval decision, patch candidate or source tree.

The original apply_structured_patch is always invoked once with unchanged
arguments and its result or exception is returned unaltered. Graphify is
read-only, attested, policy-filtered and count-only in operational telemetry.
"""
from __future__ import annotations

from collections import Counter
from functools import wraps
from typing import Any

from .graphify_attach import GraphifyContextOverlay

SCHEMA = "empire.graphify.prepatch_observer.v1"


class GraphifyPrepatchObserver:
    def __init__(self, coder: Any) -> None:
        if not isinstance(getattr(coder, "context", None), GraphifyContextOverlay):
            raise ValueError("existing attested Graphify context required")
        original = getattr(coder, "apply_structured_patch", None)
        if not callable(original):
            raise TypeError("existing patch apply method required")
        if getattr(coder, "_graphify_prepatch_observer", None) is not None:
            raise ValueError("Graphify prepatch observer already attached")
        self.coder = coder
        self.original = original
        self._counts = Counter({
            "prepatch_attempts": 0,
            "attested_prepatch_reviews": 0,
            "unavailable_reviews": 0,
            "not_indexed_target_reviews": 0,
            "dependent_source_candidates": 0,
            "zero_dependency_reviews": 0,
        })

    def install(self) -> None:
        """Observe just before an already-authorised existing Coder apply call."""
        coder = self.coder
        if getattr(coder, "_graphify_prepatch_observer", None) is not None:
            raise ValueError("observer already attached")

        @wraps(self.original)
        def observing_apply(task_id, candidate, *args, **kwargs):
            # All path/eligibility/lease/owner controls remain with the
            # existing CoderTaskWorker, and this observer never authorises.
            self._counts["prepatch_attempts"] += 1
            target = getattr(getattr(candidate, "proposal", None), "target_path", None)
            try:
                if not isinstance(target, str):
                    raise ValueError("no inspectable target path")
                result = coder.context.review_change_impact(
                    (target,), max_affected=20,
                )
                count = result["affected_source_count"]
                if type(count) is not int or not 0 <= count <= 20:
                    raise ValueError("invalid bounded dependency count")
            except Exception as exc:
                # Optional observation must never veto an already-authorised
                # owner patch, including unexpected graph/policy exceptions.
                self._counts["unavailable_reviews"] += 1
                # Classify known lack-of-coverage separately from stale or
                # unreadable evidence; never export the exception message.
                if isinstance(exc, ValueError) and "not in attested graph" in str(exc):
                    self._counts["not_indexed_target_reviews"] += 1
            else:
                self._counts["attested_prepatch_reviews"] += 1
                self._counts["dependent_source_candidates"] += count
                if count == 0:
                    self._counts["zero_dependency_reviews"] += 1
            # Never catch, change, re-order or duplicate original apply.
            return self.original(task_id, candidate, *args, **kwargs)

        coder.apply_structured_patch = observing_apply
        coder._graphify_prepatch_observer = self

    def metrics_snapshot(self) -> dict[str, int | str | bool]:
        """No customer, task, prompt, path, patch, identity or model output."""
        return {
            "schema_version": SCHEMA,
            "mode": "OBSERVE",
            "patch_authority": False,
            **dict(self._counts),
        }


def attach_graphify_prepatch_observer(coder: Any) -> GraphifyPrepatchObserver:
    observer = GraphifyPrepatchObserver(coder)
    observer.install()
    return observer
