import json

import empire_os.tag_intelligence_monitor as monitor


def test_monitor_writes_observe_only_runtime_artifact(tmp_path, monkeypatch):
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

    def fake_observe(url):
        return {
            "ok": True,
            "page_tags": {
                "url": url,
                "title": "Empire AI",
                "title_count": 1,
                "meta_description": "Predictive revenue intelligence",
                "canonical_url": url,
                "robots": "index,follow",
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

    monkeypatch.setattr(monitor, "observe_tag_surface", fake_observe)

    result = monitor.refresh_tag_intelligence_monitor(tmp_path)

    assert result["schema_version"] == "empire.tag_intelligence.monitor.v1"
    assert result["mode"] == "OBSERVE"
    assert result["target_count"] == 1
    assert result["available_target_count"] == 1
    assert result["failed_target_count"] == 0
    assert result["high_issue_count"] >= 1
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
