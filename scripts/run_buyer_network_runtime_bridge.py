from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from empire_os.buyer_network_integration import (
    BuyerNetworkIntegration,
    integration_status,
)


ROOT = Path("/srv/empire_os")
RUNTIME = ROOT / "runtime"
OUTPUT_DIR = RUNTIME / "buyer_network_intelligence"
OUTPUT = OUTPUT_DIR / "latest.json"

SCOUT = ROOT / "scripts" / "run_buyer_acquisition_scout.py"
PYTHON = ROOT / ".venv" / "bin" / "python"


DOMAIN_RE = re.compile(
    r"^(?:https?://)?"
    r"(?:www\.)?"
    r"([a-z0-9][a-z0-9.-]+\.[a-z]{2,})"
    r"(?:[/:].*)?$",
    re.I,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(".tmp")

    tmp.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    tmp.replace(path)


def buyer_runtime_files() -> list[Path]:
    if not RUNTIME.exists():
        return []

    tokens = (
        "buyer",
        "lead_smart",
        "opportunity",
        "revenue",
    )

    files: list[Path] = []

    for path in RUNTIME.rglob("*.json"):
        low = str(path).lower()

        if "buyer_network_intelligence" in low:
            continue

        if any(token in low for token in tokens):
            files.append(path)

    return sorted(files)


def walk_values(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from walk_values(item)

    elif isinstance(value, list):
        for item in value:
            yield from walk_values(item)


def normalise_domain(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    text = value.strip().lower()

    match = DOMAIN_RE.match(text)

    if not match:
        return None

    domain = match.group(1).rstrip(".")

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def extract_observed_domains(payload: Any) -> set[str]:
    keys = {
        "domain",
        "canonical_domain",
        "company_domain",
        "buyer_domain",
        "website",
        "website_url",
        "url",
    }

    domains: set[str] = set()

    for key, value in walk_values(payload):
        if str(key).lower() not in keys:
            continue

        domain = normalise_domain(value)

        if domain:
            domains.add(domain)

    return domains


def load_runtime_truth() -> tuple[list[dict[str, Any]], set[str]]:
    artifacts: list[dict[str, Any]] = []
    domains: set[str] = set()

    for path in buyer_runtime_files():
        try:
            payload = json.loads(
                path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            )

        except Exception as exc:
            artifacts.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "status": "INVALID_JSON",
                    "error": type(exc).__name__,
                }
            )
            continue

        observed = extract_observed_domains(payload)
        domains.update(observed)

        artifacts.append(
            {
                "path": str(path.relative_to(ROOT)),
                "status": "READ",
                "observed_domains": len(observed),
                "mtime": datetime.fromtimestamp(
                    path.stat().st_mtime,
                    tz=timezone.utc,
                ).isoformat(),
            }
        )

    return artifacts, domains


def safe_scout_command() -> tuple[list[str] | None, str]:
    if not SCOUT.exists():
        return None, "scout_script_missing"

    env = os.environ.copy()

    env.update(
        {
            "EMPIRE_MODE": "OBSERVE",
            "EMPIRE_EXECUTION_AUTHORITY": "OBSERVE",
            "OUTBOUND_ENABLED": "0",
            "EMPIRE_OUTBOUND_ENABLED": "0",
            "LIVE_OUTBOUND": "0",
        }
    )

    probe = subprocess.run(
        [str(PYTHON), str(SCOUT), "--help"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )

    help_text = (
        (probe.stdout or "")
        + "\n"
        + (probe.stderr or "")
    ).lower()

    safe_flags: list[str] = []

    if "--observe" in help_text:
        safe_flags.append("--observe")

    elif "--dry-run" in help_text:
        safe_flags.append("--dry-run")

    elif "--preview" in help_text:
        safe_flags.append("--preview")

    else:
        return None, "no_explicit_safe_cli_mode"

    if "--no-send" in help_text:
        safe_flags.append("--no-send")

    if "--no-outbound" in help_text:
        safe_flags.append("--no-outbound")

    if "--no-persist" in help_text:
        safe_flags.append("--no-persist")

    return [
        str(PYTHON),
        str(SCOUT),
        *safe_flags,
    ], "safe_mode_detected"


def run_existing_scout_observe() -> dict[str, Any]:
    command, reason = safe_scout_command()

    if command is None:
        return {
            "attempted": False,
            "status": "SKIPPED_FAIL_CLOSED",
            "reason": reason,
        }

    env = os.environ.copy()

    env.update(
        {
            "EMPIRE_MODE": "OBSERVE",
            "EMPIRE_EXECUTION_AUTHORITY": "OBSERVE",
            "OUTBOUND_ENABLED": "0",
            "EMPIRE_OUTBOUND_ENABLED": "0",
            "LIVE_OUTBOUND": "0",
        }
    )

    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )

    return {
        "attempted": True,
        "status": (
            "PASS"
            if completed.returncode == 0
            else "FAIL"
        ),
        "returncode": completed.returncode,
        "command": command,
        "stdout_tail": (
            completed.stdout or ""
        )[-4000:],
        "stderr_tail": (
            completed.stderr or ""
        )[-4000:],
    }


def build_snapshot(
    *,
    run_scout: bool,
) -> dict[str, Any]:

    status = integration_status()

    scout = (
        run_existing_scout_observe()
        if run_scout
        else {
            "attempted": False,
            "status": "SNAPSHOT_ONLY",
        }
    )

    artifacts, domains = load_runtime_truth()

    snapshot = {
        "schema_version": "buyer-network-runtime-v1",
        "generated_at": now_iso(),

        "authority": "OBSERVE",

        "integration": {
            "ready": status.ready,
            "loaded_modules": list(
                status.loaded_modules
            ),
            "missing_modules": list(
                status.missing_modules
            ),
        },

        "existing_buyer_scout": scout,

        "runtime_truth": {
            "artifact_count": len(artifacts),
            "candidate_domain_count": len(domains),
            "candidate_domains": sorted(domains),
            "artifacts": artifacts,
        },

        "governance": {
            "outbound_authority": False,
            "traffic_activation_authority": False,
            "commercial_terms_authority": False,
            "funds_authority": False,
        },
    }

    atomic_write_json(
        OUTPUT,
        snapshot,
    )

    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--snapshot-only",
        action="store_true",
    )

    parser.add_argument(
        "--auto-observe",
        action="store_true",
    )

    args = parser.parse_args()

    run_scout = bool(
        args.auto_observe
        and not args.snapshot_only
    )

    snapshot = build_snapshot(
        run_scout=run_scout
    )

    print(
        json.dumps(
            {
                "status": "PASS",
                "authority": snapshot["authority"],
                "integration_ready":
                    snapshot["integration"]["ready"],
                "scout":
                    snapshot["existing_buyer_scout"],
                "candidate_domain_count":
                    snapshot["runtime_truth"][
                        "candidate_domain_count"
                    ],
                "output": str(OUTPUT),
            },
            indent=2,
            default=str,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
