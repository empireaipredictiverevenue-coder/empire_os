"""Record real EmpireOS UI workflows for demos.

Primary purpose: capture the actual read-only Empire interface operating on
canonical evidence. AI-generated media may decorate the result later, but the
recorded system remains the proof layer.

Playwright is an optional dependency. Recording is loopback/private by default.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Iterable
from urllib.parse import urlparse


ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


@dataclass(frozen=True)
class DemoAction:
    action: str
    value: str | None = None
    duration_ms: int = 1000

    def validate(self) -> None:
        if self.action not in {"goto", "wait", "scroll", "click"}:
            raise ValueError(f"unsupported demo action: {self.action}")
        if self.duration_ms < 0 or self.duration_ms > 30000:
            raise ValueError("duration_ms must be 0-30000")
        if self.action in {"goto", "click"} and not str(self.value or "").strip():
            raise ValueError(f"{self.action} requires value")


@dataclass(frozen=True)
class DemoRecordingPlan:
    title: str
    base_url: str
    actions: tuple[DemoAction, ...]
    width: int = 1600
    height: int = 900
    fps: int = 30

    def validate(self) -> None:
        if not self.title.strip():
            raise ValueError("title required")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("base_url must be http(s)")
        if parsed.hostname not in ALLOWED_HOSTS:
            raise ValueError("demo recorder is loopback-only by default")
        if not self.actions:
            raise ValueError("at least one action required")
        for action in self.actions:
            action.validate()


def founder_console_demo_plan(
    *,
    base_url: str = "http://127.0.0.1:8775",
) -> DemoRecordingPlan:
    return DemoRecordingPlan(
        title="Empire AI Founder Console — Live Revenue System",
        base_url=base_url,
        actions=(
            DemoAction("goto", "/founder", 1800),
            DemoAction("wait", duration_ms=1500),
            DemoAction("scroll", "700", 1800),
            DemoAction("wait", duration_ms=900),
            DemoAction("scroll", "800", 1800),
            DemoAction("wait", duration_ms=900),
            DemoAction("scroll", "-500", 1400),
        ),
    )


def _safe_join(base_url: str, value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme:
        target = value
    else:
        target = base_url.rstrip("/") + "/" + value.lstrip("/")
    host = urlparse(target).hostname
    if host not in ALLOWED_HOSTS:
        raise ValueError("recording target escaped loopback allowlist")
    return target


def record_demo(
    plan: DemoRecordingPlan,
    *,
    output_dir: str | Path,
    mp4_name: str = "empire-demo.mp4",
) -> dict:
    plan.validate()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed; install empire-os[video-recorder]"
        ) from exc

    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    raw_video: Path | None = None
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            viewport={"width": plan.width, "height": plan.height},
            record_video_dir=str(raw_dir),
            record_video_size={"width": plan.width, "height": plan.height},
        )
        page = context.new_page()
        for action in plan.actions:
            if action.action == "goto":
                page.goto(
                    _safe_join(plan.base_url, str(action.value)),
                    wait_until="networkidle",
                    timeout=30000,
                )
            elif action.action == "wait":
                page.wait_for_timeout(action.duration_ms)
            elif action.action == "scroll":
                amount = int(str(action.value or "0"))
                page.evaluate("(y) => window.scrollBy(0, y)", amount)
                page.wait_for_timeout(action.duration_ms)
            elif action.action == "click":
                page.locator(str(action.value)).click(timeout=10000)
                page.wait_for_timeout(action.duration_ms)

        page.wait_for_timeout(800)
        video = page.video
        context.close()
        browser.close()
        if video is not None:
            raw_video = Path(video.path())

    if raw_video is None or not raw_video.exists():
        raise RuntimeError("Playwright did not produce a recording")

    mp4 = out / mp4_name
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(raw_video),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(mp4),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        final_path = mp4
    else:
        final_path = raw_video

    return {
        "title": plan.title,
        "plan": {
            "base_url": plan.base_url,
            "actions": [asdict(x) for x in plan.actions],
            "width": plan.width,
            "height": plan.height,
            "fps": plan.fps,
        },
        "raw_video": str(raw_video),
        "output": str(final_path),
        "proof_layer": "real_empire_ui",
        "synthetic_proof": False,
        "published": False,
        "actual_revenue": False,
    }
