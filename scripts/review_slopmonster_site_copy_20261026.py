#!/usr/bin/env python3
"""Read-only SlopMonster audit of existing built EmpireOS pages. Never edits pages."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from empire_os.predictive_microsite_factory import review_copy
from empire_os.third_party.slopmonster.deslop import markdown_prose, visible_text

EXTENSIONS = {".html", ".htm", ".md"}


def inspect_page(path: Path) -> dict:
    if path.suffix.lower() not in EXTENSIONS:
        raise ValueError("Only HTML or Markdown input is supported")
    raw = path.read_text(encoding="utf-8")
    text = markdown_prose(raw) if path.suffix.lower() == ".md" else visible_text(raw)
    if not text:
        return {"path": str(path), "status": "EMPTY_VISIBLE_CONTENT",
                "copy_audit": None, "html_checks": None}
    html_checks = None
    if path.suffix.lower() in {".htm", ".html"}:
        lower = raw.lower()
        html_checks = {
            "viewport_meta_detected": bool(re.search(r'<meta[^>]+name=[\'\"]viewport', lower)),
            "h1_count_in_source": len(re.findall(r"<h1\b", lower)),
            "main_landmark_in_source": bool(re.search(r"<main\b", lower)),
            "canonical_in_source": bool(re.search(r"<link[^>]+rel=[\'\"]canonical", lower)),
            "mobile_visual_test_performed": False,
            "javascript_rendered_content_checked": False,
        }
    return {
        "path": str(path), "status": "AUDITED",
        "words": len(text.split()), "copy_audit": review_copy(text),
        "html_checks": html_checks,
    }


def run(paths: list[Path], max_files: int) -> dict:
    if not 1 <= max_files <= 200:
        raise ValueError("max_files must be between 1 and 200")
    expanded: list[Path] = []
    for path in paths:
        if path.is_dir():
            expanded.extend(p for p in path.rglob("*")
                            if p.is_file() and p.suffix.lower() in EXTENSIONS)
        elif path.is_file():
            expanded.append(path)
        else:
            raise ValueError(f"input missing: {path}")
    expanded = sorted(set(expanded))
    if len(expanded) > max_files:
        raise ValueError(f"{len(expanded)} pages exceeds --max-files {max_files}")
    rows = [inspect_page(path) for path in expanded]
    return {
        "schema_version": "empire.slopmonster_website_audit.v1",
        "mode": "OBSERVE", "pages_checked": len(rows),
        "flagged_pages": sum(bool(x["copy_audit"] and x["copy_audit"]["review_required"]) for x in rows),
        "audits": rows, "changed_files": 0, "published": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--max-files", type=int, default=100)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        result = run(args.paths, args.max_files)
        rendered = json.dumps(result, ensure_ascii=False, indent=2)
        if args.report:
            out = args.report.expanduser().resolve()
            protected = [Path("/srv/empire_os"), Path("/var/www")]
            if any(out == p or p in out.parents for p in protected):
                raise ValueError("report cannot overwrite production paths")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(rendered + "\n", encoding="utf-8")
        print(json.dumps({
            "pages_checked": result["pages_checked"],
            "flagged_pages": result["flagged_pages"],
            "changed_files": 0, "published": False,
        }))
    except (OSError, ValueError) as exc:
        print(f"site copy audit error: {exc}", file=sys.stderr)
        sys.exit(2)
