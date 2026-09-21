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
