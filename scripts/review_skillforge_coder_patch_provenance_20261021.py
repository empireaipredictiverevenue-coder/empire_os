"""Original-source Coder patch provenance audit (no code execution or approval)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from empire_os.skillforge_coder_patch_provenance import (
    audit_selected_coder_patch_provenance,
)


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true",required=True)
    parser.add_argument("--original-source-root",type=Path,required=True)
    parser.add_argument("--repo-root",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    root=args.repo_root.resolve()
    output=args.output.absolute()
    allowed=root/"runtime/skillforge/replays"
    if (output.exists() or output.is_symlink()
        or not allowed.is_dir() or allowed.is_symlink()
        or output.parent.resolve()!=allowed.resolve()):
        raise ValueError("output must be new and inside isolated replay inventory")
    if args.original_source_root.resolve()==root:
        raise ValueError("original source and development workspace must differ")
    evidence=audit_selected_coder_patch_provenance(
        args.original_source_root,root)
    with output.open("x",encoding="utf-8") as file:
        json.dump(evidence,file,indent=2,sort_keys=True)
        file.write("\n")
    print(json.dumps({
        "status":evidence["status"],
        "original_receipts":evidence["selected_original_job_count"],
        "missing_commit_links":evidence["missing_explicit_implementation_commit_count"],
        "independent_implementations":evidence["independent_code_implementations_verified"],
        "skill_approval":evidence["skillforge_auto_approval"],
    },sort_keys=True))


if __name__=="__main__":
    main()
