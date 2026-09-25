from pathlib import Path

import pytest

from empire_os.pi_sandbox_runner import (
    PiSandboxJob,
    build_pi_systemd_command,
)


def test_pi_job_rejects_external_or_unbounded_shape():
    with pytest.raises(Exception):
        PiSandboxJob(
            job_id="bad/id",
            prompt="x",
            allowed_paths=("empire_os/",),
        ).validate()


def test_pi_systemd_command_hides_production_and_allows_localhost_only(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    (clone / ".empire_pi").mkdir()

    argv = build_pi_systemd_command(
        clone=clone,
        prompt="Implement a bounded test.",
        model_id="qwen-test",
        max_runtime_seconds=300,
        system_prompt="Empire safe coding policy.",
        pi_bin=Path("/opt/empire/pi-agent/bin/pi"),
    )
    joined = "\n".join(argv)
    assert "ProtectSystem=strict" in joined
    assert "ProtectHome=yes" in joined
    assert "IPAddressDeny=any" in joined
    assert "IPAddressAllow=localhost" in joined
    assert "InaccessiblePaths=/srv/empire_os" in joined
    assert "InaccessiblePaths=/etc/empire_os" in joined
    assert "InaccessiblePaths=/home/ubuntu/.ssh" in joined
    assert "ReadWritePaths=" in joined
    assert "--no-session" in argv
    assert "PI_TELEMETRY=0" in argv
    assert "Empire safe coding policy." in argv


def test_pi_job_has_no_commercial_authority_fields():
    job = PiSandboxJob(
        job_id="safe-1",
        prompt="Add tests.",
        allowed_paths=("tests/",),
    )
    job.validate()
    assert not hasattr(job, "outbound_authority")
    assert not hasattr(job, "payment_authority")
