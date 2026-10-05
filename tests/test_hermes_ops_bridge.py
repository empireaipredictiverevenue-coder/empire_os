import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from empire_os.hermes_control import (
    HermesControlError,
    HermesJob,
    _encrypt_ops_result,
    _execute_ops_request,
)


def ops_job(**overrides):
    payload = {
        "schema_version": "empire.hermes.control_job.v1",
        "job_id": "ops-bridge-test",
        "prompt": "Deterministic Ops bridge request.",
        "kind": "ops_request",
        "authority": "observe",
        "base_branch": "agent/data-cloud-wave4",
        "allowed_paths": [],
        "lease_resources": [],
        "operation": "repo_status",
        "arguments": {},
        "result_certificate_pem": (
            "-----BEGIN CERTIFICATE-----\n"
            "placeholder\n"
            "-----END CERTIFICATE-----\n"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    payload.update(overrides)
    return payload


def test_ops_request_schema_accepts_bounded_read():
    job = HermesJob.from_mapping(ops_job())
    assert job.kind == "ops_request"
    assert job.authority == "observe"


def test_ops_request_rejects_arbitrary_operation():
    with pytest.raises(HermesControlError, match="outside the allowlist"):
        HermesJob.from_mapping(
            ops_job(operation="run_shell")
        )


def test_ops_write_requires_internal_write_authority():
    with pytest.raises(
        HermesControlError,
        match="requires internal_write",
    ):
        HermesJob.from_mapping(
            ops_job(
                operation="file_write",
                arguments={
                    "path": "empire_os/example.py",
                    "content": "x = 1\n",
                },
            )
        )


def test_ops_file_write_is_bound_to_job_allowed_paths():
    raw = ops_job(
        authority="internal_write",
        allowed_paths=["empire_os/safe.py"],
        lease_resources=["path:empire_os/safe.py"],
        operation="file_write",
        arguments={
            "path": "deploy/systemd/unsafe.service",
            "content": "nope\n",
        },
    )
    job = HermesJob.from_mapping(raw)
    with pytest.raises(HermesControlError, match="outside the job path policy"):
        _execute_ops_request(
            raw,
            authority=job.authority,
            repo_root=Path("/srv/empire_os"),
            allowed_paths=job.allowed_paths,
        )


def test_ops_result_is_encrypted_with_request_certificate(tmp_path):
    key = tmp_path / "key.pem"
    cert = tmp_path / "cert.pem"
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-nodes", "-subj", "/CN=Empire Ops Test",
            "-keyout", str(key), "-out", str(cert),
            "-days", "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    encrypted = _encrypt_ops_result(
        {
            "ok": True,
            "result": {"stdout": "private-live-state"},
        },
        certificate_pem=cert.read_text(),
        runtime_root=tmp_path,
        job_id="ops-bridge-test",
    )
    assert "BEGIN CMS" in encrypted
    assert "private-live-state" not in encrypted

    encrypted_path = tmp_path / "encrypted.pem"
    encrypted_path.write_text(encrypted)
    clear_path = tmp_path / "clear.json"
    subprocess.run(
        [
            "openssl", "cms", "-decrypt",
            "-inform", "PEM",
            "-in", str(encrypted_path),
            "-recip", str(cert),
            "-inkey", str(key),
            "-out", str(clear_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(clear_path.read_text())
    assert payload["result"]["stdout"] == "private-live-state"
