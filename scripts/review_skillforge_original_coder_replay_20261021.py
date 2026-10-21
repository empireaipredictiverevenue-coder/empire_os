"""Run pinned Coder release tests in existing detached Git worktrees, once."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from empire_os.skillforge_coder_historical_replay import replay_exact_original_releases


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--read-only',action='store_true',required=True)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--repo-root',type=Path,required=True)
    parser.add_argument('--deadline-worktree',type=Path,required=True)
    parser.add_argument('--provider-worktree',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    repo=args.repo_root.resolve()
    output=args.output.absolute()
    dest=repo/'runtime/skillforge/replays'
    if (output.exists() or output.is_symlink() or not dest.is_dir()
        or dest.is_symlink() or output.parent.resolve()!=dest.resolve()):
        raise ValueError("target must be a new isolated replay output")
    report=replay_exact_original_releases(
        args.source_root,repo,
        (args.deadline_worktree,args.provider_worktree))
    with output.open('x',encoding='utf-8') as f:
        json.dump(report,f,sort_keys=True,indent=2)
        f.write('\n')
    print(json.dumps({
        'status':report['status'],
        'source_chains_with_passing_replays':report['original_revisions_with_test_pass'],
        'production_deployment_verified':report['production_deployment_verified'],
        'skillforge_auto_approval':report['skillforge_auto_approval'],
    },sort_keys=True))


if __name__=='__main__':
    main()
