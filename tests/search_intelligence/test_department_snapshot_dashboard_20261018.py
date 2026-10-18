"""Only aggregate-first-party SEO evidence may reach the search dashboard."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.search_intelligence import department_snapshot as snapshot
from empire_os.search_intelligence.api import create_search_router
from tests.test_search_department_integrated_20261018 import evidence
from empire_os.search_intelligence.department_integration_review import reconcile_department


@pytest.fixture(autouse=True)
def reset():
    snapshot._reset_snapshot_for_tests()
    yield
    snapshot._reset_snapshot_for_tests()


def report():
    return reconcile_department(**evidence())


def test_cached_aggregates_are_allowlisted_and_not_raw_source_data():
    raw = report()
    raw["private_query"] = "buyer name and private@company.test"
    n = []
    def reader():
        n.append(True)
        return raw
    a = snapshot.read_department_snapshot(reader=reader,clock=lambda:1.0)
    b = snapshot.read_department_snapshot(reader=reader,clock=lambda:300.0)
    assert len(n) == 1
    assert a == b
    assert a is not b
    assert a["schema_version"] == "empire.search_growth.department_integration.v1"
    assert a["gsc_returned_page_rows"] == 28
    assert a["legacy_404_core_topic_editorial_review_count"] == 16
    assert a["independent_google_rank_positions_verified"] is False
    assert a["customer_identifiers_disclosed"] is False
    assert "private_query" not in a
    assert "private@company.test" not in str(a)
    assert a["execution_authority"] == "NONE"
    a["open_gates"].append("LOCAL_TEST_MUTATION")
    assert "LOCAL_TEST_MUTATION" not in b["open_gates"]


def test_ttl_requery_source_exact_boundary():
    calls = []
    def reader():
        calls.append(True)
        return report()
    snapshot.read_department_snapshot(reader=reader,clock=lambda:10.0)
    snapshot.read_department_snapshot(reader=reader,clock=lambda:909.0)
    assert len(calls) == 1
    snapshot.read_department_snapshot(reader=reader,clock=lambda:910.0)
    assert len(calls) == 2


def test_unavailable_refresh_never_returns_stale_data():
    snapshot.read_department_snapshot(reader=report,clock=lambda:1)
    def fail():raise RuntimeError("secret-token-DO-NOT-PRINT")
    with pytest.raises(snapshot.DepartmentSnapshotUnavailable,
                       match="DEPARTMENT_SOURCE_EVIDENCE_UNAVAILABLE"):
        snapshot.read_department_snapshot(reader=fail,clock=lambda:1_000)
    assert snapshot._cached is None


@pytest.mark.parametrize("update",[
    lambda d:d.update(database_writes=True),
    lambda d:d.update(outbound_sent=True),
    lambda d:d.update(realised_revenue_verified=True),
    lambda d:d.update(search_rankings_verified=True),
    lambda d:d.update(status="RANKS_VERIFIED"),
    lambda d:d["open_gates"].append("CRM.email@example.test"),
    lambda d:d.update(gsc_returned_page_rows=-1),
    lambda d:d["legacy_404_editorial_category_counts"].update(
        OFF_CORE_RETAIN_404_PENDING_EVIDENCE=9000),
])
def test_promoted_authority_and_unsafe_data_rejected(update):
    x=report();update(x)
    with pytest.raises(snapshot.DepartmentSnapshotUnavailable):
        snapshot.read_department_snapshot(reader=lambda:x,clock=lambda:0)


def test_api_route_returns_only_safe_aggregates(monkeypatch):
    monkeypatch.setattr(snapshot,"read_department_snapshot",lambda: {
        "schema_version":"empire.search_growth.department_integration.v1",
        "status":"DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN",
        "mode":"OBSERVE","gsc_returned_page_rows":28,
        "search_rankings_verified":False,
        "buyer_enquiries_verified":False,
        "realised_revenue_verified":False,
    })
    app=FastAPI()
    app.include_router(create_search_router())
    result=TestClient(app).get("/v1/search/department/review")
    assert result.status_code == 200
    assert result.json()["search_rankings_verified"] is False
    assert "private" not in result.text


def test_api_route_unavailable_is_generic_non_leaking_503(monkeypatch):
    def fail():raise snapshot.DepartmentSnapshotUnavailable("sensitive customer token")
    monkeypatch.setattr(snapshot,"read_department_snapshot",fail)
    app=FastAPI()
    app.include_router(create_search_router())
    response=TestClient(app).get("/v1/search/department/review")
    assert response.status_code == 503
    assert response.json() == {"detail":"department_evidence_unavailable"}
    assert response.headers["cache-control"]=="no-store"
    assert "customer token" not in response.text
