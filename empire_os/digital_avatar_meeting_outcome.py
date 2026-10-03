"""Evidence-only post-meeting packet for Digital Avatar meetings."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import signal
import time
from typing import Any, Iterable, Mapping

from empire_os.recall_shadow_session import (
    RecallShadowSessionManifest,
    load_recall_shadow_session,
)


SESSION_ROOT = Path(os.getenv(
    "EMPIRE_RECALL_SESSION_ROOT",
    "/srv/empire_os/runtime/digital_avatar/sessions",
))
OBSERVATION_ROOT = Path(os.getenv(
    "EMPIRE_RECALL_OBSERVATION_ROOT",
    "/srv/empire_os/runtime/digital_avatar/observations",
))
MEETING_STATE_ROOT = Path(os.getenv(
    "EMPIRE_RECALL_MEETING_STATE_ROOT",
    "/srv/empire_os/runtime/digital_avatar/meeting_state",
))
OUTCOME_ROOT = Path(os.getenv(
    "EMPIRE_AVATAR_MEETING_OUTCOME_ROOT",
    "/srv/empire_os/runtime/digital_avatar/meeting_outcomes",
))
STATUS_PATH = Path(os.getenv(
    "EMPIRE_AVATAR_MEETING_OUTCOME_STATUS",
    "/srv/empire_os/runtime/digital_avatar/meeting_outcome_status.json",
))
POLL_SECONDS = max(
    0.5,
    float(os.getenv("EMPIRE_AVATAR_MEETING_OUTCOME_POLL_SECONDS", "2.0")),
)
MAX_MEETINGS = max(
    1,
    min(
        int(os.getenv("EMPIRE_AVATAR_MEETING_OUTCOME_MAX_MEETINGS", "50")),
        500,
    ),
)


@dataclass(frozen=True)
class AvatarMeetingOutcomePacket:
    meeting_id: str
    avatar_id: str
    account_name: str
    conversation_id: str | None
    opportunity_id: str | None
    lifecycle_status: str | None
    terminal: bool
    fatal: bool
    buyer_utterance_count: int
    buyer_evidence_refs: tuple[str, ...]
    verification_refs: tuple[str, ...]
    close_ready_at_end: bool
    human_takeover_required: bool
    follow_up_review_recommended: bool
    conversation_bridge_recommended: bool
    predictive_revenue_refresh_recommended: bool
    verified_commercial_outcome: bool = False
    revenue_recognized: bool = False
    cortex_customer_label_eligible: bool = False
    automatic_follow_up_send_allowed: bool = False
    private_to_owner: bool = True
    speech_execution: bool = False
    commercial_execution: bool = False
    payment_execution: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
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


def _buyer_observations(
    *,
    meeting_id: str,
    observation_root: str | Path,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    evidence_refs: list[str] = []
    verification_refs: list[str] = []
    root = Path(observation_root)
    if not root.is_dir():
        return (), ()

    for path in sorted(root.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, Mapping):
            continue
        if str(raw.get("meeting_id") or "") != meeting_id:
            continue
        observation = raw.get("observation")
        if not isinstance(observation, Mapping):
            continue
        if str(observation.get("speaker_role") or "").lower() != "buyer":
            continue
        if observation.get("is_final") is not True:
            continue
        if not str(observation.get("text") or "").strip():
            continue
        evidence_ref = str(observation.get("evidence_ref") or "").strip()
        verification_ref = str(raw.get("verification_ref") or "").strip()
        if not evidence_ref or not verification_ref:
            continue
        evidence_refs.append(evidence_ref)
        verification_refs.append(verification_ref)

    return (
        tuple(dict.fromkeys(evidence_refs)),
        tuple(dict.fromkeys(verification_refs)),
    )


def build_avatar_meeting_outcome(
    *,
    manifest: RecallShadowSessionManifest,
    meeting_state: Mapping[str, Any],
    buyer_evidence_refs: Iterable[str] = (),
    verification_refs: Iterable[str] = (),
) -> AvatarMeetingOutcomePacket:
    manifest.validate()
    if meeting_state.get("meeting_id") != manifest.session.meeting_id:
        raise ValueError("meeting outcome state/manifest identity mismatch")
    if str(meeting_state.get("avatar_id") or "") != manifest.identity.avatar_id:
        raise ValueError("meeting outcome avatar identity mismatch")
    if meeting_state.get("private_to_owner") is not True:
        raise ValueError("meeting outcome requires private meeting state")
    for field in ("speech_execution", "commercial_execution"):
        if meeting_state.get(field) is not False:
            raise ValueError(
                f"meeting outcome source {field} invariant violated"
            )
    if str(meeting_state.get("execution_authority") or "").lower() != "none":
        raise ValueError("meeting outcome source grants forbidden authority")

    buyer_refs = tuple(dict.fromkeys(
        str(value).strip()
        for value in buyer_evidence_refs
        if str(value).strip()
    ))
    verification = tuple(dict.fromkeys(
        str(value).strip()
        for value in verification_refs
        if str(value).strip()
    ))
    terminal = meeting_state.get("terminal") is True
    fatal = meeting_state.get("fatal") is True
    buyer_count = len(buyer_refs)
    close_ready = (
        meeting_state.get("conversational_close_ready") is True
    )
    takeover = meeting_state.get("human_takeover_required") is True

    follow_up = terminal and not fatal and buyer_count > 0
    conversation_bridge = (
        follow_up and bool(str(manifest.conversation_id or "").strip())
    )
    predictive_refresh = (
        follow_up and bool(str(manifest.opportunity_id or "").strip())
    )

    return AvatarMeetingOutcomePacket(
        meeting_id=manifest.session.meeting_id,
        avatar_id=manifest.identity.avatar_id,
        account_name=manifest.account_name,
        conversation_id=manifest.conversation_id,
        opportunity_id=manifest.opportunity_id,
        lifecycle_status=(
            str(meeting_state.get("lifecycle_status") or "").strip()
            or None
        ),
        terminal=terminal,
        fatal=fatal,
        buyer_utterance_count=buyer_count,
        buyer_evidence_refs=buyer_refs,
        verification_refs=verification,
        close_ready_at_end=close_ready,
        human_takeover_required=takeover,
        follow_up_review_recommended=follow_up,
        conversation_bridge_recommended=conversation_bridge,
        predictive_revenue_refresh_recommended=predictive_refresh,
    )


def process_meeting_outcomes_once(
    *,
    session_root: str | Path,
    observation_root: str | Path,
    meeting_state_root: str | Path,
    output_root: str | Path,
    max_meetings: int = MAX_MEETINGS,
) -> dict[str, Any]:
    states = Path(meeting_state_root)
    if not states.is_dir():
        return {
            "scanned": 0,
            "terminal": 0,
            "follow_up_review": 0,
            "conversation_bridge": 0,
            "predictive_refresh": 0,
            "failed": 0,
            "execution_authority": "none",
        }

    counts = {
        "scanned": 0,
        "terminal": 0,
        "follow_up_review": 0,
        "conversation_bridge": 0,
        "predictive_refresh": 0,
        "failed": 0,
    }
    for path in sorted(states.glob("*.json"))[: max(1, int(max_meetings))]:
        counts["scanned"] += 1
        meeting_id = path.stem
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(state, Mapping):
                raise ValueError("meeting state must be object")
            manifest = load_recall_shadow_session(
                Path(session_root) / f"{meeting_id}.json"
            )
            evidence, verification = _buyer_observations(
                meeting_id=meeting_id,
                observation_root=observation_root,
            )
            packet = build_avatar_meeting_outcome(
                manifest=manifest,
                meeting_state=state,
                buyer_evidence_refs=evidence,
                verification_refs=verification,
            )
            _atomic_json(
                Path(output_root) / f"{meeting_id}.json",
                packet.as_dict(),
            )
            if packet.terminal:
                counts["terminal"] += 1
            if packet.follow_up_review_recommended:
                counts["follow_up_review"] += 1
            if packet.conversation_bridge_recommended:
                counts["conversation_bridge"] += 1
            if packet.predictive_revenue_refresh_recommended:
                counts["predictive_refresh"] += 1
        except Exception:
            counts["failed"] += 1

    return {
        **counts,
        "verified_commercial_outcomes_written": 0,
        "revenue_recognition_written": False,
        "cortex_customer_labels_written": 0,
        "automatic_follow_up_send": False,
        "execution_authority": "none",
    }


def _write_status(payload: Mapping[str, Any]) -> None:
    _atomic_json(STATUS_PATH, {
        **dict(payload),
        "mode": "OBSERVE",
        "updated_at_epoch": time.time(),
    })


def run_forever() -> None:
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    while not stopping:
        result = process_meeting_outcomes_once(
            session_root=SESSION_ROOT,
            observation_root=OBSERVATION_ROOT,
            meeting_state_root=MEETING_STATE_ROOT,
            output_root=OUTCOME_ROOT,
        )
        _write_status(result)
        if not stopping:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run_forever()
