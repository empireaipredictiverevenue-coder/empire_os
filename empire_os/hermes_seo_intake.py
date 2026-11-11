"""Idempotent daily SEO -> existing Hermes control branch intake.

Invoked *inside* the existing Hermes worker, after its original Git fetch.
No second timer, scraper, datastore, or permitted commercial actions.
Only one OBSERVE research job may be proposed per iteration. A staged
original MediaOS review for the exact page/finding suppresses rework.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import stat
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from empire_os.hermes_control import (
    HermesJob, DEFAULT_BASE_BRANCH, DEFAULT_CONTROL_BRANCH,
    control_path_exists, list_pending_job_paths, publish_control_job,
)

SCHEMA = "empire.hermes.seo_research_intake.v1"
SOURCE_SCHEMA = "empire.search.founder_audit.v1"
SOURCE_ROOT = Path("/home/ubuntu/empire_releases/seo_native_sales_preview_20261108")
INPUT_DIR = Path("runtime/media_os/input")
SITE = "https://empire-ai.co.uk/"
JOB_PREFIX = "hermes-seo-auto-"
REVIEW_PREFIX = "hermes_seo_internal_editorial_review_"
CODES = frozenset({
    "short_primary_content_review",
    "page_title_missing",
    "page_h1_missing",
    "sitemap_page_noindex",
    "sitemap_page_http_error",
    "sitemap_page_nonself_canonical",
    "duplicate_page_title",
    "duplicate_page_description",
})
PRIORITY = {"critical": 0, "high": 1, "medium": 2, "low": 3}
MAX_FINDINGS = 100
MAX_SOURCE = 200_000
MAX_REVIEWS = 50
REVIEW_NAME = re.compile(
    r"^hermes_seo_internal_editorial_review_[0-9a-f]{16}\.json$"
)


class IntakeHeld(ValueError):
    """A source is not safe enough to create an agent research assignment."""


def _owned(url: Any) -> str:
    if not isinstance(url, str) or not 1 <= len(url) <= 500:
        raise IntakeHeld("INVALID_OWNED_URL")
    try:
        u = urlsplit(url)
        if (u.scheme != "https" or u.hostname != "empire-ai.co.uk"
                or u.username or u.password or u.port is not None
                or u.query or u.fragment or not u.path.startswith("/")
                or "//" in u.path):
            raise IntakeHeld("INVALID_OWNED_URL")
    except ValueError as exc:
        raise IntakeHeld("INVALID_OWNED_URL") from exc
    return url


def _load_source(path: Path, *, now: datetime) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise IntakeHeld("DAILY_AUDIT_NOT_AVAILABLE")
    st = path.stat()
    if (not stat.S_ISREG(st.st_mode)
            or not 0 < st.st_size <= MAX_SOURCE
            or st.st_mode & 0o077):
        raise IntakeHeld("DAILY_AUDIT_PERMISSIONS_OR_SIZE")
    try:
        item = json.loads(path.read_text("utf-8"))
    except (ValueError, UnicodeError, OSError) as exc:
        raise IntakeHeld("DAILY_AUDIT_BAD_JSON") from exc
    if not isinstance(item, dict):
        raise IntakeHeld("DAILY_AUDIT_BAD_JSON")
    if (item.get("schema_version") != SOURCE_SCHEMA
            or item.get("site_url") != SITE
            or item.get("source") != "empire_web_intelligence_crawler"
            or item.get("available") is not True
            or item.get("bounded_coverage") is not True
            or item.get("mode") != "OBSERVE"
            or item.get("database_writes") is not False
            or item.get("automated_publication_authorized") is not False
            or item.get("execution_allowed") is not False):
        raise IntakeHeld("DAILY_AUDIT_POLICY_HOLD")
    raw_time = item.get("observed_at")
    try:
        stamp = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError) as exc:
        raise IntakeHeld("DAILY_AUDIT_TIMESTAMP_INVALID") from exc
    if (stamp.tzinfo is None
            or stamp.date() != now.date()
            or not now - timedelta(hours=36) <= stamp <= now + timedelta(minutes=5)):
        raise IntakeHeld("DAILY_AUDIT_NOT_TODAY")
    rows = item.get("findings")
    if (not isinstance(rows, list) or len(rows) > MAX_FINDINGS
            or type(item.get("finding_count")) is not int
            or item["finding_count"] != len(rows)):
        raise IntakeHeld("DAILY_AUDIT_FINDING_COUNT_MISMATCH")
    return item


def _existing_reviews(root: Path) -> set[tuple[str, str]]:
    folder = root / INPUT_DIR
    if not folder.is_dir() or folder.is_symlink():
        raise IntakeHeld("MEDIAOS_REVIEW_INPUT_MISSING")
    paths = list(folder.glob(REVIEW_PREFIX + "*.json"))
    if len(paths) > MAX_REVIEWS:
        raise IntakeHeld("MEDIAOS_REVIEW_CAPACITY_HOLD")
    known = set()
    for path in paths:
        if not REVIEW_NAME.fullmatch(path.name) or path.is_symlink():
            raise IntakeHeld("MEDIAOS_REVIEW_FILENAME_UNTRUSTED")
        st = path.stat()
        if (not stat.S_ISREG(st.st_mode)
                or st.st_mode & 0o077
                or not 0 < st.st_size <= 65536):
            raise IntakeHeld("MEDIAOS_REVIEW_FILE_UNTRUSTED")
        try:
            review = json.loads(path.read_text("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise IntakeHeld("MEDIAOS_REVIEW_FILE_UNTRUSTED") from exc
        if (not isinstance(review, dict)
                or review.get("schema_version") !=
                "empire.media.seo_hermes_editorial_review.v1"
                or review.get("status") != "REVIEW_REQUIRED"
                or review.get("public_publish_authorized") is not False
                or review.get("execution_authority") != "none"
                or review.get("original_owner_editorial_approval") is not False
                or review.get("founder_publication_approval") is not False):
            raise IntakeHeld("MEDIAOS_REVIEW_AUTHORITY_HOLD")
        candidate = (
            _owned(review.get("target_site")),
            review.get("seo_finding_code"),
        )
        if candidate[1] not in CODES:
            raise IntakeHeld("MEDIAOS_REVIEW_CODE_UNKNOWN")
        known.add(candidate)
    return known


def _job_id(url: str, code: str) -> str:
    # Stable across daily audits: the same unreviewed issue is never
    # repeatedly assigned merely because it appeared again at midnight.
    return JOB_PREFIX + sha256(f"{url}\x00{code}".encode()).hexdigest()[:20]


def _build_manifest(
    *, job_id: str, url: str, code: str,
    receipt_digest: str, observed_at: str, now: datetime,
) -> dict[str, Any]:
    # Prompts are templates over validated enum and owned URL only.
    # No untrusted crawler/model content becomes instructions.
    prompt = (
        "OBSERVE-only SEO research for existing Search Fabric / Hermes Oracle. "
        f"Review exactly this first-party source: {url}. "
        f"Classified issue: {code}. "
        "The existing daily bounded SEO audit is "
        f"/home/ubuntu/empire_releases/seo_native_sales_preview_20261108/"
        f"seo-audit-{now.date().isoformat()}.json; "
        f"canonical JSON sha256={receipt_digest}, observed={observed_at}. "
        "If permitted, inspect the source and one safe GET of the owned page; "
        "evaluate buyer value and user intent. Distinguish technical findings "
        "from rank, traffic and qualified lead evidence. Suggest at most "
        "three original-owner-reviewed actions with provenance and uncertainty. "
        "Never guess, publish, send, spend, create files, edit code, access "
        "customer data, modify deployment, or recognise revenue. Report any "
        "unavailable source rather than inventing it."
    )
    raw = {
        "schema_version": "empire.hermes.control_job.v1",
        "job_id": job_id,
        "kind": "code_task",
        "authority": "observe",
        "base_branch": DEFAULT_BASE_BRANCH,
        "allowed_paths": [],
        "lease_resources": [],
        "pytest_targets": [],
        "max_runtime_seconds": 180,
        "ai_behavior_change": False,
        "created_at": now.isoformat(),
        "prompt": prompt,
    }
    validated = HermesJob.from_mapping(raw)
    if (validated.authority != "observe" or validated.allowed_paths
            or validated.lease_resources or validated.max_runtime_seconds > 180):
        raise IntakeHeld("MANIFEST_AUTHORITY_HOLD")
    return raw


def reconcile_seo_intake(
    root: Path, *, now: datetime | None = None,
    publish: bool = False,
    control_branch: str = DEFAULT_CONTROL_BRANCH,
    control_exists: Callable[..., bool] = control_path_exists,
    list_jobs: Callable[..., list[str]] = list_pending_job_paths,
    enqueue: Callable[..., dict[str, Any]] = publish_control_job,
    source_root: Path = SOURCE_ROOT,
) -> dict[str, Any]:
    """Find one new issue, or return a safe no-op. Caller fetched Git first."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    root = Path(root).absolute()
    base = {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "generated_at": current.isoformat(),
        "status": "HELD",
        "source_finding_count": None,
        "eligible_count": 0,
        "already_under_review_count": 0,
        "existing_auto_job_count": 0,
        "published_count": 0, "proposed_count": 0,
        "execution_authority": "none",
        "paid_models_authorized": False,
        "external_commercial_action_authorized": False,
        "public_publish_authorized": False,
        "database_write_authorized": False,
    }
    try:
        doc = _load_source(
            source_root / f"seo-audit-{current.date().isoformat()}.json",
            now=current,
        )
        base["source_finding_count"] = doc["finding_count"]
        known = _existing_reviews(root)
        rows = []
        for row in doc["findings"]:
            if not isinstance(row, Mapping):
                raise IntakeHeld("INVALID_FINDING")
            if row.get("code") not in CODES:
                continue
            if row.get("severity") not in PRIORITY:
                raise IntakeHeld("INVALID_SEVERITY")
            url = _owned(row.get("url"))
            rows.append((PRIORITY[row["severity"]], url, row["code"]))
        rows = sorted(set(rows))
        base["eligible_count"] = len(rows)
        base["already_under_review_count"] = sum(
            (url, code) in known for _, url, code in rows
        )
        if not rows:
            return {**base, "status": "NO_ELIGIBLE_FINDINGS"}
        job_paths = list_jobs(root, control_branch=control_branch)
        existing_auto = [
            p for p in job_paths
            if p.startswith("jobs/inbox/" + JOB_PREFIX) and p.endswith(".json")
        ]
        for path in existing_auto:
            job_name = path.removeprefix("jobs/inbox/").removesuffix(".json")
            if not control_exists(
                root, "jobs/results/" + job_name + ".json",
                control_branch=control_branch,
            ):
                return {**base, "status": "EXISTING_AUTO_RESEARCH_PENDING",
                        "existing_auto_job_count": len(existing_auto)}
        base["existing_auto_job_count"] = len(existing_auto)
        for _, url, code in rows:
            if (url, code) in known:
                continue
            job_id = _job_id(url, code)
            path = f"jobs/inbox/{job_id}.json"
            if (control_exists(root, path, control_branch=control_branch)
                    or control_exists(
                        root, f"jobs/results/{job_id}.json",
                        control_branch=control_branch,
                    )):
                continue
            digest = sha256(json.dumps(
                doc, sort_keys=True, separators=(",", ":"),
                ensure_ascii=True,
            ).encode()).hexdigest()
            manifest = _build_manifest(
                job_id=job_id, url=url, code=code,
                receipt_digest=digest,
                observed_at=doc["observed_at"], now=current,
            )
            if not publish:
                return {**base, "status": "NEW_RESEARCH_PROPOSED",
                        "proposed_count": 1, "job_id": job_id,
                        "finding_code": code, "page_url": url}
            result = enqueue(
                root, manifest, control_branch=control_branch,
                runtime_root=root / "runtime/hermes_control",
            )
            if result.get("published") is True:
                return {**base, "status": "RESEARCH_JOB_QUEUED",
                        "published_count": 1, "job_id": job_id,
                        "finding_code": code, "page_url": url}
            if result.get("reason") == "job_already_exists":
                return {**base, "status": "ALREADY_QUEUED",
                        "job_id": job_id}
            raise IntakeHeld("CONTROL_JOB_PUBLISH_UNVERIFIED")
        return {**base, "status": "ALL_FINDINGS_ALREADY_ASSIGNED_OR_UNDER_REVIEW"}
    except IntakeHeld as exc:
        return {**base, "status": "HELD", "reason_code": str(exc)}
    except (OSError, ValueError, TypeError) as exc:
        # Never convert provider or filesystem failures into inferred work.
        return {**base, "status": "HELD",
                "reason_code": type(exc).__name__}
