from empire_os.commercial_evidence_auto_verifier import (
    run_commercial_evidence_auto_verifier,
)


def test_auto_verifier_advances_only_bounded_rpc_results():
    calls = []

    def request(method, path, payload=None, **_kwargs):
        calls.append((method, path, payload))
        if path.endswith("list_auto_verifiable_commercial_evidence"):
            return [
                {
                    "evidence_id": "00000000-0000-0000-0000-000000000001",
                    "buyer_id": "00000000-0000-0000-0000-000000000002",
                }
            ]
        if path.endswith("auto_verify_buyer_stated_commercial_evidence"):
            return {
                "decision": "verified",
                "evidence_id": payload["p_evidence_id"],
                "status": "verified",
                "actual_revenue": False,
            }
        raise AssertionError(path)

    result = run_commercial_evidence_auto_verifier(request, limit=25)
    assert result["attempted"] == 1
    assert result["verified"] == 1
    assert result["failed_closed"] == 0
    assert result["terms_approved"] is False
    assert result["payment_mutation"] is False
    assert result["revenue_recognition"] is False
    assert all(
        "verify_commercial_evidence" not in path
        or "auto_verify_buyer_stated" in path
        for _method, path, _payload in calls
    )


def test_auto_verifier_fails_closed_per_item():
    def request(method, path, payload=None, **_kwargs):
        if path.endswith("list_auto_verifiable_commercial_evidence"):
            return [
                {"evidence_id": "00000000-0000-0000-0000-000000000001"},
                {"evidence_id": "00000000-0000-0000-0000-000000000002"},
            ]
        if payload["p_evidence_id"].endswith("0001"):
            raise RuntimeError("binding mismatch")
        return {
            "decision": "verified",
            "status": "verified",
        }

    result = run_commercial_evidence_auto_verifier(request)
    assert result["attempted"] == 2
    assert result["verified"] == 1
    assert result["failed_closed"] == 1
    assert result["ok"] is False


def test_auto_verifier_empty_queue_is_clean():
    def request(method, path, payload=None, **_kwargs):
        assert path.endswith("list_auto_verifiable_commercial_evidence")
        return []

    result = run_commercial_evidence_auto_verifier(request)
    assert result["attempted"] == 0
    assert result["verified"] == 0
    assert result["failed_closed"] == 0
    assert result["ok"] is True
