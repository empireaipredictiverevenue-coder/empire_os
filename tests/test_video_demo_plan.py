import pytest

from empire_os.video_demo_plan import DemoStep, build_video_demo_manifest


def test_manifest_is_evidence_backed_and_recording_disabled():
    result = build_video_demo_manifest(
        title="Roofing opportunity demo",
        app_url="https://empire-ai.co.uk/demo",
        niche="roofing",
        steps=[
            DemoStep(
                action="navigate",
                target="/opportunities",
                description="Show live opportunity evidence",
                evidence_ref="capability:opportunity",
            ),
            DemoStep(
                action="click",
                target="[data-testid='qualified']",
                description="Show qualification evidence",
                evidence_ref="capability:qualification",
            ),
        ],
        capability_evidence_refs=("capability:crm",),
    )
    assert result["recording_engine"] == "playwright_optional_adapter"
    assert result["recording_enabled"] is False
    assert result["publishing_enabled"] is False
    assert result["synthetic_proof_allowed"] is False
    assert result["actual_revenue"] is False


def test_manifest_rejects_non_http_target():
    with pytest.raises(ValueError, match="http"):
        build_video_demo_manifest(
            title="bad",
            app_url="file:///etc/passwd",
            niche="roofing",
            steps=[
                DemoStep(
                    action="navigate",
                    target="/",
                    description="bad",
                    evidence_ref="ref:1",
                )
            ],
            capability_evidence_refs=("ref:2",),
        )
