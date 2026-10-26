#!/usr/bin/env python3
"""Materialize private microsite previews only; never publishes or sends."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from empire_os.predictive_microsite_factory import build_candidate, review_portfolio


def run(source: Path, out_dir: Path) -> dict:
    raw = json.loads(source.read_text(encoding="utf-8"))
    specs = raw.get("candidates") if isinstance(raw, dict) and "candidates" in raw else [raw]
    if not isinstance(specs, list) or not 1 <= len(specs) <= 25:
        raise ValueError("input must contain 1-25 candidate proposals")
    if not all(isinstance(spec, dict) for spec in specs):
        raise ValueError("each candidate must be an object")
    resolved = out_dir.expanduser().resolve()
    # Write stage outputs outside production and release directories, never serve them.
    protected = (Path("/srv/empire_os"), Path("/var/www"), Path("/srv/empire_public"))
    if any(resolved == p or p in resolved.parents for p in protected):
        raise ValueError("refusing to write draft previews inside live runtime or site directories")
    reviews = review_portfolio(specs)
    resolved.mkdir(parents=True, exist_ok=True)
    for spec, packet in zip(specs, reviews):
        _, html = build_candidate(spec)
        ident = packet["id"]
        (resolved / f"{ident}.preview.html").write_text(html, encoding="utf-8")
        brief = [
            f"Candidate: {ident}",
            f"Territory: {packet['market']['area']}",
            f"Keyword: {packet['keyword']['record']['keyword']}",
            f"Audience: {packet['audience']}",
            f"Offer: {packet['offer']}",
            f"SlopMonster score: {packet['copy_audit']['score']}/5",
            f"Copy findings: {json.dumps(packet['copy_audit']['categories'], ensure_ascii=False)}",
            "Rewrite instruction: preserve the location, every source fact, technical limitations,",
            "source references, brand tone and the intent. Remove unsupported claims and vague phrasing.",
            "Never claim verified buyers, lead volume, calls, financial outcomes, or service capacity.",
            "Visual direction: accessible responsive premium dark-navy pages with gold and electric-blue accents.",
            "Use real browser screenshot testing before any owner-approved release.",
            "No external model invocation was performed by this script.",
        ]
        (resolved / f"{ident}.copy-design-brief.txt").write_text(
            "\n".join(brief) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "empire.microsite_factory_draft_batch.v1",
        "stage_only": True, "published": False, "execution_authority": "none",
        "candidates_reviewed": len(reviews),
        "held": sum(p["status"] == "HOLD_EVIDENCE" for p in reviews),
        "draft_review": sum(p["status"] == "DRAFT_REVIEW" for p in reviews),
        "previews": [p["id"] + ".preview.html" for p in reviews],
        "packets": reviews,
    }
    (resolved / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.input, args.output_dir)
        print(json.dumps({key: result[key] for key in
              ("schema_version", "candidates_reviewed", "held", "draft_review",
               "stage_only", "published", "previews")}, sort_keys=True))
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"microsite preview error: {exc}", file=sys.stderr)
        sys.exit(2)
