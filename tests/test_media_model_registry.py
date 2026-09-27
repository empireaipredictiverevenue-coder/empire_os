import json

from empire_os.model_registry import ModelRegistry


def test_media_model_eligibility_fails_closed_when_license_unknown(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "models.json"
    path.write_text(json.dumps({
        "models": [
            {
                "model_id": "unknown-media",
                "provider": "local",
                "model": "unknown",
                "capabilities": ["image_generation"],
                "media_tasks": ["image_generation"],
                "enabled": True,
            }
        ]
    }))
    monkeypatch.setenv(
        "EMPIRE_ZEN_CATALOG_CACHE",
        str(tmp_path / "missing-zen.json"),
    )

    registry = ModelRegistry(str(path))
    model = registry.get("unknown-media")

    assert model is not None
    assert model.license_id is None
    assert model.commercial_permission is None
    assert model.commercial_media_eligible("image_generation") is False


def test_media_model_eligibility_requires_verified_commercial_permission(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "models.json"
    path.write_text(json.dumps({
        "models": [
            {
                "model_id": "permitted-image",
                "provider": "local",
                "model": "permitted-image",
                "capabilities": ["image_generation"],
                "media_tasks": ["image_generation", "thumbnail"],
                "license_id": "Apache-2.0",
                "commercial_permission": True,
                "attribution_required": False,
                "deployment": "local",
                "vram_gb": 24,
                "latency_ms": 4500,
                "last_benchmark": "2026-09-23",
                "last_reviewed": "2026-09-23",
                "enabled": True,
            },
            {
                "model_id": "noncommercial-video",
                "provider": "local",
                "model": "noncommercial-video",
                "capabilities": ["video_generation"],
                "media_tasks": ["video_generation"],
                "license_id": "NON_COMMERCIAL",
                "commercial_permission": False,
                "enabled": True,
            },
        ]
    }))
    monkeypatch.setenv(
        "EMPIRE_ZEN_CATALOG_CACHE",
        str(tmp_path / "missing-zen.json"),
    )

    registry = ModelRegistry(str(path))
    image = registry.get("permitted-image")
    video = registry.get("noncommercial-video")

    assert image is not None
    assert image.commercial_media_eligible("image_generation") is True
    assert image.commercial_media_eligible("video_generation") is False

    assert video is not None
    assert video.commercial_media_eligible("video_generation") is False

    summary = registry.summary()
    assert summary["commercial_media_permission_verified"] == 1

    rows = {row["model_id"]: row for row in registry.describe()}
    assert rows["permitted-image"]["license_id"] == "Apache-2.0"
    assert rows["permitted-image"]["deployment"] == "local"
    assert rows["permitted-image"]["vram_gb"] == 24.0
    assert rows["permitted-image"]["media_tasks"] == [
        "image_generation",
        "thumbnail",
    ]
