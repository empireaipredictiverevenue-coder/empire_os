"""Bounded original-page passage anchors using existing BeautifulSoup (MIT).

Only short direct excerpts from original approved URLs. A verbatim substring
with a page checksum is traceable, but NOT proof the publisher's claim is
true or that publisher content is licensed for client redistribution.
"""
from __future__ import annotations

from hashlib import sha256
from html import unescape
import re

from bs4 import BeautifulSoup

TERMS = (
    "dental implants", "implant placement", "implant surgery",
    "surgeon", "dentures", "3d mapping", "full arch",
    "private dental services", "market study", "price transparency",
)
MAX_DOCUMENT_BYTES = 600_000
MAX_EXCERPT_CHARS = 165
MAX_EXCERPT_WORDS = 25
MAX_ANCHORS = 8


def extract_source_passage_anchors(html_bytes: bytes) -> list[dict]:
    """Return up to eight short original-page source anchors, never claims."""
    if (not isinstance(html_bytes, bytes) or not html_bytes
            or len(html_bytes) > MAX_DOCUMENT_BYTES):
        raise ValueError("BOUNDED_ORIGINAL_DOCUMENT_BYTES_REQUIRED")
    text = html_bytes.decode("utf-8", errors="replace")
    soup = BeautifulSoup(text, "html.parser")
    for node in list(soup.find_all(
        ["script", "style", "noscript", "nav", "footer", "header",
         "svg", "form", "iframe", "aside"]
    )):
        node.decompose()
    for node in list(soup.select('[aria-hidden="true"], [hidden]')):
        node.decompose()
    area = soup.select_one("main") or soup.select_one("article") or soup.body or soup
    blocks: list[str] = []
    seen: set[str] = set()
    for node in area.find_all(("h1", "h2", "h3", "p", "li"), limit=1800):
        block = " ".join(unescape(node.get_text(" ", strip=True)).split())
        if not 25 <= len(block) <= 3000 or block in seen:
            continue
        seen.add(block)
        blocks.append(block)
    anchors = []
    for term in TERMS:
        occurrences = []
        needle = re.compile(r"(?<![a-zA-Z])" + re.escape(term) + r"(?![a-zA-Z])",
                            re.IGNORECASE)
        for block in blocks:
            match = needle.search(block)
            if not match:
                continue
            # Prefer a short paragraph, not an entire navigation or SEO footer.
            start = max(0, match.start() - 70)
            end = min(len(block), match.end() + 80)
            excerpt = block[start:end].strip()
            if start:
                excerpt = excerpt.lstrip(" .,;:-")
            if end < len(block):
                excerpt = excerpt.rstrip(" .,;:-")
            words = excerpt.split()
            if len(words) > MAX_EXCERPT_WORDS:
                relative = next((i for i,w in enumerate(words)
                                 if term.split()[0].casefold() in w.casefold()), 0)
                begin = max(0, relative - 8)
                excerpt = " ".join(words[begin:begin + MAX_EXCERPT_WORDS])
            excerpt = excerpt[:MAX_EXCERPT_CHARS].strip()
            if needle.search(excerpt):
                occurrences.append((len(block), excerpt))
        if occurrences:
            _, best = min(occurrences, key=lambda pair: pair[0])
            anchors.append({
                "term": term,
                "original_page_excerpt": best,
                "excerpt_sha256": sha256(best.encode("utf-8")).hexdigest(),
                "support_level": "VERBATIM_PUBLISHER_WORDS_ONLY",
                "publisher_claim_truth_verified": False,
                "client_republication_rights_verified": False,
            })
        if len(anchors) >= MAX_ANCHORS:
            break
    return anchors
