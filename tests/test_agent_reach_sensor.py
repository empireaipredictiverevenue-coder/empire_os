import pytest

from empire_os.agent_reach_sensor import (
    AgentReachSensorError,
    _validate_public_http_url,
    run_public_sensor,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/x",
        "http://localhost/x",
        "http://10.0.0.1/x",
        "http://192.168.1.2/x",
        "http://169.254.1.1/x",
        "file:///etc/passwd",
    ],
)
def test_sensor_rejects_local_private_and_non_http_targets(url):
    with pytest.raises(AgentReachSensorError):
        _validate_public_http_url(url)


def test_public_ip_literal_is_allowed_by_url_gate():
    assert _validate_public_http_url("https://8.8.8.8/") == "https://8.8.8.8/"


def test_credentialed_or_unknown_channels_are_not_available():
    with pytest.raises(
        AgentReachSensorError,
        match="unsupported or credentialed",
    ):
        run_public_sensor("twitter", "empire ai")


def test_sensor_module_declares_no_truth_or_action_authority():
    import empire_os.agent_reach_sensor as module

    text = open(module.__file__, encoding="utf-8").read()
    assert '"truth_authority": "none"' in text
    assert '"canonical_write_performed": False' in text
    assert '"outbound_action_performed": False' in text
    assert '"execution_authority": "none"' in text
