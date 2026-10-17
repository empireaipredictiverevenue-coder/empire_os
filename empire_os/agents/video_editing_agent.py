"""Historical Video Editing Agent — canonical Empire Media OS compatibility.

OpenMontage is selected and reviewed by empire_os.media_renderer. This module
must not run its former independent queue, paid-provider actions, self-demos,
unauthorised outbound or deprecated shell-based render_demo.py invocation.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from empire_os.synthetic_agents import SyntheticAgent
from empire_os.media_renderer import (
    OPENMONTAGE_EDITORIAL_PIPELINES,
    review_openmontage_edit,
)

OPENMONTAGE_DIR = Path(
    os.environ.get("EMPIRE_OPENMONTAGE_SOURCE", "/opt/empire-ai/vendor/OpenMontage")
)
OPENCUT_DIR = Path(
    os.environ.get("EMPIRE_OPENCUT_SOURCE", "/opt/empire-ai/vendor/OpenCut")
)
OPENCUT_CLASSIC_DIR = Path(
    os.environ.get("EMPIRE_OPENCUT_CLASSIC_SOURCE", "/opt/empire-ai/vendor/OpenCut-Classic")
)


def list_openmontage_pipelines() -> list[str]:
    """Only known editorial pipelines, never unreviewed GPU/cloud recipes."""
    pdir = OPENMONTAGE_DIR / "pipeline_defs"
    if not pdir.is_dir():
        return []
    return sorted(
        name for name in OPENMONTAGE_EDITORIAL_PIPELINES
        if (pdir / (name + ".yaml")).is_file()
    )


def list_openmontage_tools() -> list[str]:
    """Read-only inventory. Tools are not made executable by discovery."""
    directory = OPENMONTAGE_DIR / "tools"
    if not directory.is_dir():
        return []
    return sorted(
        item.name for item in directory.iterdir()
        if item.is_dir() and not item.name.startswith("_")
    )


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def render_brief(project: dict, pipeline: str) -> dict:
    """Plan via the single Media OS renderer; never execute an editor here."""
    timeline = project.get("media_os_timeline")
    if not isinstance(timeline, dict):
        return {
            "ok": False,
            "state": "HOLD",
            "error": "canonical Empire Media OS timeline required",
            "render_executed": False,
        }
    review = review_openmontage_edit(
        timeline,
        pipeline=pipeline,
        source_root=str(OPENMONTAGE_DIR),
        # All gates are deliberately not authorizable by a hub message.
        licence_review_approved=False,
        source_rights_approved=False,
        local_no_paid_providers=False,
        estimated_cost_usd=None,
    )
    return {
        "ok": False,
        "state": review["state"],
        "review": review,
        "render_executed": False,
        "error": "review only; Media OS owns render execution",
    }


class VideoEditingAgent(SyntheticAgent):
    """Disabled legacy shell; retained only for read-only status compatibility."""

    def observe(self) -> dict:
        return {
            "mode": "OBSERVE",
            "canonical_owner": "empire.media_os",
            "openmontage_pipelines": list_openmontage_pipelines(),
            "openmontage_tool_categories": list_openmontage_tools(),
            "ffmpeg_available": ffmpeg_available(),
            "legacy_autonomous_render": False,
            "opencut_present": OPENCUT_DIR.is_dir(),
            "opencut_classic_present": OPENCUT_CLASSIC_DIR.is_dir(),
            "execution_authority": "none",
        }

    def reason(self, state: dict) -> str:
        return json.dumps({
            "action": "idle",
            "reasoning": "Media OS owns planning and rendering",
        })

    def act(self, decision: str) -> dict:
        return {
            "summary": "legacy video-editing worker retired; no render performed",
            "execution_authority": "none",
        }


if __name__ == "__main__":
    print(json.dumps({
        "status": "LEGACY_WORKER_DISABLED",
        "canonical_owner": "empire.media_os",
        "render_executed": False,
    }))
