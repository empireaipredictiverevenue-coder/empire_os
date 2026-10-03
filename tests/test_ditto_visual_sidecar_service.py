import base64
from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient

from empire_os.ditto_visual_sidecar_service import (
    create_ditto_visual_sidecar_app,
)


TOKEN = "visual-sidecar-token-" + ("x" * 32)


class Engine:
    engine_name = "ditto"
    model_ref = "antgroup/ditto-talkinghead"

    def __init__(self):
        self.avatars = set()
        self.register_calls = []
        self.render_calls = []

    def avatar_exists(self, avatar_id):
        return avatar_id in self.avatars

    def register_avatar(self, *, avatar_id, source_image_path):
        path = Path(source_image_path)
        self.register_calls.append(
            (avatar_id, path.read_bytes(), str(path))
        )
        self.avatars.add(avatar_id)

    def stream_jpeg_frames(
        self,
        *,
        avatar_id,
        pcm,
        sample_rate,
        target_fps,
    ):
        self.render_calls.append(
            (avatar_id, pcm, sample_rate, target_fps)
        )
        yield b"\xff\xd8frame-1\xff\xd9"
        yield b"\xff\xd8frame-2\xff\xd9"


def client(tmp_path, engine=None):
    value = engine or Engine()
    app = create_ditto_visual_sidecar_app(
        engine=value,
        auth_token=TOKEN,
        temp_root=tmp_path / "visual-register",
    )
    return TestClient(app), value


def auth():
    return {"Authorization": "Bearer " + TOKEN}


def test_health_is_render_only_and_requires_auth(tmp_path):
    c, _engine = client(tmp_path)
    assert c.get("/health").status_code == 401
    response = c.get("/health", headers=auth())
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "ditto"
    assert body["stream_format"] == "multipart-jpeg"
    assert body["meeting_transport_present"] is False
    assert body["speech_execution"] is False
    assert body["commercial_execution"] is False
    assert body["execution_authority"] == "render_only"


def test_registration_deletes_raw_reference_image(tmp_path):
    c, engine = client(tmp_path)
    raw = b"fake-private-avatar-image"
    response = c.post(
        "/v1/avatars/register",
        headers=auth(),
        json={
            "avatar_id": "phil-visual-v1",
            "source_image_base64": base64.b64encode(raw).decode(),
            "consent_evidence_ref": "consent:phil:visual-clone:v1",
        },
    )
    assert response.status_code == 200
    assert response.json()["raw_reference_media_persisted_by_api"] is False
    assert engine.register_calls[0][1] == raw
    assert Path(engine.register_calls[0][2]).exists() is False


def test_render_stream_binds_exact_pcm_hash_model_and_avatar(tmp_path):
    engine = Engine()
    engine.avatars.add("phil-visual-v1")
    c, _engine = client(tmp_path, engine)
    pcm = b"\x01\x00\x02\x00" * 32
    digest = sha256(pcm).hexdigest()
    response = c.post(
        "/v1/render-stream",
        content=pcm,
        headers={
            **auth(),
            "content-type": "application/octet-stream",
            "x-empire-avatar-id": "phil-visual-v1",
            "x-empire-audio-sha256": digest,
            "x-empire-sample-rate": "24000",
            "x-empire-target-fps": "30",
            "x-empire-model-ref": "antgroup/ditto-talkinghead",
        },
    )
    assert response.status_code == 200
    assert response.headers["x-execution-authority"] == "render_only"
    assert response.headers["x-raw-audio-persisted"] == "false"
    assert response.headers["content-type"].startswith(
        "multipart/x-mixed-replace"
    )
    body = response.content
    assert b"X-Frame-Index: 0" in body
    assert b"X-Frame-Index: 1" in body
    assert b"frame-1" in body
    assert b"frame-2" in body
    assert engine.render_calls == [
        ("phil-visual-v1", pcm, 24000, 30)
    ]


def test_render_rejects_tampered_audio_hash_before_engine(tmp_path):
    engine = Engine()
    engine.avatars.add("phil-visual-v1")
    c, _engine = client(tmp_path, engine)
    pcm = b"\x01\x00"
    response = c.post(
        "/v1/render-stream",
        content=pcm,
        headers={
            **auth(),
            "x-empire-avatar-id": "phil-visual-v1",
            "x-empire-audio-sha256": "0" * 64,
            "x-empire-sample-rate": "24000",
            "x-empire-target-fps": "30",
            "x-empire-model-ref": "antgroup/ditto-talkinghead",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "audio_sha256_mismatch"
    assert engine.render_calls == []


def test_render_rejects_wrong_model_binding(tmp_path):
    engine = Engine()
    engine.avatars.add("phil-visual-v1")
    c, _engine = client(tmp_path, engine)
    pcm = b"\x01\x00"
    response = c.post(
        "/v1/render-stream",
        content=pcm,
        headers={
            **auth(),
            "x-empire-avatar-id": "phil-visual-v1",
            "x-empire-audio-sha256": sha256(pcm).hexdigest(),
            "x-empire-sample-rate": "24000",
            "x-empire-target-fps": "30",
            "x-empire-model-ref": "wrong-model",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "visual_model_ref_mismatch"
    assert engine.render_calls == []
