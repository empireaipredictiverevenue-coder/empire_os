#!/usr/bin/env python3
"""Empire OS cinematic branding assets — generates PNGs that get burnt into video:
  - logo_watermark.png       : always-on bottom-right Empire AI logo
  - subscribe_button.png     : pulse-animated red YouTube SUBSCRIBE button (sequence of 12 frames)
  - name_plate.png           : cinematic lower-third with name + title
  - end_screen.png           : subscribe + 2 video suggestions
  - broll/[n].png            : stock-style cutaways (dashboard / data / city)
All Pillow-based, no API.
"""
from __future__ import annotations
import math, os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_LIGHT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BLACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
OUT_DIR = Path("/tmp/empire_branding")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    f = FONT_BOLD if bold else FONT_LIGHT
    try:
        return ImageFont.truetype(f, size)
    except Exception:
        return ImageFont.load_default()


# -- 1. Logo watermark (always-on, bottom-right) --

def make_logo_watermark() -> str:
    """Empire AI logo, simple wordmark with accent bar. White text, dark scrim background."""
    w, h = 360, 90
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # rounded background scrim
    d.rounded_rectangle([0, 0, w, h], radius=14, fill=(0, 0, 0, 180))
    # accent bar (Empire teal)
    d.rectangle([16, 16, 28, h - 16], fill=(0, 230, 220, 255))
    # wordmark
    f = _font(34, bold=True)
    d.text((42, 18), "EMPIRE", fill=(255, 255, 255, 255), font=f)
    # small ai label
    f2 = _font(34, bold=True)
    d.text((192, 18), "AI", fill=(0, 230, 220, 255), font=f2)
    out = OUT_DIR / "logo_watermark.png"
    img.save(out, "PNG")
    return str(out)


# -- 2. Animated subscribe button (12 frames, subtle pulse) --

def make_subscribe_button_frames() -> list[str]:
    """Pulsing red subscribe button. Returns list of 12 PNG paths."""
    paths = []
    w, h = 320, 100
    base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for i in range(12):
        # Pulse: scale 1.0 -> 1.06 -> 1.0 (sine)
        t = i / 12.0
        scale = 1.0 + 0.06 * math.sin(t * 2 * math.pi)
        # Slight horizontal jiggle for personality
        dx = int(4 * math.sin(t * 4 * math.pi))
        sw, sh = int(w * scale), int(h * scale)
        # Make a fresh RGBA each frame so we can ping-pong pulse cleanly
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        # button: red rounded rect
        d.rounded_rectangle([10, 10, w - 10, h - 10], radius=int(20 * scale),
                            fill=(255, 0, 0, 235))
        # icon: play triangle / bell — keep simple, just SUB text
        f = _font(38, bold=True)
        d.text((50 + dx, 28), "SUBSCRIBE", fill=(255, 255, 255, 255), font=f)
        # small bell dot (like the YT bell)
        d.ellipse([w - 38, 18, w - 18, 38], fill=(255, 255, 255, 240))
        layer = layer.resize((sw, sh), Image.LANCZOS if hasattr(Image, "LANCZOS") else 1)
        canvas = base.copy()
        ox = (w - sw) // 2
        canvas.paste(layer, (ox, (h - sh) // 2), layer)
        out = OUT_DIR / f"subscribe_{i:02d}.png"
        canvas.save(out, "PNG")
        paths.append(str(out))
    return paths


# -- 3. Cinematic lower-third name plate --

def make_name_plate(name: str, title: str) -> str:
    w, h = 1400, 220
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # dark gradient bar
    d.rectangle([0, 0, w, h], fill=(8, 12, 22, 220))
    # accent strip (Empire teal) runs across left side
    d.rectangle([0, 0, 16, h], fill=(0, 230, 220, 255))
    # name
    f_name = _font(76, bold=True)
    d.text((60, 20), name, fill=(255, 255, 255, 255), font=f_name)
    # title (subtle / muted)
    f_title = _font(34, bold=False)
    d.text((60, 120), title, fill=(170, 200, 220, 255), font=f_title)
    out = OUT_DIR / "name_plate.png"
    img.save(out, "PNG")
    return str(out)


# -- 4. End screen with big subscribe + 2 video cards --

def make_end_screen(video_titles: list[str]) -> str:
    """End screen with subscribe button + 2 video suggestions."""
    w, h = 1920, 1080
    img = Image.new("RGB", (w, h), (10, 14, 26))
    d = ImageDraw.Draw(img)
    # Brand title
    d.text((60, 60), "THANKS FOR WATCHING", fill=(255, 255, 255), font=_font(64))
    d.text((60, 140), "Empire AI — Predictive Revenue Intelligence",
           fill=(170, 200, 220), font=_font(28))
    # accent divider
    d.rectangle([60, 200, 280, 220], fill=(0, 230, 220))
    # big subscribe CTA box
    btn_w, btn_h = 540, 140
    bx, by = (w - btn_w) // 2, 280
    d.rounded_rectangle([bx, by, bx + btn_w, by + btn_h], radius=20,
                        fill=(255, 0, 0))
    f = _font(64, bold=True)
    d.text((bx + 100, by + 32), "SUBSCRIBE", fill=(255, 255, 255), font=f)
    # bell icon box next to button
    d.rounded_rectangle([bx + btn_w + 24, by, bx + btn_w + 24 + 140, by + btn_h],
                        radius=20, fill=(60, 60, 60))
    d.text((bx + btn_w + 64, by + 32), "🔔", fill=(255, 255, 255), font=_font(64))
    # 2 video cards
    for i, t in enumerate(video_titles[:2]):
        vw, vh = 760, 380
        vx = 200 + i * (vw + 80)
        vy = 540
        # card body with gradient hint
        d.rounded_rectangle([vx, vy, vx + vw, vy + vh], radius=14,
                            fill=(20, 30, 50))
        # accent strip top
        d.rectangle([vx, vy, vx + vw, vy + 10], fill=(0, 230, 220))
        # video number
        d.text((vx + 24, vy + 24), f"VIDEO {i+1}", fill=(170, 200, 220), font=_font(28))
        # title (wrapped manually to 2 lines max)
        title = t if len(t) < 48 else t[:45] + "..."
        d.text((vx + 24, vy + 70), title[:30], fill=(255, 255, 255), font=_font(38))
        if len(title) > 30:
            d.text((vx + 24, vy + 120), title[30:], fill=(255, 255, 255), font=_font(38))
        # WATCH NOW bar at bottom
        d.rectangle([vx, vy + vh - 60, vx + vw, vy + vh], fill=(0, 230, 220))
        d.text((vx + 24, vy + vh - 46), "▶  WATCH NEXT", fill=(10, 14, 26), font=_font(34))
    out = OUT_DIR / "end_screen.png"
    img.save(out, "PNG")
    return str(out)


# -- 5. B-roll cutaway frames (data visuals, dashboard, charts) --

def make_broll_dashboard() -> str:
    """Fake dashboard with ascending chart and KPI tiles — pure Pillow."""
    w, h = 1920, 1080
    img = Image.new("RGB", (w, h), (16, 22, 36))
    d = ImageDraw.Draw(img)
    # KPI tiles row at top
    kpis = [
        ("MRR", "$284K", "+18%", (60, 220, 130)),
        ("PIPELINE", "$1.2M", "+34%", (80, 170, 255)),
        ("WIN RATE", "47%", "+9%", (220, 180, 60)),
        ("ACV", "$8.4K", "+22%", (220, 100, 220)),
    ]
    tile_w, tile_h = 380, 180
    for i, (label, val, delta, color) in enumerate(kpis):
        x = 80 + i * (tile_w + 30)
        d.rounded_rectangle([x, 80, x + tile_w, 80 + tile_h], radius=12,
                            fill=(28, 38, 60))
        d.rectangle([x, 80, x + tile_w, 100], fill=color)
        d.text((x + 20, 110), label, fill=(170, 200, 220), font=_font(26))
        d.text((x + 20, 145), val, fill=(255, 255, 255), font=_font(58))
        d.text((x + 20, 215), delta, fill=color, font=_font(28))
    # big ascending chart
    chart_top = 320
    chart_bottom = 880
    chart_left = 120
    chart_right = 1100
    # baseline
    d.line([(chart_left, chart_bottom), (chart_right, chart_bottom)], fill=(80, 90, 110), width=2)
    # bars
    bars = 14
    bw = (chart_right - chart_left) // bars
    base_h = 60
    peak_h = chart_bottom - chart_top - 60
    points = []
    for i in range(bars):
        # exponential-ish growth
        h = base_h + int((peak_h - base_h) * (i / (bars - 1)) ** 1.5)
        x = chart_left + i * bw + 12
        y = chart_bottom - h
        d.rectangle([x, y, x + bw - 24, chart_bottom], fill=(0, 230, 220))
        points.append((x + bw // 2 - 6, y))
    # trend line
    if len(points) > 1:
        d.line(points, fill=(255, 255, 255), width=4)
    # right side: lead funnel mini diagram
    fx = 1240
    funnel = [("TOP OF FUNNEL", "12,400", (80, 170, 255)),
              ("MQL", "3,200", (60, 220, 130)),
              ("SQL", "1,180", (220, 180, 60)),
              ("WON", "$1.2M", (220, 100, 220))]
    for i, (lbl, val, col) in enumerate(funnel):
        y = 280 + i * 140
        d.rounded_rectangle([fx, y, fx + 540, y + 100], radius=8,
                            fill=(28, 38, 60))
        d.rectangle([fx, y, fx + 14, y + 100], fill=col)
        d.text((fx + 36, y + 30), lbl, fill=(170, 200, 220), font=_font(28))
        d.text((fx + 320, y + 22), val, fill=(255, 255, 255), font=_font(44))
    # brand watermark
    d.text((60, h - 60), "EMPIRE AI  •  Predictive Revenue Intelligence",
           fill=(170, 200, 220), font=_font(22))
    out = OUT_DIR / "broll_dashboard.png"
    img.save(out, "PNG")
    return str(out)


def make_broll_data_table() -> str:
    """B-roll: data table showing qualified vs unqualified leads."""
    w, h = 1920, 1080
    img = Image.new("RGB", (w, h), (12, 18, 30))
    d = ImageDraw.Draw(img)
    # title
    d.text((100, 80), "BEFORE vs AFTER EMPIRE AI", fill=(255, 255, 255), font=_font(58))
    # table headers
    headers = ["METRIC", "BEFORE", "AFTER", "LIFT"]
    col_w = [440, 380, 380, 260]
    x0 = 100
    y0 = 240
    row_h = 110
    # header row
    d.rectangle([x0, y0, x0 + sum(col_w), y0 + row_h], fill=(28, 38, 60))
    for h_idx, h_lbl in enumerate(headers):
        cx = x0 + sum(col_w[:h_idx]) + 30
        d.text((cx, y0 + 36), h_lbl, fill=(170, 200, 220), font=_font(28))
    # rows
    rows = [
        ("MQL CONVERSION", "8%", "47%", "+488%", (60, 220, 130)),
        ("PIPELINE VALUE", "$240K", "$1.2M", "+400%", (220, 180, 60)),
        ("WIN RATE", "12%", "47%", "+292%", (80, 170, 255)),
        ("DEAL CYCLE", "94d", "31d", "-67%", (220, 100, 220)),
        ("REP HOURS/WK", "62", "9", "-85%", (60, 220, 130)),
    ]
    for i, (m, b, a, lift, col) in enumerate(rows):
        y = y0 + (i + 1) * row_h
        # alt row bg
        if i % 2 == 0:
            d.rectangle([x0, y, x0 + sum(col_w), y + row_h], fill=(22, 30, 48))
        d.text((x0 + 30, y + 36), m, fill=(255, 255, 255), font=_font(32))
        d.text((x0 + col_w[0] + 30, y + 36), b, fill=(180, 180, 180), font=_font(32))
        d.text((x0 + col_w[0] + col_w[1] + 30, y + 36), a, fill=(255, 255, 255), font=_font(32, bold=True))
        # lift chip
        lx = x0 + col_w[0] + col_w[1] + col_w[2] + 30
        d.rounded_rectangle([lx, y + 30, lx + 220, y + 80], radius=8, fill=col)
        d.text((lx + 30, y + 36), lift, fill=(10, 14, 26), font=_font(28, bold=True))
    # watermark
    d.text((60, h - 60), "EMPIRE AI  •  Predictive Revenue Intelligence",
           fill=(170, 200, 220), font=_font(22))
    out = OUT_DIR / "broll_data_table.png"
    img.save(out, "PNG")
    return str(out)


# Run all at import time to materialize PNGs
if __name__ == "__main__":
    print("logo:", make_logo_watermark())
    print("subscribe frames:", len(make_subscribe_button_frames()))
    print("name plate:", make_name_plate("Phillip Livesley", "Founder, Empire AI"))
    print("end screen:", make_end_screen([
        "How we 10X'd pipeline with one AI agent",
        "Inside the Empire AI scoring model",
    ]))
    print("broll_dashboard:", make_broll_dashboard())
    print("broll_data_table:", make_broll_data_table())
