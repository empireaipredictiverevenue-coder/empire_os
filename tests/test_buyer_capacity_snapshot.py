from scripts.build_buyer_capacity_readiness import fetch_all_buyers


def test_fetch_all_buyers_paginates_past_postgrest_default_cap():
    calls = []

    def request(method, path):
        calls.append(path)
        if "offset=0" in path:
            return [{"id": f"a{i}"} for i in range(1000)]
        if "offset=1000" in path:
            return [{"id": f"b{i}"} for i in range(57)]
        raise AssertionError(path)

    rows = fetch_all_buyers(request, page_size=1000)
    assert len(rows) == 1057
    assert len(calls) == 2
    assert "limit=1000" in calls[0]
    assert "offset=1000" in calls[1]


def test_fetch_all_buyers_rejects_non_list_page():
    def request(method, path):
        return {"bad": "shape"}

    try:
        fetch_all_buyers(request, page_size=100)
    except RuntimeError as exc:
        assert "buyer projection must be a list" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
