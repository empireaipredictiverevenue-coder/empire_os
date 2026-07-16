"""
AEO Surface — publishes AEO spec drafts as rendered HTML pages.

Each page is written to ``/srv/aeo/{niche}/index.html`` (configurable)
and served as a static site for Authority Engine Optimization.

Pipeline::
  scout ▸ leads in funnel
  marketing ▸ gap analysis → draft spec
  aeo_surface ▸ render spec → write HTML to surface
  traffic_specialist ▸ advance prospects via published content
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from empire_os.marketing import AeoSpecDraft

logger = logging.getLogger("aeo_surface")

# Default surface root — where published AEO pages live
DEFAULT_SURFACE_ROOT = "/srv/aeo"


# ── Page template ──────────────────────────────────────────────────────

def _render_html(spec: AeoSpecDraft) -> str:
    """Render an AeoSpecDraft to a standalone HTML page."""
    now = datetime.utcnow().strftime("%Y-%m-%d")
    niche_display = spec.niche.replace("_", " ").title()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{niche_display} — AEO Authority Page</title>
<meta name="description" content="{spec.meta_description or spec.content_angle}">
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }}
  h1, h2, h3 {{ color: #0a3d62; }}
  .meta {{ color: #666; font-size: 0.9rem; border-bottom: 1px solid #ddd; padding-bottom: 1rem; }}
  blockquote {{ border-left: 3px solid #0a3d62; margin: 1rem 0; padding-left: 1rem; color: #555; }}
  .cta {{ background: #f0f7ff; border: 1px solid #0a3d62; border-radius: 8px; padding: 1.5rem; text-align: center; margin: 2rem 0; }}
</style>
</head>
<body>
<h1>{niche_display} — Complete Guide & Trusted Resources</h1>
<div class="meta">Published {now} · Niche: {spec.niche}</div>

<h2>Who This Is For</h2>
<p>{spec.target_audience}</p>

<h2>Common Pain Points</h2>
<p>{spec.pain_points}</p>

<h2>What People Are Asking</h2>
<p>{spec.key_questions}</p>

<h2>Our Approach</h2>
<p>{spec.content_angle}</p>

{spec.body_html}

<h2>Related Resources</h2>
<ul>
  <li>{spec.internal_links}</li>
</ul>

<h2>Competing Content</h2>
<p><small>Competitors covering this niche: {spec.competitors}</small></p>

{spec.call_to_action and f'<div class="cta"><p>{spec.call_to_action}</p></div>' or ''}

<hr>
<footer><small>Empire OS · AEO Surface · {now}</small></footer>
</body>
</html>"""


# ── Surface operations ─────────────────────────────────────────────────

def resolve_surface_root(surface_root: Optional[str] = None) -> Path:
    """Return the resolved surface root path, creating it if needed."""
    root = Path(surface_root or os.environ.get("AEO_SURFACE_ROOT") or DEFAULT_SURFACE_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    return root


def deploy_spec(
    spec: AeoSpecDraft,
    surface_root: Optional[str] = None,
) -> Path:
    """Render a spec draft to HTML and write it to the AEO surface.

    Returns the path to the written index.html.
    """
    root = resolve_surface_root(surface_root)
    niche_dir = root / spec.niche
    niche_dir.mkdir(parents=True, exist_ok=True)

    html = _render_html(spec)
    path = niche_dir / "index.html"
    path.write_text(html, encoding="utf-8")

    logger.info("Deployed AEO page for '%s' → %s", spec.niche, path)
    return path


def list_pages(surface_root: Optional[str] = None) -> list[dict]:
    """List all published AEO pages with metadata."""
    root = resolve_surface_root(surface_root)
    pages = []
    for entry in sorted(root.iterdir()):
        if entry.is_dir():
            idx = entry / "index.html"
            if idx.exists():
                mtime = datetime.fromtimestamp(idx.stat().st_mtime).isoformat()
                pages.append({
                    "niche": entry.name,
                    "path": str(idx),
                    "published_at": mtime,
                    "size_bytes": idx.stat().st_size,
                })
    return pages


def remove_page(niche: str, surface_root: Optional[str] = None) -> bool:
    """Remove a published AEO page by niche name."""
    root = resolve_surface_root(surface_root)
    niche_dir = root / niche
    idx = niche_dir / "index.html"
    if idx.exists():
        idx.unlink()
        # Remove directory if empty
        try:
            niche_dir.rmdir()
        except OSError:
            pass
        logger.info("Removed AEO page for '%s'", niche)
        return True
    return False
