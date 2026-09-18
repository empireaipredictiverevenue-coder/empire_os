"""Python symbol-aware patch helpers for Empire Coder."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from .patch import PatchEngine, PatchError


@dataclass(frozen=True)
class SymbolRange:
    name: str
    kind: str
    start_line: int
    end_line: int


def find_python_symbol(source: str, symbol_name: str) -> SymbolRange:
    tree = ast.parse(source)
    matches = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol_name:
                matches.append(node)
    if len(matches) != 1:
        raise PatchError(
            f"expected exactly one Python symbol named {symbol_name}, found {len(matches)}"
        )
    node = matches[0]
    end = getattr(node, "end_lineno", None)
    if end is None:
        raise PatchError(f"symbol {symbol_name} has no end_lineno")
    return SymbolRange(
        symbol_name,
        type(node).__name__,
        int(node.lineno),
        int(end),
    )


class AstPatchEngine:
    def __init__(self, patch_engine: PatchEngine) -> None:
        self.patch_engine = patch_engine

    def replace_python_symbol(
        self,
        task_id: str,
        path: str,
        symbol_name: str,
        replacement: str,
    ) -> dict[str, str]:
        source = self.patch_engine.read(path)
        symbol = find_python_symbol(source, symbol_name)
        lines = source.splitlines(keepends=True)
        start = symbol.start_line - 1
        end = symbol.end_line
        old = "".join(lines[start:end])
        replacement_text = replacement.rstrip() + "\n"
        if ast.parse(replacement_text) is None:
            raise PatchError("replacement did not parse")
        return self.patch_engine.replace_exact(
            task_id,
            path,
            old,
            replacement_text,
            expected_count=1,
        )

    def insert_after_python_symbol(
        self,
        task_id: str,
        path: str,
        symbol_name: str,
        addition: str,
    ) -> dict[str, str]:
        source = self.patch_engine.read(path)
        symbol = find_python_symbol(source, symbol_name)
        lines = source.splitlines(keepends=True)
        end = symbol.end_line
        old = "".join(lines[:end])
        new = old.rstrip() + "\n\n" + addition.rstrip() + "\n"
        return self.patch_engine.replace_exact(
            task_id,
            path,
            old,
            new,
            expected_count=1,
        )
