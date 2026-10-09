"""Public Vonage gateway for the self-hosted Empire Voice Lab."""
from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any
from urllib.parse import quote, urlencode, urlparse, urlunparse

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

from empire_os.decision_judge import SCHEMA_VERSION as DECISION_JUDGE_SCHEMA_VERSION
from empire_os.sb import request_json
from empire_os.voice_routing_policy import switchboard_status
from empire_os.voice_lab import EmpireVoiceLab, VoiceLabConfig, VoiceTurnDetector


router = APIRouter(prefix="/v1/voice-lab", tags=["voice-lab"])
_RUNTIME: EmpireVoiceLab | None = None


def _runtime() -> EmpireVoiceLab:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = EmpireVoiceLab()
    return _RUNTIME


def _public_base() -> str:
    return os.getenv(
        "EMPIRE_PUBLIC_BASE_URL",
        "https://empire-ai.co.uk",
    ).rstrip("/")


def _webhook_token() -> str:
    return os.getenv("EMPIRE_VONAGE_WEBHOOK_TOKEN", "").strip()


def _ws_token() -> str:
    return os.getenv("EMPIRE_VOICE_WS_TOKEN", "").strip()


def _require_webhook_token(value: str) -> None:
    configured = _webhook_token()
    if not configured or value != configured:
        raise HTTPException(status_code=401, detail="voice_webhook_unauthorized")


def _ws_url(intent_id: str, prospect_id: str, call_id: str = "") -> str:
    parsed = urlparse(_public_base())
    scheme = "wss" if parsed.scheme == "https" else "ws"
    query = urlencode({
        "intent_id": intent_id,
        "prospect_id": prospect_id,
        "call_id": call_id,
    })
    return urlunparse((
        scheme,
        parsed.netloc,
        "/v1/voice-lab/vonage/socket",
        "",
        query,
        "",
    ))


def _prospect_context(prospect_id: str) -> dict[str, str]:
    if not prospect_id:
        return {}
    rows = request_json(
        "GET",
        "/rest/v1/prospects?"
        + urlencode({
            "select": "id,business_name,niche,metro",
            "id": f"eq.{prospect_id}",
            "limit": 1,
        }),
    ) or []
    if not rows:
        return {}
    row = rows[0]
    return {
        "business_name": str(row.get("business_name") or "")[:120],
        "niche": str(row.get("niche") or "")[:80],
        "metro": str(row.get("metro") or "")[:80],
    }


def build_vonage_ncco(
    *,
    intent_id: str,
    prospect_id: str,
    context: dict[str, str],
    call_id: str = "",
) -> list[dict[str, Any]]:
    token = _ws_token()
    if not token:
        raise RuntimeError("EMPIRE_VOICE_WS_TOKEN required")
    headers = {
        "intent_id": intent_id,
        "prospect_id": prospect_id,
        "business_name": context.get("business_name", ""),
        "niche": context.get("niche", ""),
        "metro": context.get("metro", ""),
        "voice_engine": "empire_voice_lab",
        "call_id": call_id,
    }
    return [{
        "action": "connect",
        "endpoint": [{
            "type": "websocket",
            "uri": _ws_url(intent_id, prospect_id, call_id),
            "content-type": "audio/l16;rate=16000",
            "headers": headers,
            "authorization": {
                "type": "custom",
                "value": "Bearer " + token,
            },
        }],
    }]


def map_vonage_status(value: Any) -> str | None:
    status = str(value or "").strip().lower()
    mapping = {
        "started": "call_ringing",
        "ringing": "call_ringing",
        "answered": "call_answered",
        "completed": "call_completed",
        "busy": "call_busy",
        "unanswered": "call_unanswered",
        "timeout": "call_unanswered",
        "rejected": "call_rejected",
        "cancelled": "call_rejected",
        "failed": "call_failed",
    }
    return mapping.get(status)


def _record_provider_event(
    intent_id: str,
    external_call_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> Any:
    return request_json(
        "POST",
        "/rest/v1/rpc/record_voice_provider_event",
        payload={
            "p_intent_id": intent_id,
            "p_external_call_id": external_call_id,
            "p_event_type": event_type,
            "p_payload": payload,
        },
    )


def _record_turn(
    intent_id: str,
    call_id: str,
    index: int,
    direction: str,
    text: str,
    evidence_extra: dict[str, Any] | None = None,
) -> Any:
    evidence: dict[str, Any] = {
        "stt": "sherpa_whisper" if direction == "inbound" else None,
        "tts": "sherpa_kokoro" if direction == "outbound" else None,
        "speech_vendor": None,
    }
    if evidence_extra:
        evidence.update(evidence_extra)
    return request_json(
        "POST",
        "/rest/v1/rpc/record_voice_turn",
        payload={
            "p_intent_id": intent_id,
            "p_external_call_id": call_id,
            "p_turn_index": index,
            "p_direction": direction,
            "p_body_text": text,
            "p_evidence": evidence,
        },
    )


@router.get("/health")
def voice_lab_health():
    config = VoiceLabConfig.from_env()
    readiness = EmpireVoiceLab.dependency_readiness()
    models = EmpireVoiceLab.model_readiness(config)
    ws_auth = bool(_ws_token())
    webhook_auth = bool(_webhook_token())
    switchboard = switchboard_status()
    return {
        "engine": "empire_voice_lab",
        "ownership": "self_hosted",
        "speech_vendor": None,
        "stt": config.stt_backend,
        "tts": config.tts_backend,
        "sample_rate": config.output_rate,
        "dependencies": readiness,
        "models": models,
        "websocket_auth_configured": ws_auth,
        "webhook_auth_configured": webhook_auth,
        "pay_per_call_switchboard": switchboard,
        "decision_judge": {
            "engine": "empire_decision_judge",
            "schema_version": DECISION_JUDGE_SCHEMA_VERSION,
            "mode": "deterministic_local",
            "network_dependency": False,
            "execution_authority": False,
        },
        "execution_allowed": (
            all(readiness.values())
            and all(models.values())
            and ws_auth
            and webhook_auth
        ),
    }


@router.get("/vonage/answer")
def vonage_answer(
    request: Request,
    intent_id: str,
    prospect_id: str,
    token: str,
):
    _require_webhook_token(token)
    health = voice_lab_health()
    if health["execution_allowed"] is not True:
        raise HTTPException(
            status_code=503,
            detail="empire_voice_lab_not_ready",
        )
    context = _prospect_context(prospect_id)
    call_id = str(
        request.query_params.get("uuid")
        or request.query_params.get("conversation_uuid")
        or ""
    ).strip()
    return build_vonage_ncco(
        intent_id=intent_id,
        prospect_id=prospect_id,
        context=context,
        call_id=call_id,
    )


@router.post("/vonage/event")
async def vonage_event(
    request: Request,
    intent_id: str,
    token: str,
):
    _require_webhook_token(token)
    payload = await request.json()
    event_type = map_vonage_status(
        payload.get("status") or payload.get("event")
    )
    if not event_type:
        return {"ok": True, "ignored": True}
    call_id = str(
        payload.get("uuid")
        or payload.get("conversation_uuid")
        or ""
    ).strip()
    if not call_id:
        raise HTTPException(
            status_code=422,
            detail="vonage_call_id_required",
        )
    result = _record_provider_event(
        intent_id,
        call_id,
        event_type,
        dict(payload),
    )
    return {"ok": True, "result": result}


async def _play_pcm(websocket: WebSocket, pcm: bytes) -> None:
    frame_bytes = 640
    for offset in range(0, len(pcm), frame_bytes):
        chunk = pcm[offset : offset + frame_bytes]
        if not chunk:
            continue
        await websocket.send_bytes(chunk)
        await asyncio.sleep(0.019)


async def _stream_tts(
    websocket: WebSocket,
    lab: EmpireVoiceLab,
    text: str,
    stop_event: threading.Event,
) -> None:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[bytes | BaseException | None] = asyncio.Queue()

    def on_chunk(pcm: bytes, _progress: float) -> None:
        if not stop_event.is_set():
            loop.call_soon_threadsafe(queue.put_nowait, pcm)

    def produce() -> None:
        try:
            lab.stream_text(
                text,
                on_chunk,
                should_stop=stop_event.is_set,
            )
        except BaseException as exc:
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    producer = asyncio.create_task(asyncio.to_thread(produce))
    try:
        while not stop_event.is_set():
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, BaseException):
                raise item
            await _play_pcm(websocket, item)
    finally:
        stop_event.set()
        if producer.done():
            await producer


@router.websocket("/vonage/socket")
async def vonage_socket(websocket: WebSocket):
    expected = _ws_token()
    authorization = websocket.headers.get("authorization", "")
    if not expected or authorization != "Bearer " + expected:
        await websocket.close(code=4401)
        return

    health = voice_lab_health()
    if health["execution_allowed"] is not True:
        await websocket.close(code=1011)
        return

    await websocket.accept()
    intent_id = str(
        websocket.query_params.get("intent_id") or ""
    ).strip()
    prospect_id = str(
        websocket.query_params.get("prospect_id") or ""
    ).strip()
    detector = VoiceTurnDetector()
    lab = _runtime()
    context = _prospect_context(prospect_id)
    history: list[dict[str, str]] = []
    call_id = str(
        websocket.query_params.get("call_id") or ""
    ).strip()
    turn_index = 0
    opening_played = False
    playback: asyncio.Task | None = None
    playback_stop: threading.Event | None = None
    playback_may_be_buffered = False
    response_task: asyncio.Task | None = None
    turn_generation = 0

    # Streaming Zipformer supplies the fast finalized transcript.
    # Partial transcripts MUST NOT authorize commercial actions.
    streaming_asr = lab.verifier_stt
    streaming_asr_stream = None
    streaming_partial = ""
    streaming_final = ""

    async def start_playback(text: str) -> None:
        nonlocal playback, playback_stop, playback_may_be_buffered
        playback_stop = threading.Event()
        playback_may_be_buffered = True
        playback = asyncio.create_task(
            _stream_tts(
                websocket,
                lab,
                text,
                playback_stop,
            )
        )

    async def stop_playback() -> None:
        nonlocal playback, playback_stop, playback_may_be_buffered

        if playback_stop is not None:
            playback_stop.set()

        if playback and not playback.done():
            playback.cancel()
            try:
                await playback
            except asyncio.CancelledError:
                pass

        # Provider-side audio can remain buffered after our local playback
        # coroutine has completed. Barge-in must clear that buffer as well.
        if playback_may_be_buffered:
            await websocket.send_text(json.dumps({"action": "clear"}))

        playback = None
        playback_stop = None
        playback_may_be_buffered = False

    async def consume_result(
        result: dict[str, Any],
        index: int,
        generation: int,
    ) -> None:
        # Worker cancellation does not guarantee underlying thread
        # cancellation. Stale generations cannot mutate any call state.
        if generation != turn_generation:
            return

        transcript = str(result.get("transcript") or "").strip()
        response_text = str(
            result.get("response_text") or ""
        ).strip()
        decision = result.get("decision")
        asr_candidates = result.get("asr_candidates")
        asr_mode = str(result.get("asr_mode") or "").strip()

        if not transcript:
            return

        history.append({"role": "user", "content": transcript})

        if intent_id and call_id:
            await asyncio.to_thread(
                _record_turn,
                intent_id,
                call_id,
                index,
                "inbound",
                transcript,
                {
                    "decision_judge": decision,
                    "asr_candidates": asr_candidates,
                    "asr_mode": asr_mode,
                }
                if isinstance(decision, dict)
                else None,
            )

        if generation != turn_generation:
            return

        if not response_text:
            return

        history.append({
            "role": "assistant",
            "content": response_text,
        })

        if intent_id and call_id:
            await asyncio.to_thread(
                _record_turn,
                intent_id,
                call_id,
                index,
                "outbound",
                response_text,
                {"asr_mode": asr_mode},
            )

        if generation != turn_generation:
            return

        await start_playback(response_text)

    async def respond_fast(
        audio: bytes,
        index: int,
        generation: int,
        fast_transcript: str,
    ) -> None:
        result = await asyncio.to_thread(
            lab.respond_streaming_final,
            fast_transcript,
            pcm16=audio,
            business_name=context.get("business_name", ""),
            niche=context.get("niche", ""),
            metro=context.get("metro", ""),
            history=list(history),
        )
        await consume_result(result, index, generation)

    async def respond_fallback(
        audio: bytes,
        index: int,
        generation: int,
    ) -> None:
        result = await asyncio.to_thread(
            lab.respond_text,
            audio,
            business_name=context.get("business_name", ""),
            niche=context.get("niche", ""),
            metro=context.get("metro", ""),
            history=list(history),
        )

        if isinstance(result, dict):
            result = dict(result)
            result.setdefault("asr_mode", "dual_fallback")

        await consume_result(result, index, generation)

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            text = message.get("text")
            if text is not None:
                try:
                    event = json.loads(text)
                except json.JSONDecodeError:
                    continue
                call_id = str(
                    event.get("uuid")
                    or event.get("conversation_uuid")
                    or event.get("call_id")
                    or call_id
                ).strip()
                if (
                    event.get("event") == "websocket:connected"
                    and not opening_played
                ):
                    opening_text = lab.opening_text(
                        business_name=context.get("business_name", "")
                    )
                    if intent_id and call_id:
                        await asyncio.to_thread(
                            _record_turn,
                            intent_id,
                            call_id,
                            0,
                            "outbound",
                            opening_text,
                        )
                    await start_playback(opening_text)
                    opening_played = True
                continue

            frame = message.get("bytes")
            if frame is None:
                continue

            event, utterance = detector.feed(frame)

            if event == "speech_start":
                turn_generation += 1
                await stop_playback()

                if response_task and not response_task.done():
                    response_task.cancel()

                streaming_partial = ""
                streaming_final = ""
                streaming_asr_stream = (
                    streaming_asr.create_stream()
                    if streaming_asr is not None
                    else None
                )

            # Feed every frame belonging to the active utterance into the
            # persistent online recognizer. This is observation only.
            if (
                streaming_asr is not None
                and streaming_asr_stream is not None
                and event in {"speech_start", "speech", "utterance"}
            ):
                streaming_partial = streaming_asr.accept_pcm(
                    streaming_asr_stream,
                    frame,
                )

            if event == "utterance" and utterance:
                if (
                    streaming_asr is not None
                    and streaming_asr_stream is not None
                ):
                    streaming_final = streaming_asr.finish_stream(
                        streaming_asr_stream
                    )
                    streaming_asr_stream = None

                turn_index += 1
                generation = turn_generation

                if streaming_final:
                    response_task = asyncio.create_task(
                        respond_fast(
                            utterance,
                            turn_index,
                            generation,
                            streaming_final,
                        )
                    )
                else:
                    # Empty streaming final falls back to the proven dual-ASR
                    # path, but still passes through the same stale guard,
                    # persistence and playback machinery.
                    response_task = asyncio.create_task(
                        respond_fallback(
                            utterance,
                            turn_index,
                            generation,
                        )
                    )

    except WebSocketDisconnect:
        pass
    finally:
        if response_task and not response_task.done():
            response_task.cancel()
        await stop_playback()
