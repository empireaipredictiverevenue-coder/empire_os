"""Machine-readable execution ledger derived from Empire's canonical checklist.

The parser never infers production completion from code presence. It only reports
what the canonical markdown checklist explicitly marks and preserves source-line
provenance so live/runtime reconciliation can happen separately.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import re
from typing import Any


_CHECKBOX = re.compile(r"^- \[(?P<mark>[ xX])\]\s+(?P<item>.+?)\s*$")
_HEADING = re.compile(r"^(?P<level>#{1,6})\s+(?P<title>.+?)\s*$")


@dataclass(frozen=True)
class LedgerItem:
    source: str
    line: int
    section: str
    section_level: int
    item: str
    status: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_checklist(path: Path | str) -> list[LedgerItem]:
    source = Path(path)
    section = "UNSCOPED"
    section_level = 0
    items: list[LedgerItem] = []

    for line_no, raw in enumerate(
        source.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        heading = _HEADING.match(raw)
        if heading:
            section = heading.group("title").strip()
            section_level = len(heading.group("level"))
            continue

        checkbox = _CHECKBOX.match(raw)
        if not checkbox:
            continue

        status = (
            "DONE"
            if checkbox.group("mark").strip().lower() == "x"
            else "PENDING"
        )
        items.append(
            LedgerItem(
                source=str(source),
                line=line_no,
                section=section,
                section_level=section_level,
                item=checkbox.group("item").strip(),
                status=status,
            )
        )

    return items


def summarize_items(items: list[LedgerItem]) -> dict[str, Any]:
    done = sum(item.status == "DONE" for item in items)
    pending = sum(item.status == "PENDING" for item in items)
    sections: dict[str, dict[str, int]] = {}

    for item in items:
        row = sections.setdefault(
            item.section,
            {"total": 0, "done": 0, "pending": 0},
        )
        row["total"] += 1
        if item.status == "DONE":
            row["done"] += 1
        else:
            row["pending"] += 1

    return {
        "schema_version": "empire.master-execution-ledger.v1",
        "total": len(items),
        "done": done,
        "pending": pending,
        "sections": sections,
        "completion_rule": (
            "Checklist state only; live production completion still requires "
            "code + tests + live runtime + canonical data + Founder surface "
            "where applicable."
        ),
    }


def build_execution_ledger(
    path: Path | str,
) -> dict[str, Any]:
    items = parse_checklist(path)
    return {
        "summary": summarize_items(items),
        "items": [item.as_dict() for item in items],
        "authority": {
            "source_of_truth": "canonical_checklist",
            "runtime_reconciliation_required": True,
            "code_presence_is_not_completion": True,
            "execution_authority": "none",
        },
    }
