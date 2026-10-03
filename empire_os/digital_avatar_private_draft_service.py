"""Optional async grounded private-draft worker for Digital Avatar."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import time
from typing import Any, Callable

from empire_os.canonical_data_gateway import empiredb_gateway_from_environment
from empire_os.digital_avatar_evidence_pack import AvatarEvidenceResolver
from empire_os.digital_avatar_evidence_resolver import (
    build_production_avatar_evidence_resolver,
)
from empire_os.digital_avatar_private_draft_worker import (
    materialize_private_avatar_draft,
)
from empire_os.digital_avatar_response_draft import (
    GroundedAvatarDraftProvider,
    GroundedGatewayAvatarDraftProvider,
)
from empire_os.llm_gateway import LLMGateway


GUIDANCE_ROOT = Path(os.getenv(
    "EMPIRE_RECALL_GUIDANCE_ROOT",
    "/srv/empire_os/runtime/digital_avatar/guidance",
))
OBSERVATION_ROOT = Path(os.getenv(
    "EMPIRE_RECALL_OBSERVATION_ROOT",
    "/srv/empire_os/runtime/digital_avatar/meeting_observations",
))
DRAFT_ROOT = Path(os.getenv(
    "EMPIRE_AVATAR_PRIVATE_DRAFT_ROOT",
    "/srv/empire_os/runtime/digital_avatar/private_drafts",
))
STATUS_PATH = Path(os.getenv(
    "EMPIRE_AVATAR_PRIVATE_DRAFT_STATUS",
    "/srv/empire_os/runtime/digital_avatar/private_draft_status.json",
))
POLL_SECONDS = max(
    0.25,
    float(os.getenv("EMPIRE_AVATAR_PRIVATE_DRAFT_POLL_SECONDS", "1.0")),
)
MAX_ITEMS = max(
    1,
    min(
        int(os.getenv("EMPIRE_AVATAR_PRIVATE_DRAFT_MAX_PER_SCAN", "3")),
        20,
    ),
)


def _enabled(environ: dict[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    return str(
        env.get("EMPIRE_AVATAR_PRIVATE_DRAFT_ENABLED") or ""
    ).strip().lower() in {"1", "true", "yes", "on"}


def process_guidance_once(
    *,
    guidance_root: str | Path,
    draft_root: str | Path,
    evidence_resolver: AvatarEvidenceResolver,
    provider: GroundedAvatarDraftProvider,
    max_items: int = MAX_ITEMS,
) -> dict[str, Any]:
    root = Path(guidance_root)
    if not root.is_dir():
        return {
            "scanned": 0,
            "ready_for_human_review": 0,
            "blocked_evidence": 0,
            "blocked_specialist_context": 0,
            "blocked_validation": 0,
            "existing": 0,
            "failed": 0,
            "provider_calls": 0,
        }

    counts = {
        "scanned": 0,
        "ready_for_human_review": 0,
        "blocked_evidence": 0,
        "blocked_specialist_context": 0,
        "blocked_validation": 0,
        "existing": 0,
        "failed": 0,
        "provider_calls": 0,
    }
    for path in sorted(root.glob("*.json"))[: max(1, int(max_items))]:
        counts["scanned"] += 1
        try:
            result = materialize_private_avatar_draft(
                guidance_path=path,
                evidence_resolver=evidence_resolver,
                provider=provider,
                output_root=draft_root,
            )
            if result.status in counts:
                counts[result.status] += 1
            else:
                counts["failed"] += 1
            if result.provider_call_performed:
                counts["provider_calls"] += 1
        except Exception:
            counts["failed"] += 1
    return counts


def run_once(
    *,
    environ: dict[str, str] | None = None,
    gateway_factory: Callable[..., Any] = empiredb_gateway_from_environment,
    llm_factory: Callable[[], Any] = LLMGateway,
) -> dict[str, Any]:
    env = dict(os.environ if environ is None else environ)
    if not _enabled(env):
        return {
            "enabled": False,
            "scanned": 0,
            "provider_calls": 0,
            "execution_authority": "none",
            "transmission_performed": False,
            "speech_execution_allowed": False,
        }

    gateway = gateway_factory(env)
    resolver = build_production_avatar_evidence_resolver(
        observation_root=Path(
            env.get(
                "EMPIRE_RECALL_OBSERVATION_ROOT",
                str(OBSERVATION_ROOT),
            )
        ),
        gateway=gateway,
    )
    provider = GroundedGatewayAvatarDraftProvider(llm_factory())
    result = process_guidance_once(
        guidance_root=Path(
            env.get("EMPIRE_RECALL_GUIDANCE_ROOT", str(GUIDANCE_ROOT))
        ),
        draft_root=Path(
            env.get("EMPIRE_AVATAR_PRIVATE_DRAFT_ROOT", str(DRAFT_ROOT))
        ),
        evidence_resolver=resolver,
        provider=provider,
        max_items=max(
            1,
            min(
                int(
                    env.get(
                        "EMPIRE_AVATAR_PRIVATE_DRAFT_MAX_PER_SCAN",
                        str(MAX_ITEMS),
                    )
                ),
                20,
            ),
        ),
    )
    return {
        "enabled": True,
        **result,
        "execution_authority": "none",
        "transmission_performed": False,
        "speech_execution_allowed": False,
    }


def _write_status(payload: dict[str, Any]) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    state = {
        **payload,
        "mode": "COPILOT_PREVIEW",
        "private_to_owner": True,
        "execution_authority": "none",
        "transmission_performed": False,
        "speech_execution_allowed": False,
        "updated_at_epoch": time.time(),
    }
    tmp = STATUS_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    tmp.chmod(0o600)
    tmp.replace(STATUS_PATH)
    STATUS_PATH.chmod(0o600)


def run_forever() -> None:
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    while not stopping:
        try:
            result = run_once()
        except Exception as exc:
            result = {
                "enabled": _enabled(),
                "failed": 1,
                "error": f"{type(exc).__name__}:{str(exc)[:240]}",
                "execution_authority": "none",
                "transmission_performed": False,
                "speech_execution_allowed": False,
            }
        _write_status(result)
        if not stopping:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run_forever()
