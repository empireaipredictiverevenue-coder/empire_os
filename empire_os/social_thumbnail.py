"""social_thumbnail.py — $0 AI thumbnail generator for Empire OS socials.

Pipeline (no paid API):
  1. Pollinations.ai text-to-image (FREE, no key) -> background art
  2. Pillow overlay: bold headline + niche tag + accent bar
  3. PIL writes the jpg

ENV: none required. Pollinations is keyless but rate-limited; on failure we
fall back to a solid-gradient background so the pipeline never blocks.
"""
from __future__ import annotations

import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, "/root/empire_os")

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_LIGHT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
THUMB_DIR = Path("/root/empire_os/empire_os/social_thumbs")
POLLINATIONS = "https://image.pollinations.ai/prompt/"
_BG_TMP = Path("/tmp/_bg.jpg")


def _bg_prompt(niche: str, headline: str) -> str:
    base = {
        "plumbing": "plumber fixing pipe, wet tools, dramatic lighting",
        "roofing": "roof repair aerial, house, storm clouds, cinematic",
        "towing": "tow truck night, highway, neon, cinematic",
        "default": "entrepreneur dark background, neon glow, cinematic tech",
    }.get(niche.lower(), "dark gradient, neon accent, cinematic tech")
    return f"{base}, youtube thumbnail style, high contrast, no text"


def _fetch_bg(prompt: str, w: int, h: int) -> bytes | None:
    url = POLLINATIONS + urllib.parse.quote(prompt) + \
          f"?width={w}&height={h}&nologo=true&model=flux"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        return urllib.request.urlopen(req, timeout=45).read()
    except Exception:
        return None


def _gradient(w: int, h: int, c1=(10, 10, 10), c2=(20, 20, 40)) -> Image.Image:
    img = Image.new("RGB", (w, h))
    for y in range(h):
        t = y / h
        img.paste(tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)),
                  (0, y, w, y + 1))
    return img


def _wrap_text(draw, text: str, font, max_w: int) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for wd in words:
        test = (cur + " " + wd).strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines[:3]


def generate_thumbnail(headline: str, niche: str = "default",
                       out_path: str = "") -> dict:
    """Generate a punchy thumbnail. Returns {ok, out, source}."""
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(out_path) if out_path else \
        THUMB_DIR / f"thumb_{int(time.time())}.jpg"
    w, h = 1280, 720

    bg = _fetch_bg(_bg_prompt(niche, headline), w, h)
    src = "pollinations" if bg else "gradient-fallback"
    if bg:
        try:
            _BG_TMP.write_bytes(bg)
            img = Image.open(_BG_TMP).convert("RGB").resize((w, h))
        except Exception:
            img = _gradient(w, h)
            src = "gradient-fallback"
    else:
        img = _gradient(w, h)

    # scrim for text contrast
    scrim = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    sd.rectangle([0, int(h * 0.45), w, h], fill=(0, 0, 0, 175))
    img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")
    draw = ImageDraw.Draw(img)

    # accent bar + niche tag
    accent = {"plumbing": (0, 150, 255), "roofing": (255, 120, 0),
              "towing": (255, 210, 0), "default": (0, 230, 160)}.get(
        niche.lower(), (0, 230, 160))
    draw.rectangle([60, int(h * 0.45) - 12, 260, int(h * 0.45) + 12], fill=accent)
    draw.text((72, int(h * 0.45) - 4), niche.upper()[:12],
              font=ImageFont.truetype(FONT_LIGHT, 34), fill=(0, 0, 0))

    # headline (wrapped, max 3 lines)
    f = ImageFont.truetype(FONT, 72)
    lines = _wrap_text(draw, headline, f, w - 120)
    y = int(h * 0.52)
    for ln in lines:
        draw.text((60, y), ln, font=f, fill=(255, 255, 255))
        y += 82

    img.save(out, "JPEG", quality=90)
    return {"ok": True, "out": str(out), "source": src, "niche": niche}


if __name__ == "__main__":
    import sys as _s
    hl = _s.argv[1] if len(_s.argv) > 1 else "AI Agents Close Deals For You"
    ni = _s.argv[2] if len(_s.argv) > 2 else "default"
    print(generate_thumbnail(hl, ni))
