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
