"""branding_utils.py - Video branding overlays for Empire OS autopilot pipeline

Generated with branding overlay system for sponsor logos, company branding,
and text overlays integrated into Empire OS video pipeline.
"""

import os
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BRANDING_DIR = Path("/root/app/artwork")
LOGO_DIR = BRANDING_DIR / "logos"
BRANDING_DIR.mkdir(parents=True, exist_ok=True)

# Try to load a system font, fallback to default if needed
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
except:
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 40)
    except:
        font = ImageFont.load_default()

font_small = ImageFont.load_default()
font_large = font

def get_brand_overlay(script, platform="youtube"):
    """
    Generate branding overlay for Empire OS video pipeline.

    Args:
        script (dict): Script data containing title, phone, hashtags
        platform (str): Platform target ('youtube' or 'tiktok')

    Returns:
        Image: PIL Image with branding overlay applied
    """
    # Load sponsor logo if available
    sponsor_path = LOGO_DIR / "vonage.png"
    if sponsor_path.exists():
        sponsor_img = Image.open(sponsor_path)
    else:
        sponsor_img = Image.new('RGB', (200, 80), (40, 40, 40))

    # Load company logo if available
    company_path = LOGO_DIR / "empire-ai-logo.svg.png"
    if company_path.exists():
        company_img = Image.open(company_path)
    else:
        company_img = Image.new('RGB', (180, 60), (20, 20, 20))

    # Prepare text overlays
    phone = script.get("phone", "")
    title = script.get("title", "")
    hashtag = f"#EmpireOS #AI #Automation"

    # Set video dimensions based on platform (PIL needs pixels)
    img_width = 1080 if platform == "tiktok" else 720
    img_height = 1920 if platform == "tiktok" else 1080

    # Create main canvas
    canvas = Image.new('RGB', (img_width, img_height), (10, 10, 10))

    # Paste sponsor logo (top-right)
    canvas.paste(sponsor_img, (img_width - sponsor_img.width, 0))

    # Paste company logo (bottom-left)
    canvas.paste(company_img, (0, img_height - company_img.height))

    # Create text overlay with semi-transparent background
    overlay = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # First line: "AI Automation Close Deals – phone"
    draw.rectangle((20, 20, img_width - 20, 100), fill=(0, 0, 0, 200))
    draw.text((30, 50), f"AI Automation Close Deals – {phone}", font=font_small, fill=(255, 255, 255))

    # Title line (bigger)
    draw.rectangle((20, img_height - 100, img_width - 20, img_height - 20), fill=(0, 0, 0, 200))
    draw.text((30, img_height - 60), title, font=font_large, fill=(255, 255, 255))

    # Hashtags
    draw.text((30, img_height - 20), hashtag, font=font_small, fill=(200, 200, 200))

    # Apply overlay to main canvas
    canvas.paste(overlay, (0, 0), overlay)

    return canvas

def get_brand_overlay_from_file(script, platform="youtube", output_path="/tmp/brand_overlay.png"):
    """
    Generate and save branding overlay to file.

    Args:
        script (dict): Script data containing title, phone, hashtags
        platform (str): Platform target ('youtube' or 'tiktok')
        output_path (str): Path to save the overlay image

    Returns:
        Image: PIL Image with branding overlay applied
    """
    overlay = get_brand_overlay(script, platform)
    overlay.save(output_path)
    return overlay

if __name__ == "__main__":
    # Quick test
    test_script = {
        "phone": "833-274-7100",
        "title": "Test Title"
    }

    print("Creating brand overlay...")
    overlay = get_brand_overlay(test_script, platform="youtube")
    overlay.save("/tmp/test_brand_overlay.png")
    print(f"Brand overlay generated: /tmp/test_brand_overlay.png")
    print(f"Overlay size: {overlay.size}")
    print("Assets directory:", BRANDING_DIR)
    print("Logo directory:", LOGO_DIR)
    print("Available assets:", os.listdir(BRANDING_DIR) if BRANDING_DIR.exists() else "None")
