"""GitHub-backed transport bridge for Empire Ops.

The public EmpireOS repository is used only as an authenticated write transport.
Operational results are never published in plaintext: each request supplies an
ephemeral X.509 certificate and the bridge encrypts the result with OpenSSL CMS.

No arbitrary shell, DB mutation, outbound send, payment, or authority expansion
is available through this bridge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from empire_os.founder_directives import FounderDirectiveStore
from empire_os.ops_core import (
    audit,
    git_diff,
    git_log,
    git_status,
    read_repo_file,
    run_command,
    safe_repo_path,
    service_status,
    write_repo_file,
)

REPO = Path("/srv/empire_os").resolve()
RUNTIME = REPO / "runtime" / "ops_bridge"
RESULTS = RUNTIME / "results"
CONTROL_REF = os.getenv(
    "EMPIRE_OPS_BRIDGE_CONTROL_REF",
    "refs/heads/empire-ops-bridge",
).strip()
REMOTE_REF = "refs/remotes/origin/empire-ops-bridge"
REQUEST_PREFIX = "bridge/requests/"
REQUEST_ID_RE = re.compile(r"^[0-9a-f]{32}$")
MAX_REQUEST_BYTES = 120_000
MAX_RESULT_BYTES = 100_000

_ALLOWED_CHECKS = {"git_diff_check", "pytest_file", "python_compile"}
_ALLOWED_OPERATIONS = {
    "repo_status",
    "repo_log",
    "repo_diff",
    "file_read",
    "file_write",
    "run_check",
    "service_status",
    "founder_directive_ingest",
}


class BridgePolicyError(ValueError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _run_git(args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _fetch_control_ref() -> None:
    result = _run_git(
        ["fetch", "--quiet", "origin", f"+{CONTROL_REF}:{REMOTE_REF}"],
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "git fetch failed")[-2000:])


def _request_paths() -> list[str]:
    result = _run_git(["ls-tree", "-r", "--name-only", REMOTE_REF, "--", REQUEST_PREFIX])
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "git ls-tree failed")[-2000:])
    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().startswith(REQUEST_PREFIX)
        and line.strip().endswith(".json")
    ]


def _read_request(path: str) -> dict[str, Any]:
    result = _run_git(["show", f"{REMOTE_REF}:{path}"])
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "git show failed")[-2000:])
    raw = result.stdout.encode("utf-8")
    if len(raw) > MAX_REQUEST_BYTES:
        raise BridgePolicyError("request too large")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise BridgePolicyError("request must be an object")
    return payload


def _parse_expiry(value: Any) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise BridgePolicyError("expires_at required")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BridgePolicyError("invalid expires_at") from exc
    if parsed.tzinfo is None:
        raise BridgePolicyError("expires_at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def validate_request(payload: dict[str, Any], *, path: str) -> dict[str, Any]:
    if payload.get("schema_version") != "empire.ops_bridge.request.v1":
        raise BridgePolicyError("unsupported request schema")
    request_id = str(payload.get("request_id") or "").strip().lower()
    if not REQUEST_ID_RE.fullmatch(request_id):
        raise BridgePolicyError("invalid request_id")
    if path != f"{REQUEST_PREFIX}{request_id}.json":
        raise BridgePolicyError("request id/path mismatch")
    operation = str(payload.get("operation") or "").strip()
    if operation not in _ALLOWED_OPERATIONS:
        raise BridgePolicyError("operation not allowlisted")
    expires_at = _parse_expiry(payload.get("expires_at"))
    now = _utc_now()
    if expires_at <= now:
        raise BridgePolicyError("request expired")
    if expires_at > now + timedelta(minutes=30):
        raise BridgePolicyError("request expiry too far in future")
    cert = str(payload.get("result_certificate_pem") or "")
    if (
        "-----BEGIN CERTIFICATE-----" not in cert
        or "-----END CERTIFICATE-----" not in cert
        or len(cert) > 12_000
    ):
        raise BridgePolicyError("valid result certificate required")
    args = payload.get("arguments") or {}
    if not isinstance(args, dict):
        raise BridgePolicyError("arguments must be an object")
    return {
        "request_id": request_id,
        "operation": operation,
        "arguments": args,
        "result_certificate_pem": cert,
        "requested_by": str(payload.get("requested_by") or "github-bridge")[:120],
    }


def _file_sha256(path: str) -> str | None:
    target = safe_repo_path(path)
    if not target.exists():
        return None
    if not target.is_file():
        raise BridgePolicyError("target is not a file")
    return hashlib.sha256(target.read_bytes()).hexdigest()


def _execute(operation: str, args: dict[str, Any]) -> dict[str, Any]:
    if operation == "repo_status":
        return git_status()
    if operation == "repo_log":
        return git_log(int(args.get("limit", 8)))
    if operation == "repo_diff":
        return git_diff(
            str(args.get("path") or "") or None,
            staged=bool(args.get("staged", False)),
        )
    if operation == "file_read":
        return read_repo_file(
            str(args.get("path") or ""),
            offset=int(args.get("offset", 0)),
            limit=min(int(args.get("limit", 40000)), 80000),
        )
    if operation == "file_write":
        path = str(args.get("path") or "")
        expected = args.get("expected_sha256")
        current = _file_sha256(path)
        if expected is not None and str(expected) != str(current):
            raise BridgePolicyError("file sha256 mismatch")
        content = str(args.get("content") or "")
        if len(content.encode("utf-8")) > 100_000:
            raise BridgePolicyError("file content too large")
        result = write_repo_file(
            path,
            content,
            append=bool(args.get("append", False)),
        )
        result["sha256"] = _file_sha256(path)
        return result
    if operation == "run_check":
        check = str(args.get("check") or "")
        target = str(args.get("target") or "")
        if check not in _ALLOWED_CHECKS:
            raise BridgePolicyError("check not allowlisted")
        if check == "git_diff_check":
            return run_command(["git", "diff", "--check"])
        safe_repo_path(target)
        if check == "pytest_file":
            return run_command(
                ["/srv/empire_os/.venv/bin/python", "-m", "pytest", "-q", target],
                timeout=120,
            )
        return run_command(
            ["/srv/empire_os/.venv/bin/python", "-m", "py_compile", target],
            timeout=30,
        )
    if operation == "service_status":
        return service_status(str(args.get("unit") or ""))
    if operation == "founder_directive_ingest":
        text = str(args.get("text") or "").strip()
        title = str(args.get("title") or "").strip()
        priority = max(0, min(int(args.get("priority", 90)), 100))
        directive, created = FounderDirectiveStore(REPO).ingest(
            text,
            source="github_ops_bridge",
            title=title or None,
            priority=priority,
            metadata={"ingested_via": "empire_ops_github_bridge"},
        )
        return {
            "ok": True,
            "created": created,
            "directive": directive.as_dict(),
            "planning_automatic": True,
            "production_execution_automatic": False,
        }
    raise BridgePolicyError("operation not implemented")


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            clean = str(key).lower()
            if any(token in clean for token in ("secret", "token", "password", "credential")):
                out[key] = "[REDACTED]"
            else:
                out[key] = _sanitize(item)
        return out
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return value[-20000:]
    return value


def _encrypt_result(request_id: str, payload: dict[str, Any], certificate_pem: str) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    clear = json.dumps(_sanitize(payload), sort_keys=True).encode("utf-8")
    if len(clear) > MAX_RESULT_BYTES:
        clear = json.dumps({
            "request_id": request_id,
            "ok": False,
            "error": "result_too_large",
        }).encode("utf-8")
    target = RESULTS / f"{request_id}.pem"
    with tempfile.TemporaryDirectory(prefix="empire-ops-bridge-") as td:
        root = Path(td)
        clear_path = root / "result.json"
        cert_path = root / "recipient.pem"
        out_path = root / "result.pem"
        clear_path.write_bytes(clear)
        cert_path.write_text(certificate_pem, encoding="utf-8")
        completed = subprocess.run(
            [
                "openssl", "cms", "-encrypt",
                "-aes-256-cbc", "-binary",
                "-outform", "PEM",
                "-in", str(clear_path),
                "-out", str(out_path),
                str(cert_path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError("result encryption failed")
        tmp = target.with_suffix(".pem.tmp")
        tmp.write_bytes(out_path.read_bytes())
        os.chmod(tmp, 0o640)
        tmp.replace(target)
        os.chmod(target, 0o640)
    return target


def process_once(*, limit: int = 10) -> dict[str, Any]:
    _fetch_control_ref()
    RESULTS.mkdir(parents=True, exist_ok=True)
    processed = 0
    skipped = 0
    errors = 0
    for path in _request_paths():
        if processed >= max(1, min(int(limit), 25)):
            break
        request_id = Path(path).stem.lower()
        if (RESULTS / f"{request_id}.pem").is_file():
            skipped += 1
            continue
        try:
            request = validate_request(_read_request(path), path=path)
            rid = request["request_id"]
            result = _execute(request["operation"], request["arguments"])
            envelope = {
                "schema_version": "empire.ops_bridge.result.v1",
                "request_id": rid,
                "operation": request["operation"],
                "ok": True,
                "completed_at": _utc_now().isoformat(),
                "result": result,
            }
            _encrypt_result(rid, envelope, request["result_certificate_pem"])
            audit(
                "ops_github_bridge",
                request_id=rid,
                arguments={"operation": request["operation"]},
                outcome="ok",
            )
            processed += 1
        except Exception as exc:
            errors += 1
            try:
                payload = _read_request(path)
                cert = str(payload.get("result_certificate_pem") or "")
                if cert and REQUEST_ID_RE.fullmatch(request_id):
                    _encrypt_result(
                        request_id,
                        {
                            "schema_version": "empire.ops_bridge.result.v1",
                            "request_id": request_id,
                            "ok": False,
                            "completed_at": _utc_now().isoformat(),
                            "error": type(exc).__name__,
                            "message": str(exc)[:1000],
                        },
                        cert,
                    )
            except Exception:
                pass
            audit(
                "ops_github_bridge",
                request_id=request_id if REQUEST_ID_RE.fullmatch(request_id) else "invalid",
                arguments={"path": path},
                outcome=f"error:{type(exc).__name__}",
            )
    return {
        "ok": errors == 0,
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "mode": "BOUNDED_ENGINEERING",
        "general_shell": False,
        "production_authority_expanded": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(process_once(limit=args.limit), sort_keys=True))


if __name__ == "__main__":
    main()
