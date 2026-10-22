"""Manual one-shot, LOCAL Laya inference for 30 privately pinned real SEO cases."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path

from empire_os.search_intelligence.ai_first_seo_review import (
    SeoAiFirstHeld, public_safe_ai_summary, review_cases_with_local_ai,
    validated_cases,
)

DIR = Path("/home/ubuntu/empire_releases/search_jev_owner_receipts_20261021")
OUT = DIR / "seo_local_ai_first_30_20261022.json"


def run(*, execute: bool) -> dict[str, object]:
    rows=validated_cases()
    if not execute:
        return {
            "status": "LOCAL_AI_FIRST_DRY_RUN",
            "verified_original_url_cases": len(rows),
            "model_inference_attempts": 0,
            "external_paid_jev_calls": 0,
            "human_labels_created": 0,
            "execution_authority": "NONE",
        }
    if DIR.is_symlink() or DIR.stat().st_mode & 0o077 or not DIR.is_dir():
        raise SeoAiFirstHeld("PRIVATE_AI_RECEIPT_DIR_UNSAFE")
    fd = os.open(str(DIR / ".local-ai-first.lock"),
                 os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if OUT.exists() or OUT.is_symlink():
            raise SeoAiFirstHeld("AI_FIRST_RECEIPT_EXISTS_NO_REPEAT")
        reviewed=review_cases_with_local_ai(rows)
        summary=public_safe_ai_summary(reviewed)
        out_fd=os.open(str(OUT), os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(out_fd,"w",encoding="utf-8") as stream:
                json.dump(reviewed,stream,sort_keys=True,indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            OUT.unlink(missing_ok=True)
            raise
    return {**summary, "status": "AI_FIRST_SHADOW_SWEEP_COMPLETE",
            "private_receipt_written": True, "model_calls_automatic": False}


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--run-local-shadow-once",action="store_true")
    args=p.parse_args()
    try:
        result=run(execute=args.run_local_shadow_once)
    except (SeoAiFirstHeld, OSError) as exc:
        result={
            "status":"LOCAL_AI_FIRST_HELD",
            "reason":str(exc) if isinstance(exc, SeoAiFirstHeld) else "LOCAL_SOURCE_OR_FILE_UNAVAILABLE",
            "external_paid_jev_calls":0, "execution_authority":"NONE",
        }
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
