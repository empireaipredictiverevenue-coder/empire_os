import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmarks/needle_shadow_cases.jsonl"
SCRIPT = ROOT / "scripts/benchmark_needle_shadow.py"


def test_needle_benchmark_corpus_has_route_and_off_topic_cases():
    rows = [
        json.loads(line)
        for line in CASES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) >= 5
    assert any(row["expected_tool"] is None for row in rows)
    assert {row["expected_tool"] for row in rows if row["expected_tool"]} == {
        "classify_reply",
        "build_copy_brief",
    }


def test_needle_benchmark_remains_shadow_only():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "load_needle_shadow_router" in text
    assert '"tool_executed": False' in text
    assert '"execution_authority": "none"' in text
    assert ".run(" not in text
