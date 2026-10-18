"""Opt-in, CPU-only, *offline* BGE embeddings for authorised Search Intelligence.

This is NOT imported or started by the running service. FastEmbed and its
model are optional dependencies in an isolated venv, never installed into the
production EmpireOS environment. Missing cached models fail closed: no fetch.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import subprocess
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
import math


MODEL_NAME = "BAAI/bge-small-en-v1.5"
EXPECTED_DIMENSIONS = 384
MODEL_FILE = "model_optimized.onnx"


class LocalEmbeddingUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class EmbeddingVector:
    values: tuple[float, ...]
    model_id: str
    source_receipt: str
    model_sha256: str


def _artifact_fingerprint(model_cache: Path) -> str:
    root = model_cache.expanduser().resolve(strict=True)
    candidates = []
    for file in root.rglob(MODEL_FILE):
        path = file.resolve(strict=True)
        if not path.is_relative_to(root):
            raise LocalEmbeddingUnavailable("embedding model artifact points outside cache")
        if path.stat().st_size > 1_000_000:
            candidates.append(path)
    unique = list(dict.fromkeys(candidates))
    if len(unique) != 1:
        raise LocalEmbeddingUnavailable("expected exactly one cached ONNX model artifact")
    digest = sha256()
    with unique[0].open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_offline_model(model_cache: Path):
    # The hub must remain offline even if callers accidentally pass a fresh cache.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise LocalEmbeddingUnavailable("fastembed not installed in this runtime") from exc
    try:
        return TextEmbedding(
            model_name=MODEL_NAME,
            cache_dir=str(model_cache),
            threads=2,
            local_files_only=True,
        )
    except Exception as exc:
        raise LocalEmbeddingUnavailable("local cached embedding model unavailable") from exc


class IsolatedFastEmbedProcess:
    """Run FastEmbed using a separate interpreter without Empire imports.

    No shell, no inherited environment secrets, no background daemon.
    """

    def __init__(self, *, model_cache: Path, python_executable: str | Path) -> None:
        self.cache = Path(model_cache).expanduser().resolve(strict=True)
        python = Path(python_executable).expanduser()
        if not python.is_absolute():
            raise LocalEmbeddingUnavailable("isolated Python must be an absolute path")
        # Keep the venv symlink path: resolving it would discard sys.prefix
        # and start a bare interpreter without installed FastEmbed.
        python.resolve(strict=True)
        if not python.is_file() or not os.access(python, os.X_OK):
            raise LocalEmbeddingUnavailable("isolated Python executable unavailable")
        self.python_executable = python
        self.worker = (Path(__file__).resolve().parents[2] / "scripts"
                       / "_standalone_embed_worker.py")
        if not self.worker.is_file():
            raise LocalEmbeddingUnavailable("standalone embedding worker unavailable")

    def embed(self, texts: Sequence[str], *, batch_size: int = 16,
              parallel: None = None) -> list[list[float]]:
        payload = json.dumps({"texts": list(texts)}, separators=(",", ":"))
        try:
            completed = subprocess.run(
                [str(self.python_executable), str(self.worker), str(self.cache)],
                input=payload, text=True, capture_output=True, check=False,
                timeout=90,
                env={
                    "PATH": "/usr/bin:/bin",
                    "HOME": str(Path.home()),
                    "HF_HUB_OFFLINE": "1",
                    "HF_HUB_DISABLE_TELEMETRY": "1",
                    "OPENBLAS_NUM_THREADS": "2",
                    "OMP_NUM_THREADS": "2",
                },
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LocalEmbeddingUnavailable("isolated local embed worker unavailable") from exc
        if completed.returncode != 0:
            raise LocalEmbeddingUnavailable("isolated embed worker returned failure")
        try:
            document = json.loads(completed.stdout)
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise LocalEmbeddingUnavailable("invalid isolated embedding response") from exc
        vectors = document.get("vectors") if isinstance(document, dict) else None
        if not isinstance(vectors, list):
            raise LocalEmbeddingUnavailable("isolated embedding vectors missing")
        return vectors


class LocalSemanticEmbedder:
    def __init__(
        self,
        *,
        model_cache: str | Path,
        model_loader: Callable[[Path], Any] = _load_offline_model,
    ) -> None:
        self.cache = Path(model_cache).expanduser()
        self.model_sha256 = _artifact_fingerprint(self.cache)
        self.model_id = f"fastembed:{MODEL_NAME}:sha256:{self.model_sha256}"
        self._model = model_loader(self.cache)

    def embed(self, texts: Sequence[str]) -> tuple[EmbeddingVector, ...]:
        if not isinstance(texts, (list, tuple)) or len(texts) > 100:
            raise LocalEmbeddingUnavailable("embedding batch limited to 100 texts")
        if not texts:
            return ()
        if any(not isinstance(t, str) or not t.strip() or len(t) > 1500 for t in texts):
            raise LocalEmbeddingUnavailable("texts must be 1..1500 characters")
        try:
            vectors = list(self._model.embed(texts, batch_size=16, parallel=None))
        except Exception as exc:
            raise LocalEmbeddingUnavailable("local embedding inference failed") from exc
        if len(vectors) != len(texts):
            raise LocalEmbeddingUnavailable("embedding model returned wrong vector count")
        outputs = []
        for text, vector in zip(texts, vectors):
            try:
                nums = tuple(float(value) for value in vector)
            except (TypeError, ValueError) as exc:
                raise LocalEmbeddingUnavailable("embedding vector is not numeric") from exc
            if (len(nums) != EXPECTED_DIMENSIONS or
                    not all(math.isfinite(value) for value in nums) or
                    sum(value * value for value in nums) < 1e-10):
                raise LocalEmbeddingUnavailable("embedding vector invalid shape or norm")
            receipt = sha256((
                self.model_id + "\n" + text + "\n" +
                ",".join(format(v, ".8g") for v in nums)
            ).encode()).hexdigest()
            outputs.append(EmbeddingVector(
                values=nums,
                model_id=self.model_id,
                source_receipt="local-model-embedding-sha256:" + receipt,
                model_sha256=self.model_sha256,
            ))
        return tuple(outputs)


def attach_keyword_embeddings(
    records: Sequence[Mapping[str, Any]],
    encoder: LocalSemanticEmbedder,
) -> list[dict[str, Any]]:
    """Preserve original observed evidence and add locally derived vectors."""
    if len(records) > 100:
        raise LocalEmbeddingUnavailable("keyword embedding batch limited to 100")
    if not records:
        return []
    for row in records:
        if not isinstance(row, Mapping) or row.get("embedding") is not None:
            raise LocalEmbeddingUnavailable("keyword records must not contain prior embedding")
        if not row.get("evidence_refs"):
            raise LocalEmbeddingUnavailable("source evidence required for keyword embedding")
    vectors = encoder.embed([str(row.get("keyword") or "") for row in records])
    result = []
    for row, vector in zip(records, vectors):
        result.append({
            **row,
            "embedding": list(vector.values),
            "embedding_model": vector.model_id,
            "embedding_evidence_ref": vector.source_receipt,
        })
    return result


def attach_page_embeddings(
    records: Sequence[Mapping[str, Any]],
    encoder: LocalSemanticEmbedder,
) -> list[dict[str, Any]]:
    """Embed only first-party, metadata-verified live page records."""
    if len(records) > 100:
        raise LocalEmbeddingUnavailable("page embedding batch limited to 100")
    if not records:
        return []
    for row in records:
        if not isinstance(row, Mapping) or row.get("embedding") is not None:
            raise LocalEmbeddingUnavailable("page records must not contain prior embedding")
        if not row.get("eligible_for_local_topic_review") or not row.get("evidence_refs"):
            raise LocalEmbeddingUnavailable("only evidenced eligible owned pages may be embedded")
    vectors = encoder.embed([
        " ".join(str(row.get(field) or "") for field in ("title", "h1", "topic"))
        for row in records
    ])
    return [{
        **row,
        "embedding": list(vector.values),
        "embedding_model": vector.model_id,
        "embedding_evidence_ref": vector.source_receipt,
    } for row, vector in zip(records, vectors)]
