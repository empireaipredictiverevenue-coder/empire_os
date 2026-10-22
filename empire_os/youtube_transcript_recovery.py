"""Read-only YouTube caption recovery with explicit failure diagnostics.

Retrieves public caption tracks without credentials or paid APIs. Does not
misrepresent an advertised but empty track as a completed transcript.
"""
from __future__ import annotations
import html
import json
import re
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import Request, urlopen
from xml.etree import ElementTree

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _video_id(raw: str) -> str:
    if VIDEO_ID.fullmatch(raw):
        return raw
    url = urlsplit(raw)
    if url.hostname in ("youtu.be", "www.youtu.be"):
        value = url.path.strip("/").split("/")[0]
    elif url.hostname in ("youtube.com", "www.youtube.com", "m.youtube.com"):
        value = parse_qs(url.query).get("v", [""])[0]
    else:
        value = ""
    if not VIDEO_ID.fullmatch(value):
        raise ValueError("valid public YouTube video ID or URL required")
    return value


def _fetch(url: str, timeout: float) -> bytes:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"})
    with urlopen(req, timeout=timeout) as response:
        return response.read(10 * 1024 * 1024)


def retrieve_public_captions(source: str, *, timeout: float = 12,
                             fetch=None) -> dict:
    video = _video_id(source)
    fetcher = fetch or _fetch
    base = {"video_id": video, "status": "UNAVAILABLE", "text": "",
            "track_count": 0, "reason": "", "source": "public_youtube_captions"}
    try:
        page = fetcher("https://www.youtube.com/watch?v=" + video, timeout).decode("utf-8", "replace")
        match = re.search(r'"captionTracks":(\[.*?\]),"audioTracks"', page)
        if not match:
            return dict(base, reason="No caption tracks found in public player")
        tracks = json.loads(match.group(1))
        base["track_count"] = len(tracks)
        tracks.sort(key=lambda t: (t.get("languageCode") != "en", t.get("kind") == "asr"))
        errors = []
        for track in tracks:
            rawurl = track.get("baseUrl")
            if not isinstance(rawurl, str) or not rawurl.startswith("https://www.youtube.com/api/timedtext?"):
                errors.append("caption URL not a permitted YouTube timedtext endpoint")
                continue
            for suffix in ("", "&fmt=json3"):
                response = fetcher(rawurl + suffix, timeout)
                if not response.strip():
                    errors.append("caption endpoint returned empty body")
                    continue
                try:
                    if response.lstrip().startswith(b"{"):
                        payload = json.loads(response)
                        lines = ["".join(seg.get("utf8", "") for seg in event.get("segs", [])).strip()
                                 for event in payload.get("events", [])]
                    else:
                        root = ElementTree.fromstring(response)
                        lines = ["".join(node.itertext()).strip() for node in root.iter("text")]
                    transcript = "\n".join(html.unescape(line) for line in lines if line)
                    if transcript:
                        return dict(base, status="OK", text=transcript,
                                    language=track.get("languageCode"), reason="")
                    errors.append("caption payload contained no text")
                except (ValueError, ElementTree.ParseError, TypeError, AttributeError):
                    errors.append("caption payload could not be parsed")
        return dict(base, reason="; ".join(dict.fromkeys(errors))[:400])
    except Exception as exc:
        return dict(base, reason="caption retrieval failed: " + type(exc).__name__)
