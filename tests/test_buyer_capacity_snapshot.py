from types import SimpleNamespace

import pytest

from empire_os.buyer_allocation_repository import BUYER_COLUMNS, BuyerAllocationDataRepository
from empire_os.canonical_data_gateway import CanonicalDataGateway, DataGatewayUnavailable
from empire_os.data_cloud_contract import DataBackend
from empire_os.data_query import OrderSpec
from scripts import build_buyer_capacity_readiness as snapshot


class BuyerProvider:
    backend = DataBackend.EMPIREDB

    def __init__(self, pages):
        self.pages = iter(pages)
        self.calls = []

    def configured(self):
        return True

    def query(self, table, columns, **kwargs):
        self.calls.append((table, columns, kwargs))
        page = next(self.pages)
        if isinstance(page, Exception):
            raise page
        return page


def repository(provider):
    return BuyerAllocationDataRepository(CanonicalDataGateway(provider))


def test_fetch_all_buyers_paginates_through_canonical_gateway():
    provider = BuyerProvider([
        [{"id": f"a{i}"} for i in range(1000)],
        [{"id": f"b{i}"} for i in range(57)],
    ])
    rows = snapshot.fetch_all_buyers(repository(provider))
    assert len(rows) == 1057
    assert [call[2]["offset"] for call in provider.calls] == [0, 1000]
    for table, columns, query in provider.calls:
        assert table == "buyers"
        assert columns == BUYER_COLUMNS
        assert query["limit"] == 1000
        assert query["filters"] == ()
        assert query["order"] == (
            OrderSpec("created_at", descending=True),
            OrderSpec("id", descending=True),
        )


@pytest.mark.parametrize("page_size,max_rows,size,cap", [
    (2, 3, 2, 3), (0, 0, 1, 1), (2000, 1, 1000, 1000),
    (1000, 100000, 1000, 50000),
])
def test_fetch_all_buyers_preserves_bounds(page_size, max_rows, size, cap):
    pages = [[{"id": str(i)} for i in range(size)]] * ((cap + size - 1) // size)
    provider = BuyerProvider(pages)
    rows = snapshot.fetch_all_buyers(repository(provider), page_size=page_size, max_rows=max_rows)
    assert len(rows) == cap
    assert [c[2]["offset"] for c in provider.calls] == list(range(0, cap, size))
    assert all(c[2]["limit"] == size for c in provider.calls)


@pytest.mark.parametrize("page", [None, {}, "invalid"])
def test_fetch_all_buyers_rejects_non_list_page(page):
    reader = SimpleNamespace(buyer_page=lambda **kwargs: page)
    with pytest.raises(RuntimeError, match="buyer projection must be a list"):
        snapshot.fetch_all_buyers(reader)


def test_default_reader_loads_runtime_environment(monkeypatch):
    env = {"EMPIRE_DATA_BACKEND": "empiredb"}
    provider = BuyerProvider([[]])
    paths = []
    received = []
    monkeypatch.setattr(snapshot, "load_runtime_env", lambda path: paths.append(path) or env)
    monkeypatch.setattr(snapshot, "gateway_from_environment", lambda source: received.append(source) or CanonicalDataGateway(provider))
    assert snapshot.fetch_all_buyers() == []
    assert paths == ["/etc/empire_os.env"]
    assert received == [env]
    assert len(provider.calls) == 1


def test_gateway_failure_preserves_last_snapshot(monkeypatch, tmp_path):
    provider = BuyerProvider([
        [{"id": str(i)} for i in range(1000)],
        DataGatewayUnavailable("canonical read failed"),
    ])
    monkeypatch.setattr(snapshot, "load_runtime_env", lambda path: {"EMPIRE_DATA_BACKEND": "empiredb"})
    monkeypatch.setattr(snapshot, "gateway_from_environment", lambda env: CanonicalDataGateway(provider))
    output = tmp_path / "latest.json"
    output.write_text("last known snapshot\n")
    monkeypatch.setattr(snapshot, "OUT", output)
    with pytest.raises(DataGatewayUnavailable, match="canonical read failed"):
        snapshot.main()
    assert output.read_text() == "last known snapshot\n"
    assert not output.with_suffix(".json.tmp").exists()
    assert len(provider.calls) == 2


def test_unconfigured_gateway_fails_closed(monkeypatch):
    provider = BuyerProvider([])
    monkeypatch.setattr(provider, "configured", lambda: False)
    with pytest.raises(DataGatewayUnavailable):
        snapshot.fetch_all_buyers(repository(provider))
    assert provider.calls == []
