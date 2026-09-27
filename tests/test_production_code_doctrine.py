from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_doctrine_requires_production_code_and_agentic_loops():
    text = (
        ROOT / "docs/ARCHITECTURE_FIRST_ENGINEERING_DOCTRINE.md"
    ).read_text()

    assert "Production-code-first rule" in text
    assert "Do not layer patches onto production behavior" in text
    assert "Agentic orchestration rule" in text
    assert "OBSERVE -> DIAGNOSE -> PLAN -> ACT -> VERIFY -> RECORD -> REPEAT" in text
    assert "Founder verification rule" in text


def test_coder_supervisor_requests_production_implementation_not_patch():
    text = (ROOT / "empire_os/coder_supervisor.py").read_text()

    assert "production-quality code" in text
    assert "Fix root causes rather than layering symptom patches" in text
    assert "smallest safe DEVELOPMENT patch" not in text


def test_reliability_service_runs_module_directly():
    text = (
        ROOT / "deploy/systemd/empire-reliability-agent.service"
    ).read_text()

    assert "-m empire_os.reliability_agent" in text
    assert "Restart=always" in text
    assert "scripts/" not in text
