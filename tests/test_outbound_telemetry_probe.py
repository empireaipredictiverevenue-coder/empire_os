import pytest

from empire_os.outbound_telemetry_probe import probe_loopback_health


class Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


def test_loopback_probe_accepts_ready_health_payload():
    def get(url, **kwargs):
        assert url == "http://127.0.0.1:8097/health"
        assert kwargs["timeout"] <= 5.0
        return Response(200, {
            "ok": True,
            "ready": True,
            "provider": "resend",
            "mode": "OBSERVE",
            "ingest_transport": "postgres",
            "signature_verification_configured": True,
            "reply_receiving_ready": True,
        })

    result = probe_loopback_health(
        "provider_event_ingest",
        "http://127.0.0.1:8097/health",
        now=None,
        request_get=get,
    )
    assert result["success"] is True
    assert result["coverage"] is True
    assert result["details"]["provider"] == "resend"


def test_loopback_probe_reports_reachable_but_not_ready_as_partial_coverage():
    result = probe_loopback_health(
        "provider_event_ingest",
        "http://localhost:8097/health",
        request_get=lambda *_args, **_kwargs: Response(200, {
            "ok": True,
            "ready": False,
            "provider": "resend",
        }),
    )
    assert result["success"] is True
    assert result["coverage"] is False


def test_loopback_probe_failure_becomes_failed_heartbeat():
    def fail(*_args, **_kwargs):
        raise ConnectionError("down")

    result = probe_loopback_health(
        "provider_event_ingest",
        "http://127.0.0.1:8097/health",
        request_get=fail,
    )
    assert result["success"] is False
    assert result["coverage"] is False
    assert result["details"]["error"] == "ConnectionError"


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8097/health",
        "http://example.com/health",
        "http://10.0.0.2/health",
    ],
)
def test_probe_rejects_non_loopback_or_https_targets(url):
    with pytest.raises(ValueError):
        probe_loopback_health(
            "provider_event_ingest",
            url,
            request_get=lambda *_args, **_kwargs: None,
        )
