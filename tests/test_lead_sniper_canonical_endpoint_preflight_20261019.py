"""No-write endpoint preflight tests: canonical query is the only action."""
from scripts.probe_lead_sniper_canonical_endpoint_20261019 import run


class Reader:
    def __init__(self, *, fail=False):
        self.calls = []
        self.fail = fail

    def pending_review_exists(self, url):
        self.calls.append(url)
        if self.fail:
            raise PermissionError("do not leak canonical credential detail")
        return False


def test_endpoint_readonly_preflight_no_writes_and_safe_output():
    repo = Reader()
    result = run(repository=repo)
    assert result["status"] == "READ_ONLY_REVIEW_QUERY_PASS"
    assert result["canonical_empiredb_read_contract_verified"] is True
    assert result["queue_write_authorized_by_probe"] is False
    assert result["outbound_authorized"] is False
    assert len(repo.calls) == 1


def test_unavailable_canonical_read_fail_closed_no_secret_leak():
    repo = Reader(fail=True)
    result = run(repository=repo)
    assert result["status"] == "HOLD_CANONICAL_READER_UNAVAILABLE"
    assert result["reason"] == "PermissionError"
    assert "credential" not in str(result)
    assert result["queue_write_authorized_by_probe"] is False
    assert result["execution_authority"] == "none"
