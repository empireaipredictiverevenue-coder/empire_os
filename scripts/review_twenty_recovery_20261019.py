"""Twenty recovery checkpoint. Read-only server and historic Git state."""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path
from empire_os.twenty_recovery_boundary import inspect_twenty

DEFAULT_ROOT = Path("/srv/empire_os")
DEFAULT_PLUGIN = Path("/home/ubuntu/.hermes/hermes-agent/plugin-catalog/twenty-crm.yaml")


def git_marker(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", "42c0f6cc^{commit}"],
        check=False, capture_output=True, timeout=6,
    )
    return result.returncode == 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only", action="store_true", required=True)
    p.add_argument("--repo-root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--plugin", type=Path, default=DEFAULT_PLUGIN)
    args = p.parse_args(argv)
    try:
        result = inspect_twenty(args.repo_root, plugin_path=args.plugin,
                                commit_probe=git_marker)
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired) as err:
        result = {"schema_version": "empire.twenty_crm_recovery.v1",
                  "state": "HOLD", "reason_class": type(err).__name__,
                  "canonical_empiredb_writes": False,
                  "execution_authority": "none"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("mode") == "READ_ONLY_ORIGINAL_INSTANCE_RECOVERY" else 2

if __name__ == "__main__":
    raise SystemExit(main())
