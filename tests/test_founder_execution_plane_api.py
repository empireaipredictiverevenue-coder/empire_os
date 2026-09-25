from pathlib import Path

from empire_os.founder_execution_plane_api import (
    build_execution_plane_status,
)


def test_founder_execution_plane_is_read_only(tmp_path):
    payload = build_execution_plane_status(
        lease_root=tmp_path / "leases",
    )
    assert payload["architecture_first_required"] is True
    assert payload["read_only"] is True
    assert payload["execution_authority"] == "none"
    assert payload["registry"]["worker_count"] >= 8
    assert payload["active_mutation_lease_count"] == 0
