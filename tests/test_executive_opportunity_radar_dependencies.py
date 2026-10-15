"""Executive COO source freshness regression. No production reads or writes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from empire_os.executive_commercial_observer import _radar_upstream, observe_executive_commercial_roles

NOW = datetime(2026, 10, 15, 12, 55, tzinfo=timezone.utc)
RADAR = "runtime/opportunity_radar/latest.json"


def seeded(root: Path, parts: dict, *, stamp: str | None = None) -> Path:
    p = root / RADAR
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "mode": "OBSERVE",
        "generated_at": stamp or NOW.isoformat(),
        "source_status": parts,
    }))
    return p


def source(when: datetime, *, available: bool = True) -> dict:
    return {"available": available, "generated_at": when.isoformat()}


def test_fresh_wrapper_does_not_launder_stale_dependencies(tmp_path):
    seeded(tmp_path, {
        "market_gps": source(NOW - timedelta(minutes=30)),
        "competitor_market": source(NOW - timedelta(days=20)),
        "storm_opportunity": source(NOW - timedelta(days=10)),
        "economic_signals": {"available": False, "generated_at": None},
    })
    before = (tmp_path / RADAR).read_bytes()
    out = _radar_upstream(tmp_path, now=NOW)
    assert out["status"] == "STALE_UPSTREAM_HELD"
    assert out["available_source_count"] == 3
    assert out["fresh_upstream_count"] == 1
    assert out["stale_upstream_count"] == 2
    assert {r["component"] for r in out["dependencies"] if r["status"] == "STALE_OR_UNTRUSTED"} == {
        "competitor_market", "storm_opportunity"
    }
    assert out["new_opportunity_or_buyer_claim_authorized"] is False
    assert (tmp_path / RADAR).read_bytes() == before


def test_no_wrapper_and_bad_shape_fail_closed(tmp_path):
    assert _radar_upstream(tmp_path, now=NOW)["status"] == "MISSING"
    p = seeded(tmp_path, {"source": {"available": "yes"}})
    assert _radar_upstream(tmp_path, now=NOW)["status"] == "UNTRUSTED"
    p.write_text(json.dumps({
        "mode": "OBSERVE", "generated_at": NOW.isoformat(),
        "source_status": {},
    }))
    assert _radar_upstream(tmp_path, now=NOW)["status"] == "UNTRUSTED"


def test_all_date_fresh_is_not_commercial_authority(tmp_path):
    seeded(tmp_path, {"sensor": source(NOW)})
    out = _radar_upstream(tmp_path, now=NOW)
    assert out["status"] == "UPSTREAM_DATES_FRESH_NOT_COMMERCIAL_PROOF"
    assert out["new_opportunity_or_buyer_claim_authorized"] is False


def test_old_wrapper_is_not_fresh(tmp_path):
    seeded(tmp_path, {"sensor": source(NOW)}, stamp=(NOW-timedelta(days=3)).isoformat())
    assert _radar_upstream(tmp_path, now=NOW)["status"] == "STALE_RADAR_WRAPPER"


def test_observer_attaches_dependency_diagnosis_without_writing(tmp_path):
    seeded(tmp_path, {"competitor_market": source(NOW-timedelta(days=23))})
    out = observe_executive_commercial_roles(tmp_path, as_of=NOW, service_evidence={})
    assert out["opportunity_radar_dependencies"]["status"] == "STALE_UPSTREAM_HELD"
    assert out["opportunity_radar_dependencies"]["source_refresh_performed"] is False
    assert out["execution_authority"] == "none"
    assert out["production_changes"] is False
    assert out["outbound_enabled"] is False


def test_radar_offering_execution_is_invalid_even_with_fresh_sources(tmp_path):
    p = seeded(tmp_path, {"sensor": source(NOW)})
    d = json.loads(p.read_text())
    d["automatic_external_execution_allowed"] = True
    p.write_text(json.dumps(d))
    out = _radar_upstream(tmp_path, now=NOW)
    assert out["status"] == "UNTRUSTED"
    assert out["new_opportunity_or_buyer_claim_authorized"] is False
