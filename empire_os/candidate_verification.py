"""Independent proposal-branch verifier for execution-plane builders.

Candidate code is verified in a disposable clone. The production working tree is
never checked out or mutated. Verification cannot merge or deploy.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
import shutil
import subprocess
from typing import Any
from uuid import uuid4


DEFAULT_BASE_BRANCH = "feature/revenue-intelligence-v2"


class CandidateVerificationError(RuntimeError):
    pass


def _run(
    argv: list[str],
    *,
    cwd: Path,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _path_allowed(path: str, scopes: tuple[str, ...]) -> bool:
    clean = str(path or "").strip().replace("\\", "/").lstrip("./")
    for scope in scopes:
        prefix = str(scope or "").strip().replace("\\", "/").lstrip("./").rstrip("/")
        if not prefix:
            continue
        if clean == prefix or clean.startswith(prefix + "/"):
            return True
    return False


def verify_candidate_branch(
    repo_root: str | Path,
    *,
    proposal_branch: str,
    allowed_paths: tuple[str, ...],
    pytest_targets: tuple[str, ...],
    base_branch: str = DEFAULT_BASE_BRANCH,
    work_root: str | Path = "/var/tmp/empire-candidate-verify",
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    if not proposal_branch.strip():
        raise CandidateVerificationError("proposal_branch required")
    if not allowed_paths:
        raise CandidateVerificationError("allowed_paths required")

    work_base = Path(work_root)
    work_base.mkdir(parents=True, exist_ok=True)
    clone = work_base / f"verify-{uuid4().hex}"
    shutil.rmtree(clone, ignore_errors=True)

    result: dict[str, Any] = {
        "schema_version": "empire.candidate-verification.v1",
        "proposal_branch": proposal_branch,
        "base_branch": base_branch,
        "changed_paths": [],
        "rejected_paths": [],
        "checks": [],
        "passed": False,
        "production_mutation": False,
        "production_merge": False,
        "production_deploy": False,
        "execution_authority": "none",
        "proposal_commit": None,
        "candidate_patch_path": None,
    }

    try:
        cloned = _run(
            ["git", "clone", "--no-hardlinks", str(root), str(clone)],
            cwd=work_base,
            timeout=180,
        )
        if cloned.returncode != 0:
            raise CandidateVerificationError("candidate verifier clone failed")

        remote_url = _run(
            ["git", "remote", "get-url", "origin"],
            cwd=root,
        ).stdout.strip()
        if not remote_url:
            raise CandidateVerificationError("origin remote unavailable")
        _run(["git", "remote", "set-url", "origin", remote_url], cwd=clone)

        fetched = _run(
            [
                "git",
                "fetch",
                "origin",
                base_branch,
                proposal_branch,
            ],
            cwd=clone,
            timeout=180,
        )
        if fetched.returncode != 0:
            raise CandidateVerificationError("candidate fetch failed")

        checkout = _run(
            ["git", "checkout", "--detach", f"origin/{proposal_branch}"],
            cwd=clone,
        )
        if checkout.returncode != 0:
            raise CandidateVerificationError("candidate checkout failed")

        diff = _run(
            [
                "git",
                "diff",
                "--name-only",
                f"origin/{base_branch}...HEAD",
            ],
            cwd=clone,
        )
        if diff.returncode != 0:
            raise CandidateVerificationError("candidate diff failed")
        changed = sorted(
            dict.fromkeys(
                line.strip()
                for line in diff.stdout.splitlines()
                if line.strip()
            )
        )
        rejected = [
            path for path in changed if not _path_allowed(path, allowed_paths)
        ]
        result["changed_paths"] = changed
        result["rejected_paths"] = rejected
        if rejected:
            result["failure_reason"] = "path_policy_failed"
            return result
        if not changed:
            result["failure_reason"] = "no_candidate_changes"
            return result

        tests = tuple(dict.fromkeys(pytest_targets))
        if tests:
            check = subprocess.run(
                [
                    str(root / ".venv/bin/python"),
                    "-m",
                    "pytest",
                    "-q",
                    *tests,
                ],
                cwd=str(clone),
                env={
                    "PATH": "/usr/bin:/bin",
                    "PYTHONPATH": str(clone),
                    "HOME": "/var/tmp",
                },
                capture_output=True,
                text=True,
                timeout=900,
                check=False,
            )
            result["checks"].append({
                "kind": "pytest",
                "targets": list(tests),
                "returncode": check.returncode,
                "output_tail": (
                    (check.stdout or "") + "\n" + (check.stderr or "")
                )[-5000:],
            })

        result["passed"] = all(
            row.get("returncode") == 0
            for row in result["checks"]
        )
        if not result["checks"]:
            result["passed"] = True

        if result["passed"]:
            commit = _run(
                ["git", "rev-parse", "HEAD"],
                cwd=clone,
            ).stdout.strip()
            if not commit:
                raise CandidateVerificationError(
                    "candidate commit unavailable"
                )
            patch = _run(
                [
                    "git",
                    "diff",
                    "--binary",
                    f"origin/{base_branch}...HEAD",
                ],
                cwd=clone,
                timeout=180,
            )
            if patch.returncode != 0 or not patch.stdout.strip():
                raise CandidateVerificationError(
                    "candidate patch generation failed"
                )
            safe_branch = re.sub(
                r"[^A-Za-z0-9._-]+",
                "_",
                proposal_branch,
            )[:100].strip("_") or "candidate"
            artifact_dir = (
                root
                / "runtime/execution_plane/candidate_patches"
            )
            artifact_dir.mkdir(parents=True, exist_ok=True)
            artifact = (
                artifact_dir
                / f"{safe_branch}-{commit[:12]}.patch"
            )
            tmp = artifact.with_suffix(".patch.tmp")
            tmp.write_text(patch.stdout, encoding="utf-8")
            os.chmod(tmp, 0o600)
            tmp.replace(artifact)
            os.chmod(artifact, 0o600)
            result["proposal_commit"] = commit
            result["candidate_patch_path"] = str(
                artifact.relative_to(root)
            )
        return result
    finally:
        shutil.rmtree(clone, ignore_errors=True)
