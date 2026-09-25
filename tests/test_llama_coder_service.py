from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "deploy/systemd-user/empire-llama-coder.service"


def test_llama_coder_enables_jinja_tool_call_templates():
    text = UNIT.read_text(encoding="utf-8")
    assert "--jinja" in text
    assert "--chat-template chatml" in text
    assert "--host 127.0.0.1" in text
    assert "--port 11435" in text
