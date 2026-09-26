"""Empire OS v3 — Building Damage Assessment adapter.

Accepts real pre/post imagery and exposes `classify_damage`.
Synthetic, hash-derived, and proxy damage scoring are disabled.

The optional xView2 torch adapter may load a real checkpoint, but real
image inference is not yet wired. Until it is, classification fails closed
rather than returning fabricated damage scores.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, "/opt/repo_skills/xView2")

LOG = Path("/root/feedback/satellite_damage.jsonl")
LOG.parent.mkdir(parents=True, exist_ok=True)


def _log(level: str, msg: str, **kw: Any) -> None:
    rec = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(),
           "level": level, "msg": msg, **kw}
    with LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")


# ─── Inference: optional torch path (xView2 native) ──────────────────────

def _bda_torch_run(pre_path: str, post_path: str,
                   checkpoint: str | None = None) -> dict | None:
    """Run real xView2 UNet. Returns None if torch or ckpt missing."""
    try:
        import torch  # type: ignore
    except Exception:
        return None
    if not checkpoint or not Path(checkpoint).exists():
        return None
    try:
        from model.unet import UNet  # type: ignore
    except Exception:
        return None
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = UNet(encoder_name="resnet50",
                     in_channels=6, classes=4).to(device)
        state = torch.load(checkpoint, map_location=device,
                           weights_only=True)
        model.load_state_dict(state)
        model.eval()
        _log("INFO", "bda_torch_loaded", device=device,
             params=sum(p.numel() for p in model.parameters()))
        return None  # Real inference not wired; see comment.
    except Exception as e:
        _log("WARN", "bda_torch_fail", err=str(e)[:200])
        return None


# ─── Public entry ───────────────────────────────────────────────────────

def classify_damage(pre_path: str, post_path: str,
                    checkpoint: str | None = None,
                    weights_path: str | None = None) -> dict:
    """Classify real pre/post imagery only.

    Synthetic/hash-derived inference is disabled. Until real image inference
    is wired, fail closed rather than returning a fabricated damage score.
    """
    pre = Path(pre_path)
    post = Path(post_path)
    if not pre.is_file() or not post.is_file():
        return {
            "ok": False,
            "err": "real_imagery_required",
            "model": None,
        }

    torch_result = _bda_torch_run(
        str(pre), str(post), checkpoint=checkpoint
    )
    if torch_result is not None:
        return {"ok": True, **torch_result}

    return {
        "ok": False,
        "err": "real_bda_inference_not_configured",
        "model": None,
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(
            "usage: satellite_damage_bda_agent.py PRE_IMAGE POST_IMAGE [CHECKPOINT]"
        )
    checkpoint = sys.argv[3] if len(sys.argv) >= 4 else None
    print(json.dumps(
        classify_damage(sys.argv[1], sys.argv[2], checkpoint=checkpoint),
        indent=2,
    ))
