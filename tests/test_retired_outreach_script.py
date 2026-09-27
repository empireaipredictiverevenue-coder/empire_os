from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/outreach_now.py"


def test_retired_outreach_script_has_no_import_time_output_directory_mutation():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "RETIRED_LEGACY_OUTREACH_NOW" in text
    assert 'OUT = Path("/root/empire_os/outreach_pack")' in text
    assert 'OUT.mkdir(parents=True, exist_ok=True)' not in text
    assert "Use scripts/run_gtm_pipeline_worker.py" in text
