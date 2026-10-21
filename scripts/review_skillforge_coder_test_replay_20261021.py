"""Run fixed, source-grounded regression tests in a clean development worktree."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from empire_os.skillforge_coder_test_replay import replay_current_tests


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true",required=True)
    parser.add_argument("--current-worktree",type=Path,required=True)
    parser.add_argument("--original-source-root",type=Path,default=Path("/srv/empire_os"))
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    root=args.current_worktree.resolve()
    output=args.output.absolute()
    if (output.exists() or output.is_symlink()
        or not output.parent.is_dir()
        or output.parent.is_symlink()
        or not output.parent.resolve().is_relative_to(root/"runtime/skillforge/replays")):
        raise ValueError("output must be a new isolated runtime/skillforge/replays file")
    result=replay_current_tests(root,args.original_source_root)
    with output.open("x",encoding="utf-8") as file:
        json.dump(result,file,sort_keys=True,indent=2)
        file.write("\n")
    print(json.dumps({
        "status":"CURRENT_REVISION_TESTS_PASSED"
                 if result["current_revision_tests_passed"] else "REPLAY_HOLD",
        "historical_receipts":result["selected_historical_receipt_count"],
        "current_test_pass":result["current_revision_tests_passed"],
        "skillforge_approval":result["skillforge_promotion_authorized"],
    },sort_keys=True))


if __name__=="__main__":
    main()
