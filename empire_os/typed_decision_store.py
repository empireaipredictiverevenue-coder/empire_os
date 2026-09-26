"""Append-only persistence contract for empire_eval typed-decision evidence.

This module performs no connection setup. Callers must inject an execute
function. It never issues UPDATE/DELETE/TRUNCATE and never targets public.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

ExecuteFn = Callable[[str, Mapping[str, Any]], Any]

_ALLOWED_TABLES = {
    "shadow_observations",
    "reviewed_labels",
    "provider_outputs",
    "dataset_manifests",
    "eval_reports",
    "shadow_decisions",
}


class TypedDecisionStore:
    def __init__(self, execute: ExecuteFn):
        if not callable(execute):
            raise ValueError("execute callable required")
        self._execute = execute

    def append(self, table: str, values: Mapping[str, Any]) -> Any:
        if table not in _ALLOWED_TABLES:
            raise ValueError("unsupported typed-decision table")
        if not values:
            raise ValueError("values required")
        columns = list(values.keys())
        if any(not str(c).replace("_", "").isalnum() for c in columns):
            raise ValueError("unsafe column name")

        placeholders = [f":{column}" for column in columns]
        sql = (
            f"INSERT INTO empire_eval.{table} "
            f"({', '.join(columns)}) "
            f"VALUES ({', '.join(placeholders)}) "
            "RETURNING *"
        )
        return self._execute(sql, dict(values))

    def append_shadow_observation(self, values: Mapping[str, Any]) -> Any:
        return self.append("shadow_observations", values)

    def append_reviewed_label(self, values: Mapping[str, Any]) -> Any:
        return self.append("reviewed_labels", values)

    def append_provider_output(self, values: Mapping[str, Any]) -> Any:
        return self.append("provider_outputs", values)

    def append_dataset_manifest(self, values: Mapping[str, Any]) -> Any:
        return self.append("dataset_manifests", values)

    def append_eval_report(self, values: Mapping[str, Any]) -> Any:
        return self.append("eval_reports", values)

    def append_shadow_decision(self, values: Mapping[str, Any]) -> Any:
        return self.append("shadow_decisions", values)
