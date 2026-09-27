import inspect

import empire_os.auto_onboard as onboard
from empire_os.auto_onboard_data_repository import AutoOnboardDataRepository


class Snapshot:
    def as_dict(self):
        return {
            "primary_backend": "supabase_legacy",
            "configured": True,
            "dual_write_enabled": False,
            "write_fallback_enabled": False,
        }


class FakeGateway:
    def __init__(self, configured=True):
        self.configured = configured
        self.inserts = []

    def insert(self, table, row, *, return_repr=True):
        self.inserts.append((table, dict(row), return_repr))
        return []

    def snapshot(self):
        return Snapshot()


def test_auto_onboard_runtime_contains_no_direct_vendor_dependency():
    source = inspect.getsource(onboard)

    assert "SUPABASE_URL" not in source
    assert "SUPABASE_SERVICE_KEY" not in source
    assert "Supabase" not in source
    assert "/rest/v1/" not in source


def test_buyer_mirror_is_bounded_canonical_insert():
    gateway = FakeGateway()
    repository = AutoOnboardDataRepository(gateway)

    assert repository.record_buyer({
        "buyer_name": "Example",
        "niche": "roofing",
    }) is True

    assert gateway.inserts == [
        (
            "buyers",
            {"buyer_name": "Example", "niche": "roofing"},
            False,
        )
    ]
    snapshot = repository.snapshot()
    assert snapshot["repository_authority"] == "buyer_mirror_only"
    assert snapshot["delivery_path_authority"] is False
    assert snapshot["dual_write_enabled"] is False


def test_unconfigured_mirror_is_noop():
    gateway = FakeGateway(configured=False)
    repository = AutoOnboardDataRepository(gateway)

    assert repository.record_buyer({"buyer_name": "Example"}) is False
    assert gateway.inserts == []


def test_mirror_buyer_uses_supplied_repository():
    seen = []

    class Repo:
        def record_buyer(self, row):
            seen.append(dict(row))
            return True

    assert onboard._mirror_buyer(
        name="Example Buyer",
        niche="roofing",
        base=45.0,
        fee=1.0,
        funded=True,
        status="active",
        repository=Repo(),
    ) is True

    assert seen == [{
        "buyer_name": "Example Buyer",
        "niche": "roofing",
        "base_payout": 45.0,
        "per_lead_rate": 45.0,
        "fee_rate": 1.0,
        "per_call_fee": 45.0,
        "is_active": True,
        "status": "active",
        "state_coverage": ["ALL"],
        "timezone": "America/New_York",
        "priority": 5,
        "daily_cap": 0,
    }]
