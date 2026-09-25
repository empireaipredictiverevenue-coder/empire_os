"""Bounded public sensor adapter inspired by Agent Reach channel policy.

Only zero-credential public lanes are enabled here:
- web_read via Jina Reader
- youtube_search via the Agent Reach venv's yt-dlp
- github_search via public GitHub REST
- rss_read via stdlib XML parsing

Authenticated/cookie-backed channels require a separate architecture contract.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import socket
import subprocess
from typing import Any
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


YT_DLP = Path("/opt/empire/agent-reach/venv/bin/yt-dlp")
USER_AGENT = "EmpireOS-AgentReach-Sensor/1.0"


class AgentReachSensorError(RuntimeError):
    pass


@dataclass(frozen=True)
class SensorObservation:
    channel: str
    query: str
    observed_at: str
    source_url: str | None
    payload: Any
    provenance: str
    truth_authority: str = "none"
    commercial_intent_proven: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_public_http_url(value: str) -> str:
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AgentReachSensorError("public http(s) URL required")
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise AgentReachSensorError("local/private targets are forbidden")
    try:
        literal = ipaddress.ip_address(host)
        if not literal.is_global:
            raise AgentReachSensorError("local/private targets are forbidden")
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise AgentReachSensorError("hostname resolution failed") from exc
        for info in infos:
            try:
                address = ipaddress.ip_address(info[4][0])
            except ValueError:
                continue
            if not address.is_global:
                raise AgentReachSensorError("local/private targets are forbidden")
    return raw


def _get_json(url: str, *, timeout: int = 15) -> Any:
    target = _validate_public_http_url(url)
    req = Request(
        target,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    with urlopen(req, timeout=max(2, min(timeout, 30))) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def read_public_web(url: str, *, timeout: int = 20) -> SensorObservation:
    target = _validate_public_http_url(url)
    jina = f"https://r.jina.ai/{target}"
    req = Request(jina, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=max(2, min(timeout, 30))) as response:
        text = response.read().decode("utf-8", errors="replace")
    return SensorObservation(
        channel="web",
        query=target,
        observed_at=_now(),
        source_url=target,
        payload={"text": text[:200_000]},
        provenance="jina_reader",
    )


def search_youtube(
    query: str,
    *,
    limit: int = 5,
    timeout: int = 30,
) -> SensorObservation:
    clean = str(query or "").strip()
    if not clean:
        raise AgentReachSensorError("youtube query required")
    if not YT_DLP.exists():
        raise AgentReachSensorError("yt-dlp is not installed")
    count = max(1, min(int(limit), 10))
    result = subprocess.run(
        [
            str(YT_DLP),
            "--dump-single-json",
            "--flat-playlist",
            "--no-warnings",
            f"ytsearch{count}:{clean}",
        ],
        capture_output=True,
        text=True,
        timeout=max(5, min(timeout, 60)),
        check=False,
        env={
            "HOME": "/var/lib/empire/agent-reach/home",
            "PATH": "/usr/bin:/bin:/opt/empire/agent-reach/venv/bin",
        },
    )
    if result.returncode != 0:
        raise AgentReachSensorError("youtube backend failed")
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AgentReachSensorError("invalid youtube backend output") from exc
    rows = []
    for entry in raw.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        rows.append({
            "id": entry.get("id"),
            "title": entry.get("title"),
            "url": entry.get("url") or entry.get("webpage_url"),
            "channel": entry.get("channel") or entry.get("uploader"),
            "duration": entry.get("duration"),
        })
    return SensorObservation(
        channel="youtube",
        query=clean,
        observed_at=_now(),
        source_url="https://www.youtube.com/results",
        payload={"results": rows[:count]},
        provenance="yt_dlp_search",
    )


def search_public_github(
    query: str,
    *,
    limit: int = 5,
    timeout: int = 20,
) -> SensorObservation:
    clean = str(query or "").strip()
    if not clean:
        raise AgentReachSensorError("github query required")
    count = max(1, min(int(limit), 10))
    url = (
        "https://api.github.com/search/repositories?"
        + urlencode({
            "q": clean,
            "per_page": count,
            "sort": "updated",
            "order": "desc",
        })
    )
    raw = _get_json(url, timeout=timeout)
    rows = []
    for item in raw.get("items") or []:
        if not isinstance(item, dict):
            continue
        rows.append({
            "full_name": item.get("full_name"),
            "html_url": item.get("html_url"),
            "description": item.get("description"),
            "stargazers_count": item.get("stargazers_count"),
            "updated_at": item.get("updated_at"),
        })
    return SensorObservation(
        channel="github",
        query=clean,
        observed_at=_now(),
        source_url=url,
        payload={"results": rows[:count]},
        provenance="github_public_rest",
    )


def read_public_rss(
    url: str,
    *,
    limit: int = 10,
    timeout: int = 20,
) -> SensorObservation:
    target = _validate_public_http_url(url)
    req = Request(target, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=max(2, min(timeout, 30))) as response:
        data = response.read(2_000_000)
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise AgentReachSensorError("invalid RSS/Atom XML") from exc

    rows: list[dict[str, Any]] = []
    for item in root.findall(".//item"):
        rows.append({
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "published": (
                item.findtext("pubDate")
                or item.findtext("date")
                or ""
            ).strip(),
        })
    if not rows:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//a:entry", ns):
            link = entry.find("a:link", ns)
            rows.append({
                "title": (entry.findtext("a:title", default="", namespaces=ns)).strip(),
                "link": (link.attrib.get("href", "") if link is not None else "").strip(),
                "published": (
                    entry.findtext("a:published", default="", namespaces=ns)
                    or entry.findtext("a:updated", default="", namespaces=ns)
                ).strip(),
            })

    count = max(1, min(int(limit), 25))
    return SensorObservation(
        channel="rss",
        query=target,
        observed_at=_now(),
        source_url=target,
        payload={"entries": rows[:count]},
        provenance="rss_atom_public",
    )


def run_public_sensor(
    channel: str,
    query: str,
    *,
    limit: int = 5,
) -> dict[str, Any]:
    key = str(channel or "").strip().lower()
    if key == "web":
        observation = read_public_web(query)
    elif key == "youtube":
        observation = search_youtube(query, limit=limit)
    elif key == "github":
        observation = search_public_github(query, limit=limit)
    elif key == "rss":
        observation = read_public_rss(query, limit=limit)
    else:
        raise AgentReachSensorError("unsupported or credentialed channel")
    return {
        "schema_version": "empire.agent-reach-observation.v1",
        "observation": observation.as_dict(),
        "source_class": "OBSERVED_PUBLIC",
        "requires_quality_gate": True,
        "canonical_write_performed": False,
        "outbound_action_performed": False,
        "execution_authority": "none",
    }
