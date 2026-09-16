from types import SimpleNamespace

from empire_os.agents import data_acq_agent


def _ok_response():
    return SimpleNamespace(json=lambda: {"ok": True})


def test_post_preserves_matching_observed_niche_and_metro(monkeypatch):
    sent = []

    def fake_post(url, json, timeout):
        sent.append(json)
        return _ok_response()

    monkeypatch.setattr(data_acq_agent.requests, "post", fake_post)

    lead = {
        "name": "Observed Roofing Ltd",
        "niche": "Roofing",
        "metro": "Austin",
        "source": "permits",
    }

    assert data_acq_agent.post(lead, "roofing", "austin", "real") is True
    assert sent[0]["niche"] == "Roofing"
    assert sent[0]["metro"] == "Austin"
    assert sent[0]["source"] == "acq_permits"


def test_post_rejects_niche_mismatch_before_intake(monkeypatch):
    calls = []

    monkeypatch.setattr(
        data_acq_agent.requests,
        "post",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    lead = {
        "name": "Observed Plumbing Ltd",
        "niche": "plumbing",
        "metro": "Austin",
        "source": "permits",
    }

    assert data_acq_agent.post(lead, "roofing", "Austin", "real") is False
    assert calls == []


def test_post_rejects_metro_mismatch_before_intake(monkeypatch):
    calls = []

    monkeypatch.setattr(
        data_acq_agent.requests,
        "post",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    lead = {
        "name": "Observed Roofing Ltd",
        "niche": "roofing",
        "metro": "Dallas",
        "source": "permits",
    }

    assert data_acq_agent.post(lead, "roofing", "Austin", "real") is False
    assert calls == []
