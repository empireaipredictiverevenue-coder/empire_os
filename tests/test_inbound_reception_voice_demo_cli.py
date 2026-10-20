"""The exact synthetic demo is repeatable and never creates a live call."""
import json
import subprocess
import sys

import pytest

from scripts.demo_ai_receptionist_call_20261020 import run_demo


@pytest.mark.parametrize("intent", ["appointment", "callback", "human", "stop", "unknown"])
def test_synthetic_http_conversation_coverage(intent):
    result = run_demo(intent)
    assert result["status"] == "PASS_SYNTHETIC_SIGNED_WEBHOOK_CONVERSATION"
    assert result["steps"][:3] == ["talk", "input", "talk"]
    assert result["steps"] == (["talk", "input", "talk", "input"]
                              if intent == "unknown" else ["talk", "input", "talk"])
    assert result["voice_provider_connected"] is False
    assert result["actual_revenue"] is False
    assert result["contact_recorded"] is False
    assert result["appointment_booked"] is False
    assert result["callback_placed"] is False
    assert result["assistant_greeting"].startswith("Hello, you've reached")
    assert "AI receptionist" in result["assistant_greeting"]


def test_demo_bad_intent_refused():
    with pytest.raises(ValueError, match="demo_intent_not_permitted"):
        run_demo("contact-real-customer")


def test_demo_cli_requires_synthetic_flag():
    process = subprocess.run(
        [sys.executable, "-B", "-m", "scripts.demo_ai_receptionist_call_20261020"],
        capture_output=True, text=True,
    )
    assert process.returncode == 2
    assert json.loads(process.stdout)["status"] == "HELD_SYNTHETIC_ONLY_FLAG_REQUIRED"
