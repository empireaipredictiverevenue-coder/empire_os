#!/usr/bin/env python3
"""Fail-closed, READ-ONLY compatibility inventory for external agent frameworks.

No third-party application code or EmpireOS worker code is imported/executed.
No DB, task queue, credentials, HTTP, MCP, systemd or deployment actions.
Only local git metadata and source-file presence/anchors are observed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceSpec:
    slug: str
    url: str
    pinned_head: str
    licence: str
    anchors: tuple[str, ...]
    files: tuple[str, ...]
    identity_confirmed: bool = True


SOURCES = (
    SourceSpec("paperclip", "https://github.com/paperclipai/paperclip",
        "92cfd701c39bb1ea394a796023481a21decb2532", "MIT",
        ("org chart", "budgets", "heartbeats", "approval"),
        ("server/src/lib/approval-records.ts", "README.md")),
    SourceSpec("orcha", "https://github.com/open-orcha/orcha",
        "e5f9add77ebc6b9e1ecfd8adad04f3c89e42595f", "MIT",
        ("needs_verification", "rehydrate", "notifier"),
        ("orcha-cli/orcha_cli", "README.md")),
    SourceSpec("nora", "https://github.com/solomon2773/nora",
        "ae7e46e4aff429f88016cd7348eb514cb6d89bd4", "Apache-2.0",
        ("openclaw", "hermes", "budgets", "monitoring"),
        ("backend-api/agentBudgets.ts", "backend-api/fleetStatus.ts", "README.md")),
    SourceSpec("head-of-ai-template", "https://github.com/doneyli/head-of-ai-template",
        "c5f7eb6ed38396209260636e71af03e742175122", "MIT",
        ("DICE", "Scope enforcement", "dispatch"),
        ("policy.yaml", "hooks/enforce-agent-scope.sh", "README.md"),
        identity_confirmed=False),
    SourceSpec("template-agent", "https://github.com/redhat-data-and-ai/template-agent",
        "43554147435141948ed2385d8ce054a6842cecdd", "Apache-2.0",
        ("MCP", "PostgreSQL", "Langfuse"),
        ("config/agent/PROMPT.md", "README.md"),
        identity_confirmed=False),
)

LOCAL_CONTROLS = {
    "durable_deduplicated_queue": "empire_os/department_work_queue.py",
    "budget_ledger": "empire_os/department_budget_ledger.py",
    "governed_worker": "empire_os/department_worker.py",
    "department_cycle": "empire_os/department_cycle.py",
    "skillforge_digest_approval": "empire_os/skillforge.py",
    "execution_plane": "empire_os/agent_execution_plane.py",
    "founder_console": "apps/search-command-centre/src/app/founder/page.tsx",
}


def source_inventory(upstream_root: Path, spec: SourceSpec) -> dict:
    directory = upstream_root / spec.slug
    result = {
        "name": spec.slug,
        "source": spec.url,
        "pin": spec.pinned_head,
        "licence_expected": spec.licence,
        "licence_file_anchor_present": False,
        "user_identity_confirmed": spec.identity_confirmed,
        "clone_present": False,
        "pin_verified": False,
        "file_presence_only": False,
        "readme_anchors_only": False,
        "source_executed": False,
        "ready_to_install": False,
        "issues": [],
    }
    if not directory.is_dir() or not (directory / ".git").exists():
        result["issues"].append("clone_missing")
        return result
    result["clone_present"] = True
    try:
        actual = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=8,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        result["issues"].append("git_metadata_unavailable")
        return result
    result["observed_head"] = actual
    result["pin_verified"] = actual == spec.pinned_head
    if not result["pin_verified"]:
        result["issues"].append("upstream_pin_mismatch")
        return result
    try:
        licence_path = directory / "LICENSE"
        licence_text = licence_path.read_text(encoding="utf-8")[:1000]
        needle = "MIT License" if spec.licence == "MIT" else "Apache License"
        result["licence_file_anchor_present"] = needle in licence_text
    except OSError:
        pass
    if not result["licence_file_anchor_present"]:
        result["issues"].append("licence_file_anchor_unverified")
    # Existence and static README text are evidence of source presence only.
    # They do NOT establish safe runtime behavior, proper auth, or test success.
    result["file_presence_only"] = all(
        (directory / fragment).exists() and
        (directory / fragment).resolve().is_relative_to(directory.resolve())
        for fragment in spec.files
    )
    if not result["file_presence_only"]:
        result["issues"].append("expected_file_missing_or_escaped")
    try:
        readme = (directory / "README.md").read_text(encoding="utf-8").lower()
    except OSError:
        readme = ""
    result["readme_anchors_only"] = all(
        word.lower() in readme for word in spec.anchors
    )
    if not result["readme_anchors_only"]:
        result["issues"].append("documented_feature_anchor_missing")
    if not spec.identity_confirmed:
        result["issues"].append("ambiguous_ai_template_identity")
    return result


def audit(empire_root: Path, upstream_root: Path) -> dict:
    existing = {
        name: (empire_root / filename).is_file()
        and (empire_root / filename).resolve().is_relative_to(empire_root.resolve())
        for name, filename in LOCAL_CONTROLS.items()
    }
    sources = [source_inventory(upstream_root, spec) for spec in SOURCES]
    return {
        "mode": "OBSERVE",
        "execution_authority": "none",
        "third_party_code_executed": False,
        "production_services_changed": False,
        "production_queue_or_db_modified": False,
        "external_software_installed": False,
        "upstream_clones_are_review_material_not_runtime_dependencies": True,
        "upstreams": sources,
        "existing_empire_controls": existing,
        "all_expected_local_controls_present": all(existing.values()),
        "all_source_pins_verified": all(row["pin_verified"] for row in sources),
        "release_allowed": False,
        "next_step": "independent offline holdout and security evaluation; no production wiring",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--empire-root", type=Path, required=True)
    parser.add_argument("--upstream-root", type=Path, required=True)
    args = parser.parse_args()
    output = audit(args.empire_root, args.upstream_root)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if output["all_source_pins_verified"] and output["all_expected_local_controls_present"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
