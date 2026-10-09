from pathlib import Path

from scripts import materialize_buyer_network_candidate_queue as queue


def test_known_identity_lookup_does_not_scan_unrelated_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, "ROOT", tmp_path)
    runtime = tmp_path / "runtime"
    (runtime / "buyer_acquisition").mkdir(parents=True)
    (runtime / "media_os").mkdir(parents=True)
    (runtime / "buyer_acquisition/scout_latest.json").write_text(
        '{"candidates":[{"domain":"px.com"},{"domain":"leadsmartinc.com"}]}'
    )
    (runtime / "media_os/huge_untrusted_dump.json").write_text(
        '{"url":"https://fake-customer.com","self":"yourdomain.com"}'
    )
    result = queue.existing_runtime_domains()
    assert {"px.com","leadsmartinc.com"} <= result
    assert "fake-customer.com" not in result
    assert "yourdomain.com" not in result


def test_queue_rejects_own_and_placeholder_domains():
    assert not queue.accepted_domain("yourdomain.com")
    assert not queue.accepted_domain("empire-ai.co.uk")
    assert not queue.accepted_domain("empire.buyer")
    assert not queue.accepted_domain("latest.json")
    assert not queue.accepted_domain("semrush.com")
    assert queue.accepted_domain("buythecalls.com")
