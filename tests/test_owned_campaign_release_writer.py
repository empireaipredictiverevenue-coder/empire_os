import json
from pathlib import Path

from empire_os.owned_campaign_content import prepare_marketing
from empire_os.owned_campaign_preflight import INFRASTRUCTURE_GATES
from empire_os.owned_campaign_release import build_release_manifest

ROOT = Path(__file__).resolve().parent / "fixtures/owned_campaign_runtime"


def test_release_writer_requires_all_gates_and_zero_paid():
    marketing=json.loads((ROOT/"runtime/astra/department_cycle_latest.json").read_text())["marketing_growth"]
    infra={k:{"status":"PASS","evidence_refs":["live:test"]} for k in INFRASTRUCTURE_GATES}
    repo_root = Path(__file__).resolve().parents[1]
    manifest=build_release_manifest(
        marketing, infra, root=ROOT, evidence_refs=["live:test"],
        script_path=repo_root / "apps/empire-public-site/public/research-runtime.js",
    )
    assert manifest["deployment_verified"] is True
    assert manifest["zero_paid_media"] is True
    assert len(manifest["campaign_ids"]) == 5
    assert len(manifest["campaigns"]) == 5
    assert [c["campaign_id"] for c in manifest["campaigns"]] == manifest["campaign_ids"]
    assert manifest["execution_authority"] == "none"
