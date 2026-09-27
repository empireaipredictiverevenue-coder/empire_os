import inspect

import empire_os.telephony_webhook as webhook
from empire_os.telephony_data_repository import TelephonyDataRepository


class FakeGateway:
    configured = True

    def __init__(self):
        self.inserts = []

    def insert(self, table, row, *, return_repr=True):
        self.inserts.append((table, dict(row), return_repr))
        return []

    def snapshot(self):
        class Snapshot:
            def as_dict(self):
                return {
                    "primary_backend": "supabase_legacy",
                    "configured": True,
                    "dual_write_enabled": False,
                    "write_fallback_enabled": False,
                }
        return Snapshot()


def test_telephony_runtime_contains_no_direct_vendor_db_transport():
    source = inspect.getsource(webhook)

    assert "SUPABASE_URL" not in source
    assert "SUPABASE_KEY" not in source
    assert "/rest/v1/call_logs" not in source
    assert "write_to_supabase" not in source


def test_call_log_repository_is_bounded_to_canonical_insert():
    gateway = FakeGateway()
    repository = TelephonyDataRepository(gateway)

    repository.record_call({"call_sid": "c1", "status": "completed"})

    assert gateway.inserts == [
        (
            "call_logs",
            {"call_sid": "c1", "status": "completed"},
            False,
        )
    ]


def test_call_log_mirror_uses_repository(monkeypatch):
    seen = []

    class Repo:
        configured = True

        def record_call(self, row):
            seen.append(dict(row))

    monkeypatch.setattr(webhook, "_telephony_repository", lambda: Repo())

    payload = webhook.TelephonyWebhookPayload(
        call_sid="c1",
        caller_number="+441",
        destination_number="+442",
        duration=91,
        status="completed",
        payout=12.5,
        recording_url="https://recording.example/c1",
    )

    webhook.write_to_canonical_data(payload)

    assert seen == [{
        "call_sid": "c1",
        "caller_number": "+441",
        "destination_number": "+442",
        "duration": 91,
        "status": "completed",
        "payout": 12.5,
        "recording_url": "https://recording.example/c1",
    }]


def test_unconfigured_optional_mirror_is_noop(monkeypatch):
    class Repo:
        configured = False

        def record_call(self, row):
            raise AssertionError("must not write when unconfigured")

    monkeypatch.setattr(webhook, "_telephony_repository", lambda: Repo())

    payload = webhook.TelephonyWebhookPayload(
        call_sid="c1",
        caller_number="+441",
        destination_number="+442",
    )

    webhook.write_to_canonical_data(payload)


def test_telephony_repository_uses_protected_runtime_env(monkeypatch):
    seen = {}
    fake_gateway = object()

    monkeypatch.setattr(
        webhook,
        "load_runtime_env",
        lambda path: {"EMPIRE_DATA_BACKEND": "supabase_legacy"},
    )
    monkeypatch.setattr(
        webhook.os,
        "environ",
        {"HUB_URL": "http://127.0.0.1:8000"},
    )

    def gateway_factory(env):
        seen["env"] = dict(env)
        return fake_gateway

    monkeypatch.setattr(
        webhook,
        "gateway_from_environment",
        gateway_factory,
    )
    monkeypatch.setattr(
        webhook,
        "TelephonyDataRepository",
        lambda gateway: seen.setdefault("gateway", gateway) or object(),
    )

    webhook._telephony_repository()

    assert seen["env"]["EMPIRE_DATA_BACKEND"] == "supabase_legacy"
    assert seen["gateway"] is fake_gateway
