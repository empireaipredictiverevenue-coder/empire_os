"""Media OS systemd preflight must never start unavailable external model retries."""
from pathlib import Path
import json

from empire_os.media_claim_verification import refresh_media_claim_verification
from tests.test_media_claim_verification import pack


def test_pending_packs_defer_without_model_network_or_source_calls(tmp_path,monkeypatch):
    source=tmp_path/"runtime/media_os/input/research_pack_candidates.json"
    source.parent.mkdir(parents=True,exist_ok=True)
    source.write_text(json.dumps({"candidates":[pack()]}))
    import empire_os.media_claim_verification as mod
    def forbid_gateway(*args,**kw):
        raise AssertionError("Media preflight attempted external LLM gateway")
    monkeypatch.setattr(mod,"LLMGateway",forbid_gateway)
    def forbid_source(*args,**kw):
        raise AssertionError("Media preflight attempted source-network request")
    result=refresh_media_claim_verification(
        tmp_path,defer_model_inference=True,probe=forbid_source)
    assert result["ok"] is True
    assert result["research_pack_count"]==1
    assert result["pending_pack_count_before_run"]==1
    assert result["processed_pack_count"]==0
    assert result["remaining_pack_count"]==1
    assert result["verified_claim_count"]==0
    assert result["script_ready_count"]==0
    assert result["external_reads_performed"] is False
    assert result["external_write_performed"] is False
    assert result["model_inference_deferred"] is True
    assert result["model_inference_attempted"] is False
    assert result["external_model_invocation_permitted"] is False
    assert result["public_publish_authorized"] is False
    assert result["execution_authority"]=="none"


def test_deferred_preflight_preserves_only_previously_confirmed_data(tmp_path):
    source=tmp_path/"runtime/media_os/input/research_pack_candidates.json"
    source.parent.mkdir(parents=True,exist_ok=True)
    source.write_text(json.dumps({"candidates":[pack()]}))
    def forbid_probe(*args,**kwargs):
        raise AssertionError("unexpected source GET")
    first=refresh_media_claim_verification(
        tmp_path,defer_model_inference=True,probe=forbid_probe)
    second=refresh_media_claim_verification(
        tmp_path,defer_model_inference=True,probe=forbid_probe)
    assert second["verified_claim_count"]==0
    assert second["pending_pack_count_before_run"]==1
    assert second["processed_pack_count"]==0
    assert second["input_fingerprint"]==first["input_fingerprint"]


def test_systemd_default_cli_never_requests_external_model():
    source=Path("scripts/refresh_media_claim_verification.py").read_text()
    unit=Path("deploy/systemd/empire-media-os.service").read_text()
    assert 'defer_model_inference=not args.allow_model_inference' in source
    assert '--allow-model-inference' in source
    assert 'refresh_media_claim_verification.py' in unit
    assert '--allow-model-inference' not in unit
