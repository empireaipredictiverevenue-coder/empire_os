"""Offline embedding runtime: fixed model, receipt provenance, strict isolation."""
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from empire_os.search_intelligence.local_embedding_runtime import (
    LocalSemanticEmbedder,
    IsolatedFastEmbedProcess,
    LocalEmbeddingUnavailable,
    _artifact_fingerprint,
    attach_keyword_embeddings,
    attach_page_embeddings,
)
from scripts.benchmark_local_semantic import run_semantic_benchmark


@pytest.fixture
def cache(tmp_path):
    cache = tmp_path / "local-model-cache" / "snapshots" / "model"
    cache.mkdir(parents=True)
    # Synthetic ONNX-like bytes only for receipt hashing; not executable model.
    (cache / "model_optimized.onnx").write_bytes(b"x" * 1_100_000)
    return cache.parent.parent


class DeterministicModel:
    def embed(self, texts, *, batch_size, parallel):
        assert batch_size == 16
        assert parallel is None
        output = []
        for text in texts:
            values = [0.0] * 384
            values[0 if "roof" in text.lower() else 1] = 1.0
            output.append(values)
        return output


def test_local_embeddings_require_real_model_artifact_and_record_fingerprint(cache):
    encoder = LocalSemanticEmbedder(
        model_cache=cache, model_loader=lambda _: DeterministicModel(),
    )
    vecs = encoder.embed(["roofing estimates", "solar installation"])
    assert len(vecs) == 2
    assert all(len(x.values) == 384 for x in vecs)
    assert vecs[0].values[0] == 1
    assert vecs[1].values[1] == 1
    assert vecs[0].source_receipt.startswith("local-model-embedding-sha256:")
    assert encoder.model_sha256 == _artifact_fingerprint(cache)
    assert encoder.model_id.endswith(encoder.model_sha256)
    assert encoder.embed(["roofing estimates"])[0] == vecs[0]


def test_keyword_and_page_embeddings_preserve_original_source(cache):
    encoder = LocalSemanticEmbedder(
        model_cache=cache, model_loader=lambda _: DeterministicModel(),
    )
    source = [{"keyword": "roofing quote", "evidence_refs": ["gsc:real-row"]}]
    embedded = attach_keyword_embeddings(source, encoder)
    assert source[0].get("embedding") is None
    assert embedded[0]["evidence_refs"] == ["gsc:real-row"]
    assert embedded[0]["embedding_model"] == encoder.model_id
    assert embedded[0]["embedding_evidence_ref"]
    assert len(embedded[0]["embedding"]) == 384
    pages = [{
        "title": "roofing quotes", "h1": "commercial roofing",
        "topic": "roofing", "eligible_for_local_topic_review": True,
        "evidence_refs": ["owned-html:receipt"],
    }]
    page_result = attach_page_embeddings(pages, encoder)
    assert page_result[0]["evidence_refs"] == ["owned-html:receipt"]
    assert page_result[0]["embedding_model"] == encoder.model_id


def test_unverified_page_and_keyword_never_get_vectors(cache):
    encoder = LocalSemanticEmbedder(
        model_cache=cache, model_loader=lambda _: DeterministicModel(),
    )
    with pytest.raises(LocalEmbeddingUnavailable, match="source evidence"):
        attach_keyword_embeddings(
            [{"keyword": "roofing", "evidence_refs": []}], encoder
        )
    with pytest.raises(LocalEmbeddingUnavailable, match="only evidenced"):
        attach_page_embeddings(
            [{"title": "roofing", "eligible_for_local_topic_review": False,
              "evidence_refs": ["claimed"]}], encoder
        )


def test_missing_model_cache_fails_before_loader_is_invoked(tmp_path):
    with pytest.raises((LocalEmbeddingUnavailable, FileNotFoundError)):
        LocalSemanticEmbedder(model_cache=tmp_path / "missing")


@pytest.mark.parametrize("bad_texts", [[123], [""], ["x" * 1501], ["text"] * 101])
def test_invalid_embedding_batch_rejected(cache, bad_texts):
    encoder = LocalSemanticEmbedder(
        model_cache=cache, model_loader=lambda _: DeterministicModel(),
    )
    with pytest.raises(LocalEmbeddingUnavailable):
        encoder.embed(bad_texts)


def test_subprocess_embedding_is_no_shell_and_no_env_secret_leak(
    tmp_path, cache, monkeypatch,
):
    python = tmp_path / "venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o755)
    captured = {}
    def fake_run(args, **kwargs):
        captured.update(args=args, **kwargs)
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"vectors": [[1.0] + [0.0] * 383]}),
            stderr="",
        )
    monkeypatch.setattr(
        "empire_os.search_intelligence.local_embedding_runtime.subprocess.run",
        fake_run,
    )
    model = IsolatedFastEmbedProcess(model_cache=cache, python_executable=python)
    vectors = model.embed(["roofing quote"])
    assert len(vectors[0]) == 384
    assert captured["args"][0] == str(python)  # preserve venv interpreter path
    assert captured["args"][1].endswith("_standalone_embed_worker.py")
    assert captured["check"] is False
    assert captured["timeout"] == 90
    assert captured["env"]["HF_HUB_OFFLINE"] == "1"
    assert "SECRET_TOKEN" not in captured["env"]
    assert "shell" not in captured


def test_subprocess_refuses_worker_failure_without_stdout_leak(
    tmp_path, cache, monkeypatch,
):
    python = tmp_path / "python"
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o755)
    monkeypatch.setattr(
        "empire_os.search_intelligence.local_embedding_runtime.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=2, stdout="", stderr="auth token ignored"
        ),
    )
    model = IsolatedFastEmbedProcess(model_cache=cache, python_executable=python)
    with pytest.raises(LocalEmbeddingUnavailable, match="returned failure"):
        model.embed(["roofing quote"])


def test_curated_benchmark_is_not_claimed_as_real_search_volume(cache):
    encoder = LocalSemanticEmbedder(
        model_cache=cache, model_loader=lambda _: DeterministicModel(),
    )
    corpus = [{
        "keyword": "roofing quotes",
        "cluster_key": "roofing", "product_key": "roofing",
        "icp_key": "roofer", "intent_class": "commercial",
        "funnel_stage": "conversion", "cta_key": "enquiry",
        "evidence_refs": ["owned:roof"],
    }, {
        "keyword": "solar installers",
        "cluster_key": "solar", "product_key": "solar",
        "icp_key": "installer", "intent_class": "commercial",
        "funnel_stage": "conversion", "cta_key": "enquiry",
        "evidence_refs": ["owned:solar"],
    }]
    cases = (
        ("roofing quote", "roofing"),
        ("roofing work", "roofing"),
        ("solar installation", "solar"),
        ("solar leads", "solar"),
    )
    result = run_semantic_benchmark(corpus, encoder, cases=cases)
    assert result["evaluation_sample_count"] == 4
    assert result["hybrid"]["top1_accuracy"] == 1.0
    assert result["evaluation_labels_are_real_user_queries"] is False
    assert result["verified_google_ranking"] is False
    assert result["revenue_verified"] is False
    assert result["external_paid_api_calls"] == 0
