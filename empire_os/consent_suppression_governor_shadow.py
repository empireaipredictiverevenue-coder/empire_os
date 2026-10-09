# EMPIRE_WAVE_090C_C
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
import ast
import re


ROOT = Path("/srv/empire_os")


EXACT_SUPPRESSION_SIGNALS = (
    "outbound_suppressions",
    "is_suppressed",
    "suppression_reason",
    "suppression_key",
    "check_suppression",
    "suppressed",
)


@dataclass(frozen=True)
class SourceNode:
    path: str
    imports: tuple[str, ...]
    suppression_signals: tuple[str, ...]

    def as_dict(self):
        return asdict(self)


def module_to_path(
    module: str,
) -> Path | None:

    if not module:
        return None

    if module.startswith(
        "empire_os."
    ):

        relative = (
            module.replace(
                ".",
                "/",
            )
            + ".py"
        )

        path = ROOT / relative

        if path.exists():
            return path

    return None


def local_imports(
    path: Path,
) -> set[Path]:

    try:
        tree = ast.parse(
            path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        )

    except Exception:
        return set()

    found = set()

    for node in ast.walk(
        tree
    ):

        if isinstance(
            node,
            ast.Import,
        ):

            for alias in node.names:

                target = module_to_path(
                    alias.name
                )

                if target:
                    found.add(
                        target
                    )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):

            module = (
                node.module
                or ""
            )

            target = module_to_path(
                module
            )

            if target:
                found.add(
                    target
                )

            for alias in node.names:

                target = module_to_path(
                    module
                    + "."
                    + alias.name
                )

                if target:
                    found.add(
                        target
                    )

    return found


def suppression_signals(
    path: Path,
) -> set[str]:

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        ).casefold()

    except Exception:
        return set()

    return {
        signal
        for signal in EXACT_SUPPRESSION_SIGNALS
        if signal in text
    }


def trace_local_graph(
    entry: Path,
    *,
    max_nodes: int = 120,
):

    queue = [
        entry
    ]

    visited = set()
    nodes = []

    while queue:

        path = queue.pop(
            0
        ).resolve()

        if path in visited:
            continue

        if len(
            visited
        ) >= max_nodes:
            break

        try:
            path.relative_to(
                ROOT
            )
        except ValueError:
            continue

        if not path.exists():
            continue

        visited.add(
            path
        )

        imports = local_imports(
            path
        )

        signals = suppression_signals(
            path
        )

        nodes.append(
            SourceNode(
                path=str(
                    path.relative_to(
                        ROOT
                    )
                ),
                imports=tuple(
                    sorted(
                        str(
                            x.relative_to(
                                ROOT
                            )
                        )
                        for x in imports
                    )
                ),
                suppression_signals=tuple(
                    sorted(
                        signals
                    )
                ),
            )
        )

        for imported in imports:

            if imported not in visited:
                queue.append(
                    imported
                )

    return nodes


def python_paths_from_execstart(
    execstart: str,
):

    paths = []

    for match in re.findall(
        r"/srv/empire_os/[A-Za-z0-9_./-]+\.py",
        execstart,
    ):

        path = Path(
            match
        )

        if path.exists():

            paths.append(
                path
            )

    return paths
