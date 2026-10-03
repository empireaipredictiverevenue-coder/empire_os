import base64
from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient

from empire_os.cosyvoice3_sidecar_service import (
    create_cosyvoice3_sidecar_app,
)


TOKEN = "voice-sidecar-token-" + ("x" * 32)


class Engine:
    def __init__(self):
        self.voices = set()
        self.register_calls = []
        self.render_calls = []

    @property
    def model_ref(self):
        return "FunAudioLLM/Fun-CosyVoice3-0.5B-2512"

    @property
    def sample_rate(self):
        return 24000

    def voice_exists(self, voice_id):
        return voice_id in self.voices

    def register_voice(self, *, voice_id, prompt_text, prompt_wav_path):
        path = Path(prompt_wav_path)
        assert path.is_file()
        self.register_calls.append(
            (voice_id, prompt_text, path.read_bytes(), str(path))
        )
        self.voices.add(voice_id)

    def stream_pcm(self, *, voice_id, text):
        self.render_calls.append((voice_id, text))
        yield b"\x01\x00"
        yield b"\x02\x00"


def client(tmp_path, engine=None):
    value = engine or Engine()
    app = create_cosyvoice3_sidecar_app(
        engine=value,
        auth_token=TOKEN,
        temp_root=tmp_path / "voice-register",
    )
    return TestClient(app), value


def auth():
    return {"Authorization": "Bearer " + TOKEN}


def render_payload(text="Hello from Empire AI"):
    return {
        "render_id": "avatar-voice:test",
        "engine": "cosyvoice3",
        "model_ref": "FunAudioLLM/Fun-CosyVoice3-0.5B-2512",
        "voice_id": "phil-v1",
        "text": text,
        "text_sha256": sha256(text.encode()).hexdigest(),
        "language": "en",
        "output_format": "pcm_s16le",
        "sample_rate": 24000,
        "stream": True,
    }


def test_health_requires_bearer_auth(tmp_path):
    c, _engine = client(tmp_path)
    assert c.get("/health").status_code == 401
    response = c.get("/health", headers=auth())
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "cosyvoice3"
    assert body["meeting_transport_present"] is False
    assert body["execution_authority"] == "render_only"


def test_voice_registration_deletes_raw_reference_media(tmp_path):
    c, engine = client(tmp_path)
    raw = b"RIFF-test-wave-bytes"
    response = c.post(
        "/v1/voices/register",
        headers=auth(),
        json={
            "voice_id": "phil-v1",
            "prompt_text": "This is Phil's clean reference voice.",
            "reference_audio_base64": base64.b64encode(raw).decode(),
            "consent_evidence_ref": "consent:phil:voice-clone:v1",
        },
    )
    assert response.status_code == 200
    assert response.json()["raw_reference_media_persisted_by_api"] is False
    assert engine.register_calls[0][2] == raw
    temp_path = Path(engine.register_calls[0][3])
    assert temp_path.exists() is False


def test_render_requires_registered_voice_and_exact_text_fingerprint(tmp_path):
    engine = Engine()
    engine.voices.add("phil-v1")
    c, _engine = client(tmp_path, engine)

    payload = render_payload()
    response = c.post(
        "/v1/render",
        headers=auth(),
        json=payload,
    )
    assert response.status_code == 200
    assert response.content == b"\x01\x00\x02\x00"
    assert response.headers["x-voice-id"] == "phil-v1"
    assert engine.render_calls == [("phil-v1", payload["text"])]

    changed = dict(payload)
    changed["text"] = "Different human-unapproved text"
    response = c.post(
        "/v1/render",
        headers=auth(),
        json=changed,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "text_sha256_mismatch"
    assert len(engine.render_calls) == 1


def test_render_rejects_wrong_model_binding(tmp_path):
    engine = Engine()
    engine.voices.add("phil-v1")
    c, _engine = client(tmp_path, engine)
    payload = render_payload()
    payload["model_ref"] = "different-model"
    response = c.post("/v1/render", headers=auth(), json=payload)
    assert response.status_code == 422
    assert response.json()["detail"] == "voice_model_ref_mismatch"
    assert engine.render_calls == []
