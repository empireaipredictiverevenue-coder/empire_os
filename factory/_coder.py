#!/usr/bin/env python3
"""_coder.py — applies a generated diff via Aider inside the sandbox.

Aider is the coding engine: git-aware, repo-map aware. It writes the patch
to a context-scoped file set, then we run `aider --apply` for the change.

Run inside container: /root/venv/bin/python3 /root/factory/_coder.py
Expects /root/factory/_diff.txt (the LLM diff) produced by orchestrator.coder.
"""
import subprocess, sys, os

DIFF = "/root/factory/_diff.txt"


def main():
    if not os.path.isfile(DIFF):
        print("NO_DIFF")
        sys.exit(0)
    # Aider apply mode: feed diff on stdin, auto-accept, no chat.
    r = subprocess.run(
        ["/root/venv/bin/aider", "--no-auto-commits", "--yes", "--apply"],
        stdin=open(DIFF), capture_output=True, text=True, timeout=240,
    )
    out = (r.stdout + r.stderr)
    print(out[-800:] if len(out) > 800 else out)
    print("CODER_DONE")


if __name__ == "__main__":
    main()
