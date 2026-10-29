"""No-write compatibility tests against the exact already pinned Founder V4.9 app."""
import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, "/srv/empire_os/scripts")
import founder_radar_pinned_v49_compat_20261029 as patch
PATH="/v1/founder-dashboard/overview"

def test_pinned_lifecycle_compatibility_preserves_every_existing_field():
    with TestClient(patch.app) as client:
        response=client.get(PATH)
        assert response.status_code==200
        updated=response.json()
        # Get the baseline from the pinned original endpoint, not from newer repo code.
        base=next(
            r for r in patch.app.routes
            if hasattr(r,'original_router')
            and any(getattr(n,'path',None)==PATH for n in r.original_router.routes)
        )
        old_route=next(r for r in base.original_router.routes if getattr(r,'path',None)==PATH)
        original=old_route.endpoint()
        assert set(updated)==set(original)
        assert set(updated)-{'opportunity_radar'} == set(original)-{'opportunity_radar'}
        assert updated['mode'] == original['mode']
        assert updated['execution_authority'] == original['execution_authority']
        radar=updated["opportunity_radar"]
        assert radar['available'] is True
        assert radar['execution_authority'] == 'none'
        assert radar['automatic_external_execution_allowed'] is False
        lifecycle=radar["lifecycle_evidence"]
        assert lifecycle["status"]=="CURRENT_DERIVED_HISTORY_OBSERVED"
        assert lifecycle["history_verified_for_cycle"] is True
        assert lifecycle["execution_authority"]=="none"
        assert lifecycle["outreach_authorized"] is False
        assert lifecycle["commercial_validation_verified"] is False


def test_live_v49_and_other_pinned_routes_remain_unchanged():
    with TestClient(patch.app) as client:
        for path in ["/health", "/v1/predictive-cloud/v4/shadow-readiness", "/v1/predictive-cloud/status"]:
            response=client.get(path)
            assert response.status_code==200,(path,response.status_code)
            body=response.json()
            if path=="/health":
                assert body["ok"] is True
            if "v4/shadow-readiness" in path:
                assert body["trading_authorized"] is False
                assert body["commercial_prediction_authorized"] is False


def test_invalid_history_fails_closed_without_claiming_verified():
    original=patch._verified_radar
    try:
        patch._verified_radar=lambda: (_ for _ in ()).throw(ValueError('invalid_history'))
        with TestClient(patch.app) as client:
            data=client.get(PATH).json()
            assert data["opportunity_radar"].get("lifecycle_evidence") is None
    finally:
        patch._verified_radar=original



def test_oversized_dashboard_stream_is_not_truncated_or_augmented():
    old = patch.MAX_JSON_BODY
    try:
        patch.MAX_JSON_BODY = 1
        with TestClient(patch.app) as client:
            response = client.get(PATH)
            assert response.status_code == 200
            result = response.json()
            assert "lifecycle_evidence" not in result["opportunity_radar"]
            assert "available" in result["opportunity_radar"]
    finally:
        patch.MAX_JSON_BODY = old


def test_unrelated_founder_routes_not_augmented():
    with TestClient(patch.app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json().get("service") == "founder-dashboard-read-api"
        assert "opportunity_radar" not in response.json()


def test_release_override_points_only_at_protected_pinned_compatibility_stage():
    source = Path("/srv/empire_os/scripts/empire-founder-dashboard-api-radar-20261029.conf").read_text()
    assert source.startswith("[Service]\nExecStart=\n")
    assert "--app-dir /opt/empire-ai/founder-read-releases/radar-v1-20261029 " in source
    assert "founder_radar_pinned_v49_compat_20261029:app --host 127.0.0.1 --port 8766" in source
    assert "--app-dir /srv/empire_os/scripts " not in source
    assert "EMPIRE_EXECUTION_MODE" not in source
    assert "zzzzzzzzzzzz-founder-radar-20261029.conf" > "zzzzzzzzzzz-predictive-v49-20261025.conf"
