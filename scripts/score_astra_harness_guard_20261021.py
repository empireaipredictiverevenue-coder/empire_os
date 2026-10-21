"""Compare original on-disk Harness² model results with a trusted guarded script.

This is an original-evidence task-quality measurement, not a forecast or revenue
claim. All input files are redacted copies in an isolated Harness² run.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from empire_os.astra_harness_evidence_guard import evaluate_guarded_answer, verified_snapshot_facts

def _decode(text: str) -> dict:
    try:
        block=re.search(r"\{[\s\S]*?\}",text)
        value=json.loads(block.group(0)) if block else {}
        return value if isinstance(value,dict) else {}
    except (ValueError,AttributeError):
        return {}

def grade(kind: str, source: dict, output: dict) -> dict:
    expected=verified_snapshot_facts(kind,source)
    observed=output.get("one_brief_reason")
    reason=observed if isinstance(observed,str) else ""
    wrong_claim=bool(re.search(
        r"\b(fraud|criminal|scam|wrongdoing|misconduct)\b|"
        r"actual count should be|observed values.{0,25}incorrect", reason,flags=re.I))
    flags_ok=all(output.get(key) is False for key in
                 ("verified_replies","verified_revenue","activation_ready"))
    # Named, original fields must be cited with the actual values and context.
    if kind=="conversion":
        fact=expected["source_facts"]
        grounded=(str(fact["outreach_entered"]) in reason
                  and str(fact["observed_replies"]) in reason
                  and ("reply" in reason.lower() or "outreach" in reason.lower()))
    elif kind=="acquisition":
        fact=expected["source_facts"]
        grounded=(str(fact["priority_target_candidates"]) in reason
                  and str(fact["demand_gap_candidates"]) in reason
                  and "target" in reason.lower() and "gap" in reason.lower())
    else:
        cents=expected["source_facts"]["snapshot_recognized_revenue_cents"]
        grounded=f"recognized_revenue_cents={cents}" in reason
    return {"flags_ok":flags_ok, "source_numbers_grounded":grounded,
            "unsupported_accusations_or_corrections":wrong_claim,
            "pass":flags_ok and grounded and not wrong_claim}

def score(root:Path)->dict:
    result={}
    for kind in ("conversion","acquisition"):
        source=json.loads((root/"sources"/kind/"evidence.json").read_text())
        base=root/"executions"/f"empire_evidence-oc-agg1/{kind}/base1/answer.txt"
        original=base.read_text(encoding="utf-8")
        observed=_decode(original)
        guarded=evaluate_guarded_answer(kind,source,original)["review"]
        result[kind]={"baseline":grade(kind,source,observed),
                      "guarded":grade(kind,source,guarded)}
    return {"schema_version":"empire.astra.harness2_guard_comparison.v1",
            "basis":"ORIGINAL_REDACTED_RUNTIME_SNAPSHOTS",
            "tasks":result,
            "baseline_passed":sum(t["baseline"]["pass"] for t in result.values()),
            "guarded_passed":sum(t["guarded"]["pass"] for t in result.values()),
            "task_count":len(result),
            "improves_evidence_grounding":all(t["guarded"]["pass"] for t in result.values())
                       and not all(t["baseline"]["pass"] for t in result.values()),
            "production_activation_authorized":False,
            "model_generated_code_executed":False,"realized_revenue_improvement_proven":False}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--read-only",required=True,action="store_true")
    p.add_argument("--run-root",required=True);args=p.parse_args()
    print(json.dumps(score(Path(args.run_root)),sort_keys=True))
