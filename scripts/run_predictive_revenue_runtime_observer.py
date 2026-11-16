#!/usr/bin/env python3
"""Predictive Revenue OBSERVE: distinguish registered forecasts from research.

Original observer (preserved in git history at 3d564d115) scanned every
runtime JSON file for keyword fragments, then treated buyer/marketing/research
nodes as forecasts. That was not a source-of-truth or an authenticated query.

The source classifier reads ONLY the original authenticated-source preflight.
An explicitly activated private branch invokes the original model with native
tenant-bound census inputs and a separate restricted writer. Default is still
OBSERVE. No runtime-file observation or public forecast request is admitted.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path("/srv/empire_os")
OUT_REL = "runtime/predictive_revenue_control/predictive_revenue_runtime_latest.json"
PREFLIGHT_REL = (
    "runtime/predictive_revenue_control/authenticated_source_preflight_latest.json"
)
PREFLIGHT_SCHEMA = "empire.predictive_revenue.authenticated_source_preflight.v1"
MAX_SOURCE_AGE_SECONDS = 1800
CONTROL_NAMES = (
    "canonical_identity", "conflict_detection", "duplicate_detection",
    "entity_classification", "input_quality", "output_quality", "quarantine",
)
GOVERNANCE = {
    "prediction_mutation": False,
    "db_write": False,
    "outbound": False,
    "action_authority_granted": False,
}


def _service_credential_metadata_safe(info, acl: bytes | None = None) -> bool:
    """Accept only systemd's protected owner/group or exact service-user ACL."""
    import stat
    import struct
    mode = stat.S_IMODE(info.st_mode)
    if not stat.S_ISREG(info.st_mode):
        return False
    if (
        (info.st_uid == os.geteuid() and mode == 0o400)
        or (info.st_uid == 0 and mode == 0o440 and info.st_gid == os.getegid())
    ):
        return True
    # systemd 259 may use root:root + user:<service-uid>:r--. The 0440
    # group mode is then the POSIX ACL mask; the root group has no access.
    if info.st_uid != 0 or info.st_gid != 0 or mode != 0o440 or not isinstance(acl, bytes):
        return False
    if len(acl) != 44 or struct.unpack_from("<I", acl)[0] != 2:
        return False
    entries = [struct.unpack_from("<HHI", acl, i) for i in range(4, 44, 8)]
    sentinel = 0xffffffff
    return set(entries) == {
        (1, 4, sentinel), (2, 4, os.geteuid()), (4, 0, sentinel),
        (16, 4, sentinel), (32, 0, sentinel),
    }


def _credential_fd_safe(fd: int) -> bool:
    try:
        acl = os.getxattr(fd, "system.posix_acl_access")
    except OSError:
        acl = None
    return _service_credential_metadata_safe(os.fstat(fd), acl)


def _service_reader_configuration(env: Mapping[str, str]) -> dict[str, str]:
    """Consume only systemd's read-only per-service credential mount.

    The original root vault is never chmodded, persisted into Environment or
    copied into the application tree. The service manager delivers it to the
    founder-approved existing department-cycle identity. No writer fallback.
    """
    import stat
    from psycopg.conninfo import make_conninfo
    from scripts.provision_revenue_event_evidence_login_20261018 import LOGIN, TENANT
    directory = Path(env.get("CREDENTIALS_DIRECTORY", ""))
    if (str(directory) != "/run/credentials/empire-department-cycle.service"
            or directory.resolve() != directory
            or not os.statvfs(directory).f_flag & os.ST_RDONLY):
        raise ValueError("systemd credential mount required")
    path = directory / "predictive-revenue-reader"
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not _credential_fd_safe(fd):
            raise ValueError("private service credential required")
        content = os.read(fd, 4097)
        if len(content) > 4096:
            raise ValueError("bounded original credential required")
    finally:
        os.close(fd)
    lines = content.decode("ascii").splitlines()
    prefix = f"/var/run/postgresql:5432:empiredb:{LOGIN}:"
    if len(lines) != 1 or not lines[0].startswith(prefix) or not lines[0][len(prefix):]:
        raise ValueError("original reader credential required")
    dsn = make_conninfo(host="/var/run/postgresql", port=5432, dbname="empiredb",
                       user=LOGIN, password=lines[0][len(prefix):], connect_timeout=5)
    configuration = {"EMPIRE_PREDICTIVE_TENANT_ID": TENANT,
                     "EMPIRE_PREDICTIVE_CENSUS_DSN": dsn,
                     "EMPIRE_PREDICTIVE_REGISTRY_READER_DSN": dsn}
    # Optional independently provisioned writer; never reuse the reader.
    if env.get("EMPIRE_PREDICTIVE_NATIVE_REGISTRATION_ENABLED") == "1":
        from empire_os.predictive_registry_transport import NATIVE_FORECAST_WRITER_LOGIN
        fd = os.open(directory / "predictive-revenue-writer",
                     os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            if not _credential_fd_safe(fd):
                raise ValueError("private writer credential required")
            content = os.read(fd, 4097)
            if len(content) > 4096:
                raise ValueError("bounded writer credential required")
        finally:
            os.close(fd)
        lines = content.decode("ascii").splitlines()
        prefix = f"127.0.0.1:5432:empiredb:{NATIVE_FORECAST_WRITER_LOGIN}:"
        if len(lines) != 1 or not lines[0].startswith(prefix) or not lines[0][len(prefix):]:
            raise ValueError("dedicated writer credential required")
        configuration["EMPIRE_PREDICTIVE_REGISTRAR_DSN"] = make_conninfo(
            host="127.0.0.1", port=5432, dbname="empiredb",
            user=NATIVE_FORECAST_WRITER_LOGIN, password=lines[0][len(prefix):],
            connect_timeout=5)
    return configuration


def _load_bounded_preflight(path: Path) -> dict[str, Any] | None:
    """Only local original preflight; refuse symlinks, oversize or malformed."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 32768:
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def _utc(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def evaluate_original_source(
    source: Mapping[str, Any] | None, *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """A verified transport status is NOT a verified forecast row.

    A positive aggregate source count cannot establish row identity, predicted
    amount, input provenance, or pre-outcome timestamp custody. Never
    synthesize a registered forecast, pass a candidate, or label verified.
    """
    now = now or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise ValueError("aware current time required")
    now = now.astimezone(timezone.utc)
    source = source if isinstance(source, Mapping) else {}
    observed = _utc(source.get("generated_at"))
    fresh = bool(
        observed is not None
        and 0 <= (now - observed).total_seconds() <= MAX_SOURCE_AGE_SECONDS
    )
    schema_ok = source.get("schema_version") == PREFLIGHT_SCHEMA
    source_mode_ok = source.get("mode") == "OBSERVE"
    registry_auth = (
        fresh and schema_ok and source_mode_ok
        and source.get("registry_reader_authenticated_session") is True
        and source.get("original_restricted_registry_reader_reused") is True
    )
    count = source.get("registry_scoped_rows_observed")
    count_valid = type(count) is int and 0 <= count <= 100000
    scoped_count = count if registry_auth and count_valid else None

    if not source:
        status = "ORIGINAL_REGISTRY_PREFLIGHT_MISSING"
    elif not schema_ok or not source_mode_ok:
        status = "ORIGINAL_REGISTRY_PREFLIGHT_CONTRACT_INVALID"
    elif not fresh:
        status = "ORIGINAL_REGISTRY_PREFLIGHT_STALE"
    elif not registry_auth or not count_valid:
        status = "ORIGINAL_REGISTRY_READER_UNAUTHENTICATED"
    elif count == 0:
        status = "AUTHENTICATED_REGISTRY_EMPTY_NO_FORECASTS"
    else:
        status = "REGISTERED_ROWS_REQUIRE_CASE_LEVEL_FORECAST_VALIDATION"

    # Previous 1247 matches were nested research fields, not 1247 actual
    # forecast records. A valid source must come through the original private
    # tenant-bound reader with row-by-row issuance and outcome custody.
    return {
        "schema_version": "empire-predictive-revenue-contextual-runtime-v3",
        "generated_at": now.isoformat(),
        "lane": "predictive_revenue",
        "mode": "OBSERVE",
        "status": status,
        "source_scope": "ORIGINAL_TENANT_BOUND_EMPIREDB_REGISTRY_ONLY",
        "classification_contract": "ORIGINAL_AUTHENTICATED_FORECAST_ROW_REQUIRED",
        "source_preflight_artifact": PREFLIGHT_REL,
        "source_preflight_fresh": fresh,
        "original_registry_reader_authenticated": bool(registry_auth),
        "original_registry_scoped_rows_reported": scoped_count,
        "registered_forecast_rows_independently_inspected": False,
        "research_runtime_json_scanned_as_forecast_candidates": False,
        "research_records_released_or_deleted": False,
        "candidate_count": 0,
        "identity_resolved_count": 0,
        "identity_unresolved_count": 0,
        "input_present_count": 0,
        "output_present_count": 0,
        "evidence_present_count": 0,
        "passed_count": 0,
        "quarantined_count": 0,
        "duplicate_identity_count": 0,
        "duplicate_identities": [],
        "conflict_count": 0,
        "conflicts": [],
        "runtime_verified_controls": [],
        "runtime_unverified_controls": list(CONTROL_NAMES),
        "real_forecast_qualifications_verified": False,
        "genuine_forecast_outcome_pairs_verified": False,
        "model_calibration_authorized": False,
        "commercial_authority": "none",
        "execution_authority": "none",
        "governance": dict(GOVERNANCE),
    }


def review_newsjack_research(root: Path, env: Mapping[str, str], *, now: datetime) -> dict[str, Any]:
    """Read original MediaOS references through the original JEV adapter.

    This is research context, never a native revenue-model observation or a
    commercial scope assertion. Runs on this observer's existing schedule.
    """
    result = {
        "status": "DISABLED", "source": "runtime/media_os/last30days/research_handoff_latest.json",
        "research_only": True, "revenue_model_input_authorized": False,
        "forecast_registered": False, "database_writes": False,
        "lookback_days": 30, "topics": [],
    }
    if env.get("EMPIRE_PREDICTIVE_NEWSJACK_RESEARCH_ENABLED") != "1":
        return result
    result["status"] = "SOURCE_OR_ADAPTER_UNAVAILABLE_HOLD"
    sector = env.get("EMPIRE_PREDICTIVE_NEWSJACK_RESEARCH_SECTOR", "")
    market = env.get("EMPIRE_PREDICTIVE_NEWSJACK_RESEARCH_MARKET", "")
    if sector not in ("ai", "roofing", "solar", "hvac", "dental") or market not in ("GB", "US"):
        result["status"] = "EXPLICIT_RESEARCH_SCOPE_REQUIRED"
        return result
    try:
        from hashlib import sha256
        from empire_os.jev_newsjack_adapters import signals_from_last30days_research_handoff
        from empire_os.jev_newsjack_traffic import review_newsjack_jev_traffic
        path = root / result["source"]
        if (path.resolve() != path.absolute() or not path.is_file()
                or not 0 < path.stat().st_size <= 250000):
            return result
        raw = path.read_bytes()
        if len(raw) > 250000:
            return result
        handoff = json.loads(raw)
        if not isinstance(handoff, dict) or not isinstance(handoff.get("topics"), list):
            return result
        # Only the existing approved feed topics; do not invent news queries.
        # Scope below is operator research selection, never proven geography.
        from empire_os.media_last30days_cycle import APPROVED_TOPICS
        topics = []
        for row in handoff["topics"]:
            if not isinstance(row, dict) or row.get("topic") not in APPROVED_TOPICS:
                raise ValueError("unapproved research topic")
            topic = row["topic"]
            expected_sector = "roofing" if topic == "AI lead generation for roofing contractors" else "ai"
            if sector != expected_sector:
                topics.append({"topic": topic, "status": "OUTSIDE_CONFIGURED_RESEARCH_SECTOR"})
                continue
            intake = signals_from_last30days_research_handoff(
                handoff, topic=topic, sector=sector, market=market, as_of=now.isoformat())
            review = review_newsjack_jev_traffic(
                intake["signals"], as_of=now.isoformat(),
                approved_sectors=[sector], approved_markets=[market])
            topics.append({
                "topic": topic, "status": "ORIGINAL_JEV_RESEARCH_REVIEWED",
                "mapped_count": intake["mapped_count"], "rejected_count": intake["rejected_count"],
                "duplicate_count": intake["duplicate_count"], "status_counts": review["status_counts"],
                "source_references": [s["evidence_refs"][0] for s in intake["signals"]],
            })
        result.update(status="ORIGINAL_LAST30DAYS_NEWSJACK_RESEARCH_REVIEWED",
                      source_generated_at=handoff["generated_at"], source_sha256=sha256(raw).hexdigest(),
                      research_sector=sector, research_market=market,
                      research_scope_verified=False, topics=topics)
    except Exception:
        # Never export source text, raw exception messages or provider data.
        result["status"] = "SOURCE_OR_ADAPTER_UNAVAILABLE_HOLD"
    return result


def run(*, root: Path = ROOT, now: datetime | None = None,
        write: bool = True,
        producer_environment: Mapping[str, str] | None = None) -> dict[str, Any]:
    output = root / OUT_REL
    source = _load_bounded_preflight(root / PREFLIGHT_REL)
    report = evaluate_original_source(source, now=now)
    # Existing department-cycle hook remains the sole scheduled entry point.
    # Activation is a separate owner/founder deployment decision. Never use
    # runtime JSON or public request points as observations/credentials.
    env = dict(producer_environment or {})
    if env.get("EMPIRE_PREDICTIVE_NATIVE_SOURCE_ENABLED") == "1":
        if not env.get("EMPIRE_PREDICTIVE_CENSUS_DSN") or not env.get("EMPIRE_PREDICTIVE_REGISTRY_READER_DSN"):
            try:
                for key, value in _service_reader_configuration(env).items():
                    env.setdefault(key, value)
                report["native_reader_credential_delivery"] = "SYSTEMD_SERVICE_SCOPED"
            except Exception:
                report["native_reader_credential_delivery"] = "SERVICE_SCOPED_CREDENTIAL_UNAVAILABLE"
        if (env.get("EMPIRE_PREDICTIVE_TENANT_ID")
                and env.get("EMPIRE_PREDICTIVE_CENSUS_DSN")
                and env.get("EMPIRE_PREDICTIVE_REGISTRY_READER_DSN")):
            from empire_os.predictive_revenue_source_preflight import review_authenticated_sources
            live_source = review_authenticated_sources(
                tenant_id=env["EMPIRE_PREDICTIVE_TENANT_ID"],
                registry_dsn=env["EMPIRE_PREDICTIVE_REGISTRY_READER_DSN"],
                census_dsn=env["EMPIRE_PREDICTIVE_CENSUS_DSN"],
                as_of=datetime.now(timezone.utc),
            )
            delivery = report.get("native_reader_credential_delivery")
            report = evaluate_original_source(live_source, now=datetime.now(timezone.utc))
            report["source_preflight_origin"] = "LIVE_ORIGINAL_RESTRICTED_READERS"
            if delivery:
                report["native_reader_credential_delivery"] = delivery
        from empire_os.predictive_materializer import produce_native_revenue_forecast
        native = produce_native_revenue_forecast(
            tenant_id=env.get("EMPIRE_PREDICTIVE_TENANT_ID", ""),
            census_dsn=env.get("EMPIRE_PREDICTIVE_CENSUS_DSN", ""),
            reader_dsn=env.get("EMPIRE_PREDICTIVE_REGISTRY_READER_DSN", ""),
            writer_dsn=env.get("EMPIRE_PREDICTIVE_REGISTRAR_DSN", "") if write else "",
            registration_enabled=(write and
                env.get("EMPIRE_PREDICTIVE_NATIVE_REGISTRATION_ENABLED") == "1"),
            history_days=30,
        )
        report["native_producer"] = native
        if (env.get("EMPIRE_PREDICTIVE_TENANT_ID")
                and env.get("EMPIRE_PREDICTIVE_REGISTRY_READER_DSN")
                and env.get("EMPIRE_PREDICTIVE_CENSUS_DSN")):
            from empire_os.predictive_revenue_daily_census import review_native_outcome_readiness
            report["native_outcome_readiness"] = review_native_outcome_readiness(
                tenant_id=env["EMPIRE_PREDICTIVE_TENANT_ID"],
                reader_dsn=env["EMPIRE_PREDICTIVE_REGISTRY_READER_DSN"],
                census_dsn=env["EMPIRE_PREDICTIVE_CENSUS_DSN"],
            )
        # OBSERVE describes the original source classifier, not the optional
        # private producer's authority. Do not conceal possible writes.
        report["governance"]["prediction_mutation"] = native["registration_attempted"]
        report["governance"]["db_write"] = native["registration_commit_state"] in (
            "UNKNOWN", "COMMITTED", "EXACT_RECORD_PRESENT")
    report["newsjack_research"] = review_newsjack_research(
        root, env, now=now or datetime.now(timezone.utc))
    if write:
        # Original output path only; no second scheduler or receipt registry.
        output.parent.mkdir(parents=True, exist_ok=True)
        tmp = output.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp.replace(output)
    return report


if __name__ == "__main__":
    result = run(producer_environment=os.environ)
    print(json.dumps({
        "status": result["status"],
        "candidate_count": result["candidate_count"],
        "quarantined_count": result["quarantined_count"],
        "original_registry_scoped_rows_reported":
            result["original_registry_scoped_rows_reported"],
        "research_runtime_json_scanned_as_forecast_candidates": False,
        "mode": result["mode"],
        "database_writes": result["governance"]["db_write"],
        "native_producer_status": result.get("native_producer", {}).get("status"),
    }, sort_keys=True))
