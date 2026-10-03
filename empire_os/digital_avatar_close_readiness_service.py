"""Private canonical close-readiness enrichment for Digital Avatar meetings."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import signal
import time
from typing import Any, Callable

from empire_os.canonical_data_gateway import (
    DataGatewayUnavailable,
    empiredb_gateway_from_environment,
)
from empire_os.digital_avatar_close_readiness import (
    assess_canonical_avatar_close_readiness,
)
from empire_os.digital_avatar_evidence_resolver import (
    build_canonical_commercial_evidence_resolver,
)
from empire_os.recall_meeting_state_snapshot import (
    materialize_recall_meeting_state_snapshot,
)
from empire_os.recall_shadow_session import (
    RecallShadowSessionManifest,
    load_recall_shadow_session,
)


SESSION_ROOT = Path(os.getenv(
    "EMPIRE_RECALL_SESSION_ROOT",
    "/srv/empire_os/runtime/digital_avatar/sessions",
))
GUIDANCE_ROOT = Path(os.getenv(
    "EMPIRE_RECALL_GUIDANCE_ROOT",
    "/srv/empire_os/runtime/digital_avatar/guidance",
))
RUNTIME_STATE_ROOT = Path(os.getenv(
    "EMPIRE_RECALL_RUNTIME_STATE_ROOT",
    "/srv/empire_os/runtime/digital_avatar/runtime_state",
))
CLOSE_READINESS_ROOT = Path(os.getenv(
    "EMPIRE_AVATAR_CLOSE_READINESS_ROOT",
    "/srv/empire_os/runtime/digital_avatar/close_readiness",
))
MEETING_STATE_ROOT = Path(os.getenv(
    "EMPIRE_RECALL_MEETING_STATE_ROOT",
    "/srv/empire_os/runtime/digital_avatar/meeting_state",
))
STATUS_PATH = Path(os.getenv(
    "EMPIRE_AVATAR_CLOSE_READINESS_STATUS",
    "/srv/empire_os/runtime/digital_avatar/close_readiness_status.json",
))
POLL_SECONDS = max(
    0.5,
    float(os.getenv("EMPIRE_AVATAR_CLOSE_READINESS_POLL_SECONDS", "2.0")),
)
MAX_SESSIONS = max(
    1,
    min(
        int(os.getenv("EMPIRE_AVATAR_CLOSE_READINESS_MAX_SESSIONS", "25")),
        250,
    ),
)


@dataclass(frozen=True)
class AvatarCloseReadinessSnapshot:
    meeting_id: str
    avatar_id: str
    commercial_envelope_configured: bool
    canonical_grounding_attempted: bool
    canonical_grounding_available: bool
    policy_eligible: bool
    canonical_grounded: bool
    conversational_close_ready: bool
    binding_execution_allowed: bool
    human_takeover_required: bool
    discount_bps: int
    canonical_evidence_refs: tuple[str, ...]
    blockers: tuple[str, ...]
    mode: str = "OBSERVE"
    private_to_owner: bool = True
    speech_execution: bool = False
    commercial_execution: bool = False
    payment_execution: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    tmp = path.parent / f".{path.name}.{os.getpid()}.tmp"
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    finally:
        if tmp.exists():
            tmp.unlink()


def _unconfigured(
    manifest: RecallShadowSessionManifest,
) -> AvatarCloseReadinessSnapshot:
    return AvatarCloseReadinessSnapshot(
        meeting_id=manifest.session.meeting_id,
        avatar_id=manifest.identity.avatar_id,
        commercial_envelope_configured=False,
        canonical_grounding_attempted=False,
        canonical_grounding_available=False,
        policy_eligible=False,
        canonical_grounded=False,
        conversational_close_ready=False,
        binding_execution_allowed=False,
        human_takeover_required=False,
        discount_bps=0,
        canonical_evidence_refs=(),
        blockers=("commercial_close_envelope_not_configured",),
    )


def _canonical_unavailable(
    manifest: RecallShadowSessionManifest,
) -> AvatarCloseReadinessSnapshot:
    return AvatarCloseReadinessSnapshot(
        meeting_id=manifest.session.meeting_id,
        avatar_id=manifest.identity.avatar_id,
        commercial_envelope_configured=True,
        canonical_grounding_attempted=True,
        canonical_grounding_available=False,
        policy_eligible=False,
        canonical_grounded=False,
        conversational_close_ready=False,
        binding_execution_allowed=False,
        human_takeover_required=True,
        discount_bps=0,
        canonical_evidence_refs=(),
        blockers=("canonical_commercial_evidence_unavailable",),
    )


def build_close_readiness_snapshot(
    *,
    manifest: RecallShadowSessionManifest,
    gateway: Any | None,
) -> AvatarCloseReadinessSnapshot:
    manifest.validate()
    if manifest.commercial_policy is None or manifest.close_proposal is None:
        return _unconfigured(manifest)
    if gateway is None:
        return _canonical_unavailable(manifest)

    resolver = build_canonical_commercial_evidence_resolver(gateway)
    result = assess_canonical_avatar_close_readiness(
        policy=manifest.commercial_policy,
        proposal=manifest.close_proposal,
        resolver=resolver,
    )
    return AvatarCloseReadinessSnapshot(
        meeting_id=manifest.session.meeting_id,
        avatar_id=manifest.identity.avatar_id,
        commercial_envelope_configured=True,
        canonical_grounding_attempted=True,
        canonical_grounding_available=True,
        policy_eligible=result.policy_eligible,
        canonical_grounded=result.canonical_grounded,
        conversational_close_ready=result.conversational_close_ready,
        binding_execution_allowed=False,
        human_takeover_required=result.human_takeover_required,
        discount_bps=result.discount_bps,
        canonical_evidence_refs=result.canonical_evidence_refs,
        blockers=result.blockers,
    )


def process_close_readiness_once(
    *,
    session_root: str | Path,
    output_root: str | Path,
    guidance_root: str | Path,
    runtime_state_root: str | Path,
    meeting_state_root: str | Path,
    gateway_factory: Callable[..., Any] = empiredb_gateway_from_environment,
    environ: dict[str, str] | None = None,
    max_sessions: int = MAX_SESSIONS,
) -> dict[str, Any]:
    root = Path(session_root)
    if not root.is_dir():
        return {
            "scanned": 0,
            "configured": 0,
            "ready": 0,
            "takeover_required": 0,
            "canonical_unavailable": 0,
            "failed": 0,
            "meeting_state_refreshed": 0,
            "execution_authority": "none",
        }

    counts = {
        "scanned": 0,
        "configured": 0,
        "ready": 0,
        "takeover_required": 0,
        "canonical_unavailable": 0,
        "failed": 0,
        "meeting_state_refreshed": 0,
    }
    gateway: Any | None = None
    gateway_attempted = False
    source_env = dict(os.environ if environ is None else environ)

    for path in sorted(root.glob("*.json"))[: max(1, int(max_sessions))]:
        counts["scanned"] += 1
        try:
            manifest = load_recall_shadow_session(path)
            if (
                manifest.commercial_policy is not None
                and manifest.close_proposal is not None
            ):
                counts["configured"] += 1
                if not gateway_attempted:
                    gateway_attempted = True
                    try:
                        gateway = gateway_factory(source_env)
                    except DataGatewayUnavailable:
                        gateway = None
            snapshot = build_close_readiness_snapshot(
                manifest=manifest,
                gateway=gateway,
            )
            if snapshot.conversational_close_ready:
                counts["ready"] += 1
            if snapshot.human_takeover_required:
                counts["takeover_required"] += 1
            if (
                snapshot.commercial_envelope_configured
                and not snapshot.canonical_grounding_available
            ):
                counts["canonical_unavailable"] += 1

            target = Path(output_root) / f"{snapshot.meeting_id}.json"
            _atomic_json(target, snapshot.as_dict())

            try:
                materialize_recall_meeting_state_snapshot(
                    meeting_id=snapshot.meeting_id,
                    guidance_root=guidance_root,
                    runtime_state_root=runtime_state_root,
                    close_readiness_root=output_root,
                    output_root=meeting_state_root,
                )
                counts["meeting_state_refreshed"] += 1
            except ValueError as exc:
                if str(exc) != "meeting state unavailable":
                    raise
        except Exception:
            counts["failed"] += 1

    return {
        **counts,
        "private_to_owner": True,
        "speech_execution": False,
        "commercial_execution": False,
        "payment_execution": False,
        "execution_authority": "none",
    }


def _write_status(payload: dict[str, Any]) -> None:
    state = {
        **payload,
        "mode": "OBSERVE",
        "updated_at_epoch": time.time(),
    }
    _atomic_json(STATUS_PATH, state)


def run_forever() -> None:
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    while not stopping:
        result = process_close_readiness_once(
            session_root=SESSION_ROOT,
            output_root=CLOSE_READINESS_ROOT,
            guidance_root=GUIDANCE_ROOT,
            runtime_state_root=RUNTIME_STATE_ROOT,
            meeting_state_root=MEETING_STATE_ROOT,
        )
        _write_status(result)
        if not stopping:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run_forever()
