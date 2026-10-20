from datetime import datetime, timedelta, timezone

from empire_os.coder.provider_health import ProviderHealth


def test_failure_excludes_route_until_cooldown(tmp_path):
    health = ProviderHealth(tmp_path / "health.json", cooldown_seconds=300)
    health.record_failure("ollama", "small", "TimeoutError")
    assert ("ollama", "small") in health.excluded_routes()


def test_success_clears_route_cooldown(tmp_path):
    health = ProviderHealth(tmp_path / "health.json", cooldown_seconds=300)
    health.record_failure("ollama", "small", "TimeoutError")
    health.record_success("ollama", "small")
    assert health.excluded_routes() == ()


def test_expired_cooldown_is_not_excluded(tmp_path):
    health = ProviderHealth(tmp_path / "health.json", cooldown_seconds=30)
    health.record_failure("ollama", "small", "TimeoutError")
    future = datetime.now(timezone.utc) + timedelta(minutes=2)
    assert health.excluded_routes(now=future) == ()


def test_timeout_backoff_and_recovery(tmp_path, monkeypatch):
    from empire_os.coder import provider_health as module

    health = ProviderHealth(tmp_path / "health.json", cooldown_seconds=300)
    start = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    for index, expected in enumerate((300, 600, 1200, 2400, 3600, 3600)):
        now = start + timedelta(seconds=10 * index)
        monkeypatch.setattr(module, "_now", lambda now=now: now)
        health.record_failure("ollama", "writer", "ollama_request_failed:TimeoutError")
        row = health.snapshot()["routes"]["ollama:writer"]
        assert row["cooldown_seconds_applied"] == expected
    health.record_success("ollama", "writer")
    health.record_failure("ollama", "writer", "TimeoutError")
    assert health.snapshot()["routes"]["ollama:writer"]["cooldown_seconds_applied"] == 300
