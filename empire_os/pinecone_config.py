#!/usr/bin/env python3
"""
pinecone_config.py — single source of truth for Pinecone configuration.

All Pinecone clients and intel functions read from here. No hardcoded paths,
no scattered .env reads, no silent fallbacks.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


ENV_PATH = Path("/root/empire_os/.env")


class PineconeConfigError(Exception):
    """Configuration is missing or invalid (raised at boot)."""


@dataclass(frozen=True)
class PinconeConfig:
    """Immutable Pinecone configuration. Construct once via `load()`."""

    api_key: str
    index: str
    cloud: str
    region: str
    embed_model: str
    dimension: int
    field_map_text: str = "text"

    def redact_key(self) -> str:
        """Return a log-safe view of the API key."""
        if len(self.api_key) <= 12:
            return self.api_key[:4] + "..."
        return f"{self.api_key[:6]}...{self.api_key[-4:]}"


# Embed model → dimension. The MCP server enforces this contract.
EMBED_MODEL_DIMS: dict[str, Optional[int]] = {
    "llama-text-embed-v2": 1024,
    "multilingual-e5-large": 1024,
    "pinecone-sparse-english-v0": None,  # sparse, no fixed dim
}


def _read_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict. No shell expansion, no variable interpolation."""
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _get(name: str, env_file: dict[str, str], default: Optional[str] = None) -> Optional[str]:
    """env var → .env → default. None only if default is None and both empty."""
    val = os.environ.get(name)
    if val:
        return val.strip().strip('"').strip("'")
    val = env_file.get(name)
    if val:
        return val.strip().strip('"').strip("'")
    return default


def load() -> PinconeConfig:
    """Load config from env + .env. Raises PineconeConfigError on bad config."""
    env_file = _read_env_file(ENV_PATH)

    api_key = _get("PINECONE_API_KEY", env_file)
    if not api_key:
        raise PineconeConfigError(
            "PINECONE_API_KEY missing. Set it in env or /root/empire_os/.env"
        )
    if not re.match(r"^pcsk_[A-Za-z0-9_-]+$", api_key):
        raise PineconeConfigError(
            f"PINECONE_API_KEY has unexpected shape (len={len(api_key)}). "
            "Pinecone serverless keys start with 'pcsk_'."
        )

    embed_model = _get("PINECONE_EMBED", env_file, "llama-text-embed-v2")
    if embed_model not in EMBED_MODEL_DIMS:
        raise PineconeConfigError(
            f"PINECONE_EMBED={embed_model!r} not recognized. "
            f"Supported: {sorted(EMBED_MODEL_DIMS)}"
        )
    dim_env = _get("PINECONE_DIM", env_file)
    if dim_env:
        dimension = int(dim_env)
    else:
        dimension = EMBED_MODEL_DIMS[embed_model]
        if dimension is None:
            raise PineconeConfigError(
                f"embed model {embed_model!r} is sparse — set PINECONE_DIM explicitly"
            )

    return PinconeConfig(
        api_key=api_key,
        index=_get("PINECONE_INDEX", env_file, "empire-leads") or "empire-leads",
        cloud=_get("PINECONE_CLOUD", env_file, "aws") or "aws",
        region=_get("PINECONE_REGION", env_file, "us-east-1") or "us-east-1",
        embed_model=embed_model,
        dimension=dimension,
    )
