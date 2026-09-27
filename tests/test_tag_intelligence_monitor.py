import json

import empire_os.tag_intelligence_monitor as monitor


def _write_targets(tmp_path):
    targets = tmp_path / "runtime/tag_intelligence/targets.json"
    targets.parent.mkdir(parents=True)
    targets.write_text(
        json.dumps({
            "targets": [{
                "id": "empire-home",
                "url": "https://empire-ai.co.uk",
                "expectations": {
                    "intended_public": True,
                    "schema_expected": True,
                    "google_analytics_expected": True,
                },
            }]
        }),
        encoding="utf-8",
    )


def _observation(url, *, robots="index,follow"):
    return {
        "ok": True,
        "page_tags": {
            "url": url,
            "title": "Empire AI",
            "title_count": 1,
            "meta_description": "Predictive revenue intelligence",
            "canonical_url": url,
            "robots": robots,
            "open_graph": {
                "title": "Empire AI",
                "description": "Predictive revenue intelligence",
                "url": url,
                "image": "https://empire-ai.co.uk/og.jpg",
            },
            "twitter": {"card": "summary_large_image"},
            "json_ld_types": ["Organization"],
            "hreflang": [],
            "viewport_present": True,
            "charset_present": True,
            "h1_count": 1,
            "images_missing_alt": 0,
            "meta_keywords_present": False,
        },
        "measurement_tags": {
            "ga4_measurement_ids": [],
            "google_tag_ids": [],
            "gtm_container_ids": [],
            "google_ads_conversion_ids": [],
            "meta_pixel_ids": [],
            "duplicate_tag_counts": {},
            "observed_events": [],
            "duplicate_event_counts": {},
            "meta_capi_enabled": None,
            "meta_event_id_dedup": None,
            "server_side_tagging": None,
            "revenue_truth_linked": None,
        },
        "limitations": ["static_markup_observation_only"],
        "mode": "OBSERVE",
        "execution_authority": "none",
    }


def test_monitor_writes_observe_only_runtime_artifact(tmp_path, monkeypatch):
    _write_targets(tmp_path)
    monkeypatch.setattr(
        monitor,
        "observe_tag_surface",
        lambda url: _observation(url),
    )

    result = monitor.refresh_tag_intelligence_monitor(tmp_path)

    assert result["schema_version"] == "empire.tag_intelligence.monitor.v1"
    assert result["mode"] == "OBSERVE"
    assert result["target_count"] == 1
    assert result["available_target_count"] == 1
    assert result["failed_target_count"] == 0
    assert result["high_issue_count"] >= 1
    assert result["monitored_site_count"] == 1
    assert result["monitored_page_count"] == 1
    assert result["search_issue_count"] == 0
    assert result["measurement_issue_count"] >= 1
    assert result["change_count"] == 0
    assert result["critical_change_count"] == 0
    assert result["pages_with_public_noindex"] == 0
    assert result["pages_missing_canonical"] == 0
    assert result["pages_missing_schema"] == 0
    assert result["missing_conversion_event_count"] == 0
    assert result["duplicate_conversion_event_count"] == 0
    assert result["measurement_observation"]["ga4"] == (
        "NOT_OBSERVED_IN_STATIC_MARKUP"
    )
    assert result["measurement_observation"]["gtm"] == (
        "NOT_OBSERVED_IN_STATIC_MARKUP"
    )
    assert result["measurement_observation"]["meta_capi_dedup"] == "UNKNOWN"
    assert result["measurement_observation"]["revenue_truth_linkage"] == "UNKNOWN"
    change_state = result["targets"][0]["changes"]
    assert change_state["comparison_state"] == "BASELINE_ESTABLISHED"
    assert change_state["previous_snapshot_available"] is False
    assert change_state["change_count"] == 0
    assert change_state["critical_change_count"] == 0
    assert result["automatic_tag_mutation"] is False
    assert result["publishing_execution"] is False
    assert result["measurement_platform_write"] is False
    assert result["actual_revenue"] is False
    assert result["execution_authority"] == "none"

    written = json.loads(
        (
            tmp_path / "runtime/tag_intelligence/latest.json"
        ).read_text(encoding="utf-8")
    )
    assert written == result


def test_monitor_detects_real_change_after_baseline(tmp_path, monkeypatch):
    _write_targets(tmp_path)

    state = {"robots": "index,follow"}

    def fake_observe(url):
        return _observation(url, robots=state["robots"])

    monkeypatch.setattr(monitor, "observe_tag_surface", fake_observe)

    first = monitor.refresh_tag_intelligence_monitor(tmp_path)
    assert first["critical_change_count"] == 0

    state["robots"] = "noindex,nofollow"
    second = monitor.refresh_tag_intelligence_monitor(tmp_path)

    change_state = second["targets"][0]["changes"]
    assert change_state["comparison_state"] == "COMPARED"
    assert change_state["previous_snapshot_available"] is True
    assert change_state["change_count"] >= 1
    assert change_state["critical_change_count"] >= 1
    assert any(
        row["field"] == "robots"
        and row["previous"] == "index,follow"
        and row["current"] == "noindex,nofollow"
        for row in change_state["changes"]
    )
