"""Normalize public auto-captions into cited video-learning evidence.

Keeps timestamped source anchors; source claims are hypotheses, not verified
revenue facts, deployment approvals or model-training instructions.
"""
from __future__ import annotations
import html
import re
from collections.abc import Mapping

TIME = re.compile(r"^(\d\d:\d\d:\d\d\.\d{3}) -->")
TAG = re.compile(r"<[^>]*>")
KEYWORDS = ("quote", "estimate", "trial", "client", "lead", "price", "payment",
            "profit", "follow", "offer", "sms", "appointment", "customer")


def normalize_vtt(source: str) -> list[dict[str, str]]:
    if not isinstance(source, str) or not source.lstrip().startswith("WEBVTT"):
        raise ValueError("WebVTT captions required")
    blocks = re.split(r"\n\s*\n", source.replace("\r\n", "\n"))
    cues = []
    for block in blocks:
        lines = block.splitlines()
        match_at = next(((n, TIME.match(line)) for n, line in enumerate(lines) if TIME.match(line)), None)
        if not match_at:
            continue
        idx, match = match_at
        payload = " ".join(html.unescape(TAG.sub("", line)).strip()
                           for line in lines[idx+1:] if line.strip())
        payload = re.sub(r"\s+", " ", payload).strip()
        if payload:
            cues.append({"at": match.group(1), "text": payload})
    # Auto-caption rolling windows repeat most words. Keep only incoming tails.
    prior: list[str] = []
    out = []
    for cue in cues:
        words = cue["text"].split()
        overlap = 0
        for n in range(min(len(prior), len(words)), 0, -1):
            if [w.casefold() for w in prior[-n:]] == [w.casefold() for w in words[:n]]:
                overlap = n
                break
        new = words[overlap:]
        if new:
            out.append({"at": cue["at"], "text": " ".join(new)})
        prior = words
    return out


def strategy_evidence(cues: list[Mapping[str, str]], video_id: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("video ID required")
    matches = {term: [] for term in KEYWORDS}
    for cue in cues:
        snippet = cue["text"]
        for term in KEYWORDS:
            if re.search(r"\b" + re.escape(term) + r"s?\b", snippet, flags=re.I):
                if len(matches[term]) < 12:
                    matches[term].append({"timestamp": cue["at"], "snippet": snippet[:180]})
    return {"schema_version": "empire.video_strategy_evidence.v1",
            "video_id": video_id, "source": "youtube_auto_captions",
            "caption_quality": "AUTO_GENERATED_UNVERIFIED",
            "cues": len(cues), "topic_evidence": matches,
            "financial_claims_verified": False,
            "automation_authorized": False,
            "model_promotion_authorized": False}
