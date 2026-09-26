from pathlib import Path

from empire_os.builder_capabilities import (
    builder_capability_ready,
    read_builder_capabilities,
    record_builder_capability,
)


def test_builder_capability_defaults_fail_closed(tmp_path):
    path = tmp_path / "caps.json"
    assert builder_capability_ready(
        "pi",
        "code_mutation",
        path=path,
    ) is False


def test_builder_capability_records_narrow_evidence(tmp_path):
    path = tmp_path / "caps.json"
    record_builder_capability(
        "empire_coder",
        "structured_patch_mutation",
        ready=True,
        reason="probe_passed",
        model="local-test",
        evidence={"production_mutation": False},
        path=path,
    )
    assert builder_capability_ready(
        "empire_coder",
        "structured_patch_mutation",
        path=path,
    ) is True
    payload = read_builder_capabilities(path)
    row = payload["workers"]["empire_coder"]["structured_patch_mutation"]
    assert row["execution_authority"] == "none"
    assert payload["commercial_authority"] is False
    assert payload["production_deploy_authority"] is False


def test_probe_source_declares_no_production_mutation():
    import empire_os.empire_coder_capability_probe as module
    text = Path(module.__file__).read_text(encoding="utf-8")
    assert "production_mutation: bool = False" in text
    assert "production_push: bool = False" in text
