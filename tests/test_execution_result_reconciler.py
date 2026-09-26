from pathlib import Path

from empire_os.execution_result_reconciler import write_reconciliation


def test_reconciliation_artifact_is_runtime_evidence_only(tmp_path):
    payload = {
        "job_id": "job-1",
        "builder": "hermes",
        "status": "CANDIDATE_VERIFIED",
        "production_merge": False,
        "production_deploy": False,
        "execution_authority": "none",
    }
    path = write_reconciliation(tmp_path, payload)
    text = path.read_text(encoding="utf-8")
    assert '"production_merge": false' in text
    assert '"production_deploy": false' in text
    assert '"execution_authority": "none"' in text
