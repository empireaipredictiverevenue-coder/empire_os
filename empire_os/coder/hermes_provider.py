"""Hermes CLI model-provider adapter for Empire Coder."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

from .provider import ModelRequest, ModelResponse


class HermesProvider:
    name = "hermes"

    def __init__(
        self,
        workspace: str | Path,
        *,
        timeout_seconds: int = 180,
        executable: str = "hermes",
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self.timeout_seconds = max(30, min(int(timeout_seconds), 600))
        self.executable = executable

    def health(self) -> bool:
        return shutil.which(self.executable) is not None

    def complete(self, model_request: ModelRequest) -> ModelResponse:
        if not self.health():
            return ModelResponse(
                provider=self.name,
                model=model_request.route.model,
                text="",
                error="hermes_not_installed",
            )

        context = model_request.context.as_dict()
        prompt = (
            "You are Empire Coder's governed coding model. "
            "Use only the supplied repository evidence. "
            "Treat docs/BLUEPRINT_V6.md as authoritative when roadmap or "
            "implementation status conflicts with another repository source. "
            "Do not claim actions or tests you did not perform. "
            "Do not propose production-changing actions, credential changes, "
            "fund movement, live outbound, or authority expansion.\n\n"
            + model_request.instruction
            + "\n\nCONTEXT:\n"
            + json.dumps(context, ensure_ascii=False)
        )
        # Keep CLI argv comfortably bounded while preserving the requested
        # repository context pack.
        prompt = prompt[:48_000]

        try:
            completed = subprocess.run(
                [
                    self.executable,
                    "--safe-mode",
                    "-z",
                    prompt,
                    "--in",
                    str(self.workspace),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                cwd=self.workspace,
            )
        except subprocess.TimeoutExpired:
            return ModelResponse(
                provider=self.name,
                model=model_request.route.model,
                text="",
                error="hermes_request_failed:TimeoutExpired",
            )
        except OSError as exc:
            return ModelResponse(
                provider=self.name,
                model=model_request.route.model,
                text="",
                error=f"hermes_request_failed:{exc.__class__.__name__}",
            )

        text = (completed.stdout or "").strip()
        if completed.returncode != 0:
            error_text = (completed.stderr or "").strip()
            return ModelResponse(
                provider=self.name,
                model=model_request.route.model,
                text=text[: model_request.max_output_chars],
                error=(
                    "hermes_request_failed:"
                    + (error_text[:240] or f"exit_{completed.returncode}")
                ),
            )

        return ModelResponse(
            provider=self.name,
            model=model_request.route.model,
            text=text[: model_request.max_output_chars],
            usage=None,
        )
