"""Read-only preflight: .venv/bin/python scripts/check_factory_hybrid_v1.py input.json

JSON fields: request, proposal_gate, self_review, independent_review,
optional promptfoo_result and council_result. Do NOT treat arbitrary JSON
as trusted attestation or use the exit code to approve deployment.
"""
import json
import sys
from pathlib import Path
from empire_os.factory_hybrid_quality_v1 import evaluate_hybrid_quality


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_factory_hybrid_v1.py <evidence.json>", file=sys.stderr)
        return 2
    evidence = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    result = evaluate_hybrid_quality(**evidence).as_dict()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "VERIFIED_FOR_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
