import subprocess

import scripts.run_buyer_deferred_enrichment as worker


def test_identity_recovery_timeout_is_bounded_defer(monkeypatch):
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["identity"], timeout=45)

    monkeypatch.setattr(worker.subprocess, "run", timeout)
    result = worker.recover_identity_isolated(
        business_name="Acme Roofing",
        website="https://acme.example",
        metro="Dallas, TX",
        hard_timeout_seconds=45,
    )
    assert result["decision"] == "deferred"
    assert result["identity"] is None
    assert result["reason"] == "identity_recovery_timeout"


def test_identity_recovery_accepts_valid_child_json(monkeypatch):
    def success(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            ["identity"],
            0,
            stdout='{"decision":"resolved","identity":{"name":"Alex Smith"}}',
            stderr="",
        )

    monkeypatch.setattr(worker.subprocess, "run", success)
    result = worker.recover_identity_isolated(
        business_name="Acme Roofing",
        website="https://acme.example",
        metro="Dallas, TX",
    )
    assert result["decision"] == "resolved"
    assert result["identity"]["name"] == "Alex Smith"


def test_batch_prospect_loader_uses_three_bounded_queries(monkeypatch):
    calls = []

    def fake_get(path, params):
        calls.append((path, dict(params)))
        if path == "/rest/v1/prospects":
            return [{
                "id": "p1",
                "business_name": "Acme Roofing",
                "website": None,
            }]
        if path == "/rest/v1/prospect_entity_links":
            return [{
                "prospect_id": "p1",
                "entity_id": "e1",
                "active": True,
                "match_score": 1.0,
            }]
        if path == "/rest/v1/prospect_acquisitions":
            return []
        raise AssertionError(path)

    monkeypatch.setattr(worker, "_get", fake_get)
    rows = worker._prospect_rows(["p1"])
    assert rows["p1"]["entity_id"] == "e1"
    assert len(calls) == 3
    assert calls[0][1]["id"] == "in.(p1)"
    assert calls[1][1]["prospect_id"] == "in.(p1)"
    assert calls[2][1]["prospect_id"] == "in.(p1)"
