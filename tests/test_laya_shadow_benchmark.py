import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmarks/laya_reply_cases.jsonl"
SCRIPT = ROOT / "scripts/benchmark_laya_shadow.py"


def test_laya_reply_benchmark_covers_commercial_reply_classes():
    rows = [
        json.loads(line)
        for line in CASES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    labels = {row["expected_label"] for row in rows}
    assert {
        "positive",
        "question",
        "objection",
        "later",
        "negative",
        "unsubscribe",
    }.issubset(labels)


def test_laya_benchmark_keeps_shadow_review_gate():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "review_typed_decision_result" in text
    assert '"shadow_only": True' in text
    assert '"execution_authority": "none"' in text
    assert "raw_accuracy" in text
    assert "safe_accuracy" in text
    assert "escalation_rate" in text
    assert "unsafe_accepts" in text
    assert "return 0 if unsafe_accepts == 0 else 2" in text
