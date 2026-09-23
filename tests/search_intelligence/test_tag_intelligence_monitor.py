import json

from empire_os import tag_intelligence_monitor as module


def test_monitor_writes_observe_only_runtime(monkeypatch, tmp_path):
    target_dir = tmp_path / "runtime/tag_intelligence"
    target_dir.mkdir(parents=True)
    (target_dir / "targets.json").write_text(
        json.dumps({
            "targets": [
                {
                    "id": "empire-home",
                    "url": "https://example.com",
                    "expectations": {
                        "intended_public": True,
                        "meta_ads_expected": True,
                    },
                }
            ]
        })
    )

    monkeypatch.setattr(
        module,
        "observe_tag_surface",
        lambda url: {
            "ok": True,
            "page_tags": {
                "url": url,
                "title": "",
                "meta_description": "",
                "canonical_url": "",
                "robots": "noindex,follow",
                "open_graph": {},
                "twitter": {},
            },
            "measurement_tags": {
                "meta_pixel_ids": ["123"],
                "meta_capi_enabled": True,
                "meta_event_id_dedup": False,
            },
            "limitations": ["static_markup_observation_only"],
        },
    )

    result = module.refresh_tag_intelligence_monitor(tmp_path)

    assert result["target_count"] == 1
    assert result["available_target_count"] == 1
    assert result["critical_issue_count"] >= 2
    assert result["automatic_tag_mutation"] is False
    assert result["measurement_platform_write"] is False
    assert result["execution_authority"] == "none"

    saved = json.loads(
        (target_dir / "latest.json").read_text()
    )
    assert saved["schema_version"] == "empire.tag_intelligence.monitor.v1"


def test_monitor_compares_against_previous_snapshot(monkeypatch, tmp_path):
    target_dir = tmp_path / "runtime/tag_intelligence"
    target_dir.mkdir(parents=True)
    (target_dir / "targets.json").write_text(
        json.dumps({
            "targets": [
                {
                    "id": "site",
                    "url": "https://example.com",
                    "expectations": {},
                }
            ]
        })
    )
    (target_dir / "latest.json").write_text(
        json.dumps({
            "targets": [{
                "target_id": "site",
                "page_tags": {
                    "url": "https://example.com",
                    "title": "Old",
                    "canonical_url": "https://example.com/",
                    "robots": "index,follow",
                },
                "measurement_tags": {
                    "meta_pixel_ids": ["123"],
                },
            }]
        })
    )

    monkeypatch.setattr(
        module,
        "observe_tag_surface",
        lambda url: {
            "ok": True,
            "page_tags": {
                "url": url,
                "title": "New",
                "canonical_url": "https://example.com/",
                "robots": "noindex,follow",
                "open_graph": {},
                "twitter": {},
            },
            "measurement_tags": {
                "meta_pixel_ids": [],
            },
            "limitations": [],
        },
    )

    result = module.refresh_tag_intelligence_monitor(tmp_path)

    assert result["critical_change_count"] >= 2
    changes = result["targets"][0]["changes"]
    fields = {row["field"] for row in changes["changes"]}
    assert "robots" in fields
    assert "meta_pixel_ids" in fields



def test_monitor_uses_env_public_target_when_no_target_file(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv(
        "EMPIRE_TAG_MONITOR_URLS",
        "https://empire-ai.co.uk",
    )
    monkeypatch.setattr(
        module,
        "observe_tag_surface",
        lambda url: {
            "ok": True,
            "page_tags": {
                "url": url,
                "title": "Empire AI",
                "meta_description": "Predictive Revenue",
                "canonical_url": url,
                "robots": "index,follow",
                "open_graph": {
                    "title": "Empire AI",
                    "description": "Predictive Revenue",
                    "url": url,
                    "image": url + "/og.jpg",
                },
                "twitter": {"card": "summary_large_image"},
                "json_ld_types": ["Organization"],
            },
            "measurement_tags": {},
            "limitations": [],
        },
    )

    result = module.refresh_tag_intelligence_monitor(tmp_path)

    assert result["target_count"] == 1
    row = result["targets"][0]
    assert row["url"] == "https://empire-ai.co.uk"
    assert row["expectations"]["intended_public"] is True
    assert row["expectations"]["schema_expected"] is True


def test_monitor_does_not_compare_explicitly_unavailable_previous_snapshot(
    monkeypatch,
    tmp_path,
):
    target_dir = tmp_path / "runtime/tag_intelligence"
    target_dir.mkdir(parents=True)
    (target_dir / "targets.json").write_text(
        json.dumps({
            "targets": [
                {
                    "id": "site",
                    "url": "https://example.com",
                    "expectations": {},
                }
            ]
        })
    )
    (target_dir / "latest.json").write_text(
        json.dumps({
            "targets": [{
                "target_id": "site",
                "available": False,
                "page_tags": {
                    "url": "https://example.com",
                    "title": "Old",
                    "robots": "index,follow",
                },
                "measurement_tags": {
                    "meta_pixel_ids": ["123"],
                },
            }]
        })
    )

    monkeypatch.setattr(
        module,
        "observe_tag_surface",
        lambda url: {
            "ok": True,
            "page_tags": {
                "url": url,
                "title": "New",
                "canonical_url": "https://example.com/",
                "robots": "noindex,follow",
                "open_graph": {},
                "twitter": {},
            },
            "measurement_tags": {
                "meta_pixel_ids": [],
            },
            "limitations": [],
        },
    )

    result = module.refresh_tag_intelligence_monitor(tmp_path)

    assert result["change_count"] == 0
    assert result["critical_change_count"] == 0
    changes = result["targets"][0]["changes"]
    assert changes["comparison_state"] == "BASELINE_ESTABLISHED"
    assert changes["previous_snapshot_available"] is False
