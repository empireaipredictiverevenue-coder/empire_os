"""Five independently licensed photographs for the original Chicago evidence cards.

Owner-only offline review export. This DOES NOT edit source claims, sign rights,
modify original five campaigns, mint permission or publish any website asset.
"""
from __future__ import annotations

import base64
from hashlib import sha256
from html import escape
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess

V16_SOURCE_SHA = "93c9f75a56b93cf4fde40656d177d734bf2814afd39ffe84bfd4d71555b15275"
EVIDENCE = [
    ("Roof replacement work", "Roofers at work · illustrative",
     "Public Domain Images", "Public domain",
     "https://commons.wikimedia.org/wiki/File:Roofing_contractors.jpg",
     "https://creativecommons.org/publicdomain/mark/1.0/"),
    ("Permit guidance", "Actual Chicago City Hall",
     "ajay_suresh", "CC BY 2.0",
     "https://commons.wikimedia.org/wiki/File:Chicago_City_Hall_(51575574600).jpg",
     "https://creativecommons.org/licenses/by/2.0/"),
    ("Property permit status", "Construction site in Eugene, Oregon · illustrative",
     "Visitor7", "CC BY-SA 3.0",
     "https://commons.wikimedia.org/wiki/File:Construction_Site.jpg",
     "https://creativecommons.org/licenses/by-sa/3.0/"),
    ("Contractor licensing", "Roofing installation in Indiana · illustrative",
     "Paul West", "CC BY-SA 4.0",
     "https://commons.wikimedia.org/wiki/File:Shingle-roof-contractor.jpg",
     "https://creativecommons.org/licenses/by-sa/4.0/"),
    ("Jurisdiction & ZIP checks", "Chicago West Lawn neighbourhood · illustrative",
     "Alfred Twu", "CC0 1.0",
     "https://commons.wikimedia.org/wiki/File:08-chicago-westlawn-s-pulaski-ave.jpg",
     "https://creativecommons.org/publicdomain/zero/1.0/"),
]

STYLE = """
/* Five actual photographs: each distinct, captioned and attached to the correct original evidence note. */
#research-method .evidence-visual {
    margin:-16px -16px 17px;
    border-radius:13px;
    overflow:hidden;
    border:1px solid #38a3db65;
    background:#04102a;
    position:relative;
}
#research-method .evidence-visual img {
    display:block;width:100%;height:auto;aspect-ratio:16/9;
    object-fit:cover;
    filter:saturate(.92) contrast(1.08);
}
#research-method .evidence-visual figcaption {
    padding:8px 11px 10px;
    line-height:1.32;font-size:.64rem;
    color:#d4e9ff;
    background:linear-gradient(110deg,#04152af0,#0c305ae9);
    min-height:42px;
}
#research-method .evidence-visual figcaption a {
    color:#a9e8ff;
    text-decoration-thickness:1px;
    text-underline-offset:2px;
}
#research-method .fact {overflow:hidden}
#research-method .fact .source {font-size:.76rem!important}
@media(min-width:2560px) {
    #research-method .evidence-visual {margin:-28px -28px 22px;border-radius:18px}
    #research-method .evidence-visual figcaption {font-size:1.05rem;padding:14px 18px;min-height:63px}
}
@media(max-width:540px) {
    #research-method .evidence-visual {margin:-18px -18px 16px}
    #research-method .evidence-visual figcaption {font-size:.75rem}
}
"""


def _webp(photo: bytes, width: int, quality: int) -> bytes:
    """Use the original Ubuntu ffmpeg installation; no new Python dependencies."""
    height=round(width*9/16)
    command=[
        "ffmpeg","-hide_banner","-loglevel","error",
        "-f","image2pipe","-i","pipe:0",
        "-vf",f"scale={width}:{height}:force_original_aspect_ratio=increase,"
              f"crop={width}:{height},setsar=1",
        "-frames:v","1","-c:v","libwebp","-lossless","0",
        "-quality",str(quality),"-compression_level","6",
        "-f","image2pipe","pipe:1",
    ]
    result=subprocess.run(command,input=photo,stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,check=True,timeout=25)
    if not result.stdout.startswith(b"RIFF") or b"WEBP" not in result.stdout[:16]:
        raise ValueError("Actual ffmpeg WebP output was not generated")
    return result.stdout


def enrich(original_html: bytes, image_dir: Path) -> tuple[bytes, dict]:
    if sha256(original_html).hexdigest() != V16_SOURCE_SHA:
        raise ValueError("Source must be the exact V16 original-owner reviewed export")
    html = original_html.decode("utf-8")
    all_photos = list(re.finditer(
        r"data:image/(?:webp|png);base64,([A-Za-z0-9+/=]+)", html
    ))
    if len(all_photos) != 3:
        raise ValueError("Three existing original owner assets required")
    # Never touch the original orbital-A logo. Reduce existing photographic
    # WebP sources only to keep this standalone offline review bounded.
    reductions = [(all_photos[0], 900, 24), (all_photos[2], 600, 24)]
    for match, width, quality in reversed(reductions):
        raw=base64.b64decode(match.group(1))
        optimized=_webp(raw,width,quality)
        old=match.group(1)
        html=html.replace(old,base64.b64encode(optimized).decode(),1)

    if html.count('<article class="fact">') != 5:
        raise ValueError("Refusing replacement unless exactly five evidence notes exist")
    provenance=[]
    for number, (title,label,artist,licence,source,licence_url) in enumerate(EVIDENCE,1):
        path=image_dir/f"candidate_{number}.jpg"
        if not path.is_file() or path.is_symlink():
            raise ValueError("Source imagery must be a regular licensed local photograph")
        original=path.read_bytes()
        compressed=_webp(original,520,21)
        data=base64.b64encode(compressed).decode()
        description=(
            f'<figure class="evidence-visual">'
            f'<img src="data:image/webp;base64,{data}" '
            f'alt="{escape(label,quote=True)}" width="520" height="292" '
            f'loading="lazy" decoding="async">'
            f'<figcaption>{escape(label)} · '
            f'<a href="{escape(source,quote=True)}" rel="noopener noreferrer" '
            f'target="_blank">{escape(artist)}</a> · '
            f'<a href="{escape(licence_url,quote=True)}" rel="noopener noreferrer" '
            f'target="_blank">{escape(licence)}</a> '
            f'· cropped for layout; photo is not the official research record'
            f'</figcaption></figure>'
        )
        marker=f'<article class="fact"><span class="micro">Evidence note {number}</span>'
        if html.count(marker)!=1: raise ValueError("Evidence note markup changed")
        html=html.replace(marker,
                          '<article class="fact">'+description+
                          f'<span class="micro">Evidence note {number}</span>',1)
        provenance.append({
            "evidence_note":number,"subject":title,"alt":label,
            "copyright_holder":artist,"license":licence,"source_url":source,
            "license_url":licence_url,
            "original_download_sha256":sha256(original).hexdigest(),
            "embedded_webp_sha256":sha256(compressed).hexdigest(),
            "embedded_webp_bytes":len(compressed),
        })

    if html.count("</style>") !=1:
        raise ValueError("Expected one original CSS style closing tag")
    html=html.replace("</style>",STYLE+"</style>",1)
    if ("noindex,nofollow,noarchive" not in html
         or "<script" in html.lower()
         or "<form" in html.lower()
         or html.count('class="evidence-visual"') !=5
         or html.count("Read official source")!=5
         or html.count("data:image/png;base64,")!=1):
        raise ValueError("Safety, brand or original official research integrity changed")
    output=html.encode("utf-8")
    result={
        "schema_version":"empire.chicago.original_owner_evidence_photos_v17",
        "status":"PRIVATE_CINEMATIC_REVIEW_NOT_LIVE",
        "source_html_sha256":V16_SOURCE_SHA,
        "output_html_sha256":sha256(output).hexdigest(),
        "output_bytes":len(output),
        "five_evidence_photos":provenance,
        "photo_credit_links":10,
        "remote_image_requests":0,
        "original_official_source_links":5,
        "original_campaign_count_modified":0,
        "live_publication":False,
        "brand_media_owner_signoff":False,
        "seo_owner_signoff":False,
    }
    return output,result
