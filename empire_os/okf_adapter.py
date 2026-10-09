"""Private OKF v0.2 export of Buyer Scout research; no commercial authority."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit
import json
import os
import re
import shutil
import tempfile

import yaml
from empire_os.buyer_claim_provenance import verified_direct_purchase_receipt

EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
HASH = re.compile(r"[a-f0-9]{64}\Z")
PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{8,}\d)(?!\w)")
VERSION = "0.2"


def moment(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def public_url(value: Any, expected: str) -> str | None:
    try:
        raw = str(value or "")
        u = urlsplit(raw)
        host = (u.hostname or "").casefold().rstrip(".").removeprefix("www.")
        if (u.scheme not in {"http", "https"} or not host or host != expected
            or u.username or u.password or u.port not in (None, 80, 443)
            or u.query or u.fragment or len(raw) > 850
            or EMAIL.search(raw)
            or any(part in u.path.lower() for part in (
                "/people/", "/team/", "/staff/", "/profile/", "/employee/"))):
            return None
        return u.geturl()
    except ValueError:
        return None


def company_host(row: Mapping[str, Any]) -> str:
    website = str(row.get("website") or "")
    try:
        u = urlsplit(website)
        host = (u.hostname or "").lower().rstrip(".").removeprefix("www.")
        declared = str(row.get("domain") or "").lower().rstrip(".").removeprefix("www.")
        if (u.scheme not in {"http", "https"} or not host or host != declared
            or u.username or u.password or u.port not in (None, 80, 443)
            or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,251}[a-z0-9]", host)):
            return ""
        return host
    except ValueError:
        return ""


def frontmatter(data: Mapping[str, Any]) -> str:
    return "---\n" + yaml.safe_dump(dict(data), sort_keys=False,
        allow_unicode=True) + "---\n\n"


def documents_from_scout(
    scout: Mapping[str, Any], *, now: datetime, limit: int = 30,
) -> dict[str, str]:
    """Explicitly research-only. No contact details or direct buying authority."""
    rows = scout.get("candidates")
    if not isinstance(rows, list) or now.tzinfo is None:
        raise ValueError("invalid_scout_or_clock")
    out: dict[str, str] = {}
    for row in rows[:max(0, min(limit, 30))]:
        if not isinstance(row, Mapping):
            continue
        host = company_host(row)
        if not host or host in out:
            continue
        packet = row.get("buyer_claim_provenance")
        packet = packet if isinstance(packet, Mapping) else {}
        raw = packet.get("claim_receipts")
        raw = raw if isinstance(raw, list) else []
        receipts = []
        for item in raw[:5]:
            if not isinstance(item, Mapping):
                continue
            source = public_url(item.get("source_url"), host)
            date = moment(item.get("observed_at"))
            digest = str(item.get("content_sha256") or "")
            if not source or not date or not HASH.fullmatch(digest):
                continue
            if date > now + timedelta(minutes=5):
                continue
            receipts.append((source, date, digest, item))
        relationship = str(packet.get("buyer_relationship") or "unknown")
        allowed = {"unknown", "direct_inventory_buyer", "intermediary_or_marketplace",
                   "lead_supplier_or_publisher", "mixed_role_requires_review"}
        if relationship not in allowed:
            relationship = "unknown"
        confirmed = verified_direct_purchase_receipt(
            {"buyer_claim_provenance": packet},
            company_website=str(row.get("website") or ""), now=now,
        )
        if relationship == "direct_inventory_buyer" and not confirmed:
            relationship = "unknown"
        meta = {
            "type": "Buyer Demand Research",
            "title": f"Commercial source research for {host}",
            "description": "Source-linked research; not verified buyer or outbound approval.",
            "resource": f"https://{host}/",
            "tags": ["empire-os", "buyer-evidence", "research-only"],
            "status": "draft",
            "generated": {"by": "process:empire-okf-export", "at": iso(now)},
            "sources": [
                {"id": f"source-{i}", "resource": url, "title": "First-party commercial page"}
                for i, (url, _, _, _) in enumerate(receipts, 1)
            ],
            "empire_policy_authority": "none",
            "empire_canonical_system": "EmpireDB",
            "empire_observed_relationship": relationship,
            "empire_purchase_statement_observed": bool(confirmed),
        }
        if receipts:
            meta["stale_after"] = iso(max(x[1] for x in receipts) + timedelta(days=30))
        text = "# Commercial evidence\n\nResearch only: no customer, consent, purchasing"
        text += " transaction or execution authority has been verified.\n\n"
        text += f"## Relationship\n\n{relationship.replace('_', ' ')}.\n\n"
        if not receipts:
            text += "No source-backed commercial claims available.\n"
        for i, (_, observed, digest, item) in enumerate(receipts, 1):
            excerpt = EMAIL.sub("[email redacted]", " ".join(
                str(item.get("claim_excerpt") or "").split())[:200])
            excerpt = PHONE.sub("[phone redacted]", excerpt)
            for person in row.get("first_party_people") or []:
                if isinstance(person, Mapping):
                    name = str(person.get("name") or "").strip()
                    if len(name) >= 5:
                        excerpt = re.sub(re.escape(name), "[name redacted]",
                                         excerpt, flags=re.IGNORECASE)
            excerpt = excerpt.replace("[", "\\[").replace("]", "\\]")
            text += (f"- Observed {iso(observed)}. Source-text SHA-256:"
                     f" `{digest}`. Excerpt: {excerpt}.[^source-{i}]\n")
        if receipts:
            text += "\n" + "".join(
                f"[^source-{i}]: First-party source page {i}.\n"
                for i in range(1, len(receipts) + 1)
            )
        out[f"buyers/{host}.md"] = frontmatter(meta) + text
    return out


def export_private_bundle(
    scout_path: Path, output_root: Path, *, now: datetime,
    limit: int = 30,
) -> dict[str, Any]:
    """Atomic create-only private export. No operational database writes."""
    scout = json.loads(Path(scout_path).read_text(encoding="utf-8"))
    docs = documents_from_scout(scout, now=now, limit=limit)
    root = Path(output_root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink():
        raise ValueError("symlink_output_root_denied")
    target = root / ("run-" + iso(now).replace("-", "").replace(":", ""))
    if target.exists() or target.is_symlink():
        raise FileExistsError("bundle_run_already_exists")
    temp = Path(tempfile.mkdtemp(prefix=".okf-staging-", dir=root))
    try:
        (temp / "buyers").mkdir(mode=0o700)
        index = '---\nokf_version: "0.2"\n---\n\n# Private EmpireOS buyer research\n\n'
        for name, content in sorted(docs.items()):
            dest = temp / name
            dest.write_text(content, encoding="utf-8")
            dest.chmod(0o600)
            index += f"- [Research for {dest.stem}](/{name}) — unverified.\n"
        (temp / "index.md").write_text(index, encoding="utf-8")
        (temp / "index.md").chmod(0o600)
        hashes = {
            f.relative_to(temp).as_posix(): sha256(f.read_bytes()).hexdigest()
            for f in sorted(temp.rglob("*.md"))
        }
        manifest = {
            "schema": "empire.okf.private.v1", "okf_version": VERSION,
            "concept_count": len(docs), "files_sha256": hashes,
            "authority": "none", "visibility": "private",
            "source_name": Path(scout_path).name,
        }
        (temp / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (temp / "manifest.json").chmod(0o600)
        os.replace(temp, target)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return {"bundle_path": str(target), "concept_count": len(docs),
            "authority": "none", "db_writes": 0, "outbound_sent": 0}


def verify_bundle_files(root: Path) -> int:
    """Check exported file digests before a reader uses their metadata."""
    manifest = json.loads((root / "manifest.json").read_text())
    if (manifest.get("schema") != "empire.okf.private.v1"
        or manifest.get("okf_version") != VERSION
        or manifest.get("visibility") != "private"
        or manifest.get("authority") != "none"
        or not isinstance(manifest.get("files_sha256"), dict)):
        raise ValueError("untrusted_bundle_manifest")
    count = 0
    for name, digest in manifest["files_sha256"].items():
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("unsafe_path")
        item = root / name
        if item.is_symlink() or sha256(item.read_bytes()).hexdigest() != digest:
            raise ValueError("integrity_check_failed")
        count += int(name != "index.md")
    return count

def catalogue_summary(root: Path, *, now: datetime | None = None) -> dict:
    """Only advisory trust and freshness; never authorises agent execution."""
    count = verify_bundle_files(root)
    now = now or datetime.now(timezone.utc)
    fresh = 0
    stale = 0
    for file in (root / "buyers").glob("*.md"):
        content = file.read_text(encoding="utf-8")
        header = content.split("---", 2)[1] if content.startswith("---") else ""
        metadata = yaml.safe_load(header)
        if not isinstance(metadata, dict) or metadata.get("status") != "draft":
            raise ValueError("untrusted_okf_status")
        if "verified" in metadata or metadata.get("empire_policy_authority") != "none":
            raise ValueError("policy_escalation_denied")
        expires = moment(metadata.get("stale_after"))
        fresh += int(expires is not None and now < expires)
        stale += int(expires is None or now >= expires)
    if fresh + stale != count:
        raise ValueError("count_mismatch")
    return {"concepts": count, "fresh": fresh, "stale_or_undated": stale,
            "trust": "unverified", "execution_authority": "none",
            "mode": "OBSERVE"}


def list_private_research(
    root: Path, *, now: datetime, max_results: int = 30,
) -> dict[str, Any]:
    """Read-only SkillForge/Astra research surface, without source-page bodies."""
    if now.tzinfo is None:
        raise ValueError("aware_clock_required")
    root = Path(root)
    verified_count = verify_bundle_files(root)
    items = []
    for path in sorted((root / "buyers").glob("*.md"))[:max(0, min(max_results, 30))]:
        content = path.read_text(encoding="utf-8")
        if not content.startswith("---\n"):
            raise ValueError("invalid_frontmatter")
        meta = yaml.safe_load(content.split("---", 2)[1])
        if not isinstance(meta, Mapping) or meta.get("type") != "Buyer Demand Research":
            raise ValueError("invalid_research_type")
        if meta.get("status") != "draft" or "verified" in meta:
            raise ValueError("authority_escalation_denied")
        if meta.get("empire_policy_authority") != "none":
            raise ValueError("authority_escalation_denied")
        source_list = meta.get("sources")
        if not isinstance(source_list, list):
            raise ValueError("missing_sources")
        host = path.stem
        safe_sources = []
        for src in source_list[:5]:
            if not isinstance(src, Mapping):
                raise ValueError("invalid_source")
            url = public_url(src.get("resource"), host)
            if url is None:
                raise ValueError("untrusted_source")
            safe_sources.append(url)
        expiry = moment(meta.get("stale_after"))
        items.append({
            "concept_id": f"buyers/{host}",
            "relationship": str(meta.get("empire_observed_relationship") or "unknown"),
            "trust": "unverified",
            "fresh": expiry is not None and now < expiry,
            "sources": safe_sources,
            "execution_authority": "none",
        })
    return {
        "concept_count": verified_count,
        "results": items,
        "status": "research_only",
        "execution_authority": "none",
    }
