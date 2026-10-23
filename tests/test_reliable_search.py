from pathlib import Path
import importlib


def _module(
    monkeypatch,
    tmp_path,
):
    module = importlib.import_module(
        "empire_os.search_fabric.reliable_search"
    )

    module._MEMO.clear()

    monkeypatch.setattr(
        module,
        "HEALTH_PATH",
        tmp_path
        / "provider-health.json",
    )

    return module


def test_memo_prevents_duplicate_public_call(
    monkeypatch,
    tmp_path,
):
    module = _module(
        monkeypatch,
        tmp_path,
    )

    calls = {
        "count": 0,
    }

    monkeypatch.setattr(
        module,
        "_last_known_good",
        lambda *a, **k: None,
    )

    def public(
        query,
        num=10,
    ):
        calls["count"] += 1

        return [{
            "title":
                "Jane Founder Real Company",
            "link":
                "https://real-company.com/team/jane-founder",
            "snippet":
                "Jane Founder Real Company",
            "position":
                1,
            "engine":
                "brave_web",
        }]

    monkeypatch.setattr(
        module,
        "search_public_web",
        public,
    )

    first = module.search_reliable(
        '"Jane Founder"',
        num=8,
        use_cache=False,
    )

    second = module.search_reliable(
        '"Jane Founder"',
        num=8,
        use_cache=False,
    )

    assert first["organic"]
    assert second["organic"]

    assert calls["count"] == 1

    assert (
        second[
            "searchParameters"
        ]["memory_cache"]
        is True
    )


def test_two_failures_open_persistent_circuit(
    monkeypatch,
    tmp_path,
):
    module = _module(
        monkeypatch,
        tmp_path,
    )

    calls = {
        "count": 0,
    }

    monkeypatch.setattr(
        module,
        "_last_known_good",
        lambda *a, **k: None,
    )

    def failed_public(
        query,
        num=10,
    ):
        calls["count"] += 1
        return []

    monkeypatch.setattr(
        module,
        "search_public_web",
        failed_public,
    )

    one = module.search_reliable(
        '"Person One"',
        use_cache=False,
    )

    two = module.search_reliable(
        '"Person Two"',
        use_cache=False,
    )

    three = module.search_reliable(
        '"Person Three"',
        use_cache=False,
    )

    assert calls["count"] == 2

    assert (
        one["searchParameters"][
            "search_state"
        ]
        == "PROVIDER_DEGRADED"
    )

    assert (
        two[
            "search_operational_status"
        ]
        == "CIRCUIT_OPEN"
    )

    assert (
        three["searchParameters"][
            "circuit_open"
        ]
        is True
    )


def test_last_known_good_prevents_network_call(
    monkeypatch,
    tmp_path,
):
    module = _module(
        monkeypatch,
        tmp_path,
    )

    calls = {
        "count": 0,
    }

    monkeypatch.setattr(
        module,
        "_last_known_good",
        lambda *a, **k: {
            "organic": [{
                "title":
                    "Jane Founder Company",
                "link":
                    "https://company.com/jane",
                "snippet":
                    "",
                "engine":
                    "brave_web",
            }],
            "searchParameters": {
                "search_state":
                    "STALE_RESULTS",
            },
            "search_operational_status":
                "DEGRADED_WITH_LAST_KNOWN_GOOD",
            "error":
                None,
        },
    )

    def public(
        *args,
        **kwargs,
    ):
        calls["count"] += 1
        return []

    monkeypatch.setattr(
        module,
        "search_public_web",
        public,
    )

    result = module.search_reliable(
        '"Jane Founder"',
        use_cache=True,
    )

    assert result["organic"]
    assert calls["count"] == 0


def test_reserved_domains_are_never_search_evidence(
    monkeypatch,
    tmp_path,
):
    module = _module(
        monkeypatch,
        tmp_path,
    )

    monkeypatch.setattr(
        module,
        "_last_known_good",
        lambda *a, **k: None,
    )

    monkeypatch.setattr(
        module,
        "search_public_web",
        lambda *a, **k: [{
            "title":
                "Sahil Aggarwal Example",
            "link":
                "https://example.com/sahil",
            "snippet":
                "",
            "engine":
                "brave_web",
        }],
    )

    result = module.search_reliable(
        '"Sahil Aggarwal"',
        use_cache=False,
    )

    assert result["organic"] == []

    assert (
        result["searchParameters"][
            "search_state"
        ]
        == "PROVIDER_DEGRADED"
    )



def test_healthy_zero_hit_search_does_not_trip_circuit(monkeypatch, tmp_path):
    module=_module(monkeypatch,tmp_path)
    from empire_os.search_fabric.public_fallback import PublicSearchRows
    monkeypatch.setattr(module,"_last_known_good",lambda *a,**k:None)
    calls=[]
    def zero(query,num=10):
        calls.append(query)
        return PublicSearchRows([],provider_available=True)
    monkeypatch.setattr(module,"search_public_web",zero)
    for key in ("missing-company-1","missing-company-2","missing-company-3"):
        r=module.search_reliable(key,use_cache=False)
        assert r["search_operational_status"]=="HEALTHY"
        assert r["searchParameters"]["search_state"]=="NO_RELEVANT_RESULTS"
        assert r["organic"]==[]
    assert len(calls)==3
    assert module.provider_health()["consecutive_failures"]==0
    assert module.provider_health()["circuit_open"] is False


def test_search_shell_without_provider_proof_fails_closed(monkeypatch,tmp_path):
    module=_module(monkeypatch,tmp_path)
    from empire_os.search_fabric.public_fallback import PublicSearchRows
    monkeypatch.setattr(module,"_last_known_good",lambda *a,**k:None)
    monkeypatch.setattr(module,"search_public_web",lambda *a,**k:
                        PublicSearchRows([],provider_available=False))
    r=module.search_reliable("shell-query",use_cache=False)
    assert r["search_operational_status"]=="DEGRADED"
