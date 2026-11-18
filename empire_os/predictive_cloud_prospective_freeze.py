"""Single-owner prospective research freeze (NOT production model predictions).

Freezes the next DESNZ publisher-stage research cohort after Q3 2026.
Existing Data Brokerage owner performs an atomic create-once under its lock.
Every later read verifies the exact frozen bytes and pinning receipt.
No schedules, tenant UI, model deployment, training, outbound or finance.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import os
import stat

from empire_os.predictive_cloud_temporal_research_pilot import (
    LATEST_PUBLISHED, OUTPUT, RELATIVE, _cloud_source,
    _validate_status_rows, research_pilot,
)
from empire_os.predictive_cloud_temporal_science_eval import _fit, _require_asof_separation

SCHEMA = "empire.predictive_cloud.prospective_publisher_stage_freeze.v1"
CUTOFF = LATEST_PUBLISHED.isoformat()
FREEZE_DIR = RELATIVE / "prospective_freezes"
RECEIPT = FREEZE_DIR / ("repd_" + CUTOFF + "_freeze.json")
RESEARCH_CONTEXT = "EMPIRE_INTERNAL_RESEARCH_OBSERVE"
EXPECTED_ROWS = 14_967
EXPECTED_SOURCE_SHA = "ec3b08d7986faff59b2a29adca75521583094198faa4f72244d16e09e936f440"
ESTIMATOR_NAME = "EXPLORATORY_HIERARCHICAL_STAGE_TECH_SMOOTHING_50_100"
TOP_N = 500
MAX_LABEL_BYTES = 30_000_000
MAX_SCORE_BYTES = 12_000_000  # observed 14,967-row complete cohort ~8.35 MB
MAX_MODEL_BYTES = 50_000  # actual research-only stage/technology parameters ~26.3 KB


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _verified_private_file(path: Path, expected: str, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("FROZEN_RESEARCH_FILE_MISSING_OR_LINKED")
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o077 or st.st_size > limit:
        raise ValueError("FROZEN_RESEARCH_FILE_MODE_OR_SIZE_HOLD")
    raw = path.read_bytes()
    after = path.stat()
    if (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
            after.st_ctime_ns):
        raise ValueError("FROZEN_RESEARCH_FILE_CHANGED_DURING_READ")
    if _sha(raw) != expected:
        raise ValueError("FROZEN_RESEARCH_SHA_MISMATCH")
    return raw


def _immutable_create(path: Path, raw: bytes) -> bool:
    """Create-once. Never replace a committed model, freeze or audit receipt."""
    parent = path.parent
    if parent.is_symlink():
        raise ValueError("UNTRUSTED_FREEZE_DIRECTORY_LINK")
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if parent.stat().st_mode & 0o077:
        raise ValueError("UNTRUSTED_FREEZE_DIRECTORY_PERMISSIONS")
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
            raise ValueError("FROZEN_RESEARCH_EXISTING_OBJECT_UNTRUSTED")
        return False
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # Only our own incomplete creation can be removed.
        if path.exists():
            path.unlink()
        raise
    return True


def _validate_training(
    training: list[dict], asof: str,
) -> tuple[float, dict[str,float], dict[tuple[str,str],float]]:
    if len(training) != 42_940:
        raise ValueError("TRAINING_LEDGER_SIZE_NOT_PINNED")
    date_endings = set()
    for row in training:
        if (row.get("label_is_publisher_change_not_business_outcome") is not True
                or row.get("training_admission_allowed") is not False
                or row.get("label_available_after_publisher_edition", "") > asof
                or row.get("features_available_after_publisher_edition", "")
                    >= row.get("label_available_after_publisher_edition", "")):
            raise ValueError("RESEARCH_TRAINING_ASOF_OR_AUTHORITY_HOLD")
        date_endings.add(row["label_available_after_publisher_edition"])
    if date_endings != {"2026-05-06", "2026-08-03", "2026-11-13"}:
        raise ValueError("RESEARCH_TRAINING_EDITION_INVENTORY_HOLD")
    return _fit(training)


def _build_scores(
    states: dict[str,dict[str,str]],
    training: list[dict],
    asof: str,
) -> tuple[bytes, dict]:
    if asof != CUTOFF or len(states) != EXPECTED_ROWS:
        raise ValueError("PROSPECTIVE_PUBLISHER_ASOF_OR_COHORT_MISMATCH")
    base, stage_rates, mix_rates = _validate_training(training, asof)
    ranked = []
    for ref, obj in states.items():
        stage = obj["status"]
        technology = obj["technology"]
        estimate = mix_rates.get(
            (stage, technology), stage_rates.get(stage, base))
        if not 0 < estimate < 1:
            raise ValueError("INVALID_PROSPECTIVE_RESEARCH_SCORE")
        ranked.append({
            "public_project_key_sha256":
                _sha(("REPD:PROJECT:V1:" + ref).encode()),
            "asof_publisher_date":asof,
            "published_development_stage_at_asof":stage,
            "published_technology_at_asof":technology,
            "stage_change_research_score":round(estimate, 12),
            "target":"NEXT_PUBLISHED_REPD_DEVELOPMENT_STAGE_CHANGE",
            "score_is_calibrated_forecast":False,
            "score_is_customer_purchase_probability":False,
            "customer_revenue_predicted":False,
            "production_model_training_authorized":False,
            "next_official_publisher_outcome_unobserved":True,
        })
    ranked.sort(key=lambda r:(-r["stage_change_research_score"],
                               r["public_project_key_sha256"]))
    if len({r["public_project_key_sha256"] for r in ranked})!=len(ranked):
        raise ValueError("RESEARCH_FROZEN_PROJECT_KEY_COLLISION")
    raw=("".join(json.dumps(r,sort_keys=True,separators=(",",":"))+"\n"
                 for r in ranked)).encode()
    if len(raw)>MAX_SCORE_BYTES:
        raise ValueError("BOUNDED_PROSPECTIVE_SCORE_FILE_EXCEEDED")
    model = {
        "estimator":ESTIMATOR_NAME,
        "training_rows":len(training),
        "training_event_count":sum(r["published_stage_changed"] is True
                                    for r in training),
        "global_smoothed_rate":base,
        "stage_smoothed_rates":sorted(
            [{"stage":k,"rate":v} for k,v in stage_rates.items()],
            key=lambda x:x["stage"]),
        "stage_and_technology_smoothed_rates":sorted(
            [{"stage":key[0],"technology":key[1],"rate":v}
             for key,v in mix_rates.items()],
            key=lambda x:(x["stage"],x["technology"])),
        "no_future_outcome_data":True,
        "no_customer_prediction_model":True,
        "model_authority":"RESEARCH_OBSERVE_ONLY",
    }
    return raw, {
        "score_rows":len(ranked),
        "scored_top_n_predeclared":TOP_N,
        "top_n_public_hashed_project_keys_sha256":
            _sha(("\n".join(r["public_project_key_sha256"]
                            for r in ranked[:TOP_N])+"\n").encode()),
        "model_specification_sha256":_sha(
            json.dumps(model,sort_keys=True,separators=(",",":")).encode()),
        "model_research_parameters":model,
        "score_min":min(r["stage_change_research_score"] for r in ranked),
        "score_max":max(r["stage_change_research_score"] for r in ranked),
    }


def verify_frozen_cohort(root: str | Path) -> dict:
    """Verify committed original freeze only; never recompute it or shift as-of."""
    root = Path(root).resolve()
    receipt_path = root / RECEIPT
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ValueError("NO_COMMITTED_PROSPECTIVE_RESEARCH_FREEZE")
    if receipt_path.stat().st_mode & 0o077 or receipt_path.stat().st_size>25_000:
        raise ValueError("FROZEN_RECEIPT_FILE_ACCESS_HOLD")
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get("schema") != SCHEMA
            or receipt.get("status") != "FROZEN_PROSPECTIVE_RESEARCH_COHORT"
            or receipt.get("publisher_asof_date") != CUTOFF
            or receipt.get("original_source_sha256") != EXPECTED_SOURCE_SHA
            or receipt.get("scored_research_projects") != EXPECTED_ROWS
            or receipt.get("top_n_predeclared") != TOP_N
            or receipt.get("training_production_authorized") is not False
            or receipt.get("customer_delivery_authorized") is not False
            or receipt.get("future_publisher_outcomes_observed") is not False):
        raise ValueError("FROZEN_RECEIPT_STATUS_OR_AUTHORITY_INVALID")
    freeze_dir=root/FREEZE_DIR
    if freeze_dir.is_symlink() or freeze_dir.stat().st_mode & 0o077:
        raise ValueError("FROZEN_RESEARCH_DIRECTORY_TRUST_HOLD")
    if (receipt.get("score_object_filename") !=
            "repd_" + CUTOFF + "_scores_" + receipt.get("score_object_sha256", "") + ".jsonl"
            or receipt.get("model_object_filename") !=
            "repd_" + CUTOFF + "_model_" + receipt.get("model_object_sha256", "") + ".json"):
        raise ValueError("FROZEN_RESEARCH_OBJECT_PATH_PIN_MISMATCH")
    raw = _verified_private_file(
        freeze_dir / receipt["score_object_filename"],
        receipt["score_object_sha256"], MAX_SCORE_BYTES)
    scored = [json.loads(x) for x in raw.splitlines()]
    if len(scored)!=EXPECTED_ROWS:
        raise ValueError("FROZEN_SCORE_OBJECT_COUNT_MISMATCH")
    if (len({r.get("public_project_key_sha256") for r in scored}) != EXPECTED_ROWS
            or any(r.get("asof_publisher_date")!=CUTOFF
                   or r.get("next_official_publisher_outcome_unobserved") is not True
                   or r.get("production_model_training_authorized") is not False
                   or type(r.get("stage_change_research_score")) is not float
                   or not 0 < r["stage_change_research_score"] < 1
                   for r in scored)
            or scored != sorted(scored,key=lambda r:(-r["stage_change_research_score"],
                                                      r["public_project_key_sha256"]))):
        raise ValueError("FROZEN_SCORE_OBJECT_RESEARCH_AUTHORITY_OR_ORDER_HOLD")
    top_hash = _sha(("\n".join(x["public_project_key_sha256"]
                            for x in scored[:TOP_N])+"\n").encode())
    if top_hash != receipt.get("top_n_project_hashes_sha256"):
        raise ValueError("FROZEN_TOP_N_ORDER_NOT_PINNED")
    model_path=freeze_dir/receipt["model_object_filename"]
    model_raw=_verified_private_file(model_path,receipt["model_object_sha256"],MAX_MODEL_BYTES)
    model=json.loads(model_raw)
    if (model.get("model_authority")!="RESEARCH_OBSERVE_ONLY"
            or model.get("training_rows")!=42940
            or model.get("training_event_count")!=1266
            or _sha(json.dumps(model,sort_keys=True,separators=(",", ":")).encode())
                != receipt.get("model_specification_sha256")):
        raise ValueError("FROZEN_RESEARCH_MODEL_AUTHORITY_OR_LEDGER_HOLD")
    return {
        "status":"VERIFIED_IMMUTABLE_PROSPECTIVE_RESEARCH_FREEZE",
        "publisher_asof_date":receipt["publisher_asof_date"],
        "frozen_at":receipt["frozen_at"],
        "research_scored_projects":receipt["scored_research_projects"],
        "top_n_predeclared":TOP_N,
        "score_object_sha256":receipt["score_object_sha256"],
        "model_object_sha256":receipt["model_object_sha256"],
        "new_objects_written":0,
        "production_forecasts_produced":0,
        "customer_delivery_authorized":False,
        "model_training_authorized":False,
    }


def freeze_once(root: str | Path, *,
                now: datetime | None = None) -> dict:
    """Freeze once from verified current research; afterwards verify-only."""
    root=Path(root).resolve()
    if root != Path("/srv/empire_os"):
        return {"status":"NONCANONICAL_PROSPECTIVE_FREEZE_HELD",
                "new_objects_written":0,
                "model_training_authorized":False}
    receipt=root/RECEIPT
    if receipt.exists() or receipt.is_symlink():
        return verify_frozen_cohort(root)
    current = now or datetime.now(timezone.utc)
    if not isinstance(current,datetime) or current.utcoffset() is None:
        raise ValueError("FREEZE_ACTUAL_TIME_TZ_REQUIRED")
    current=current.astimezone(timezone.utc)
    if current.date() <= LATEST_PUBLISHED:
        raise ValueError("FREEZE_ACTUAL_TIME_MUST_FOLLOW_PUBLISHER_ASOF")
    report_path=root/OUTPUT
    if report_path.is_symlink() or not report_path.is_file():
        raise ValueError("ORIGINAL_TEMPORAL_OWNER_REPORT_UNAVAILABLE")
    pilot=json.loads(report_path.read_text())
    verified=research_pilot(root,now=current)
    if (pilot.get("renewables")!=verified.get("renewables")
            or pilot.get("quality_gates")!=verified.get("quality_gates")
            or pilot.get("production_model_training_authorized") is not False
            or len(pilot.get("renewables",{}).get("release_snapshots",[]))!=4):
        raise ValueError("TEMPORAL_PILOT_REPORT_VERSION_OR_AUTHORITY_HOLD")
    ledger=pilot.get("private_temporal_label_ledger") or {}
    original_ledger=root/ledger["private_object_rel"]
    training_raw=_verified_private_file(
        original_ledger,ledger["object_sha256"],MAX_LABEL_BYTES)
    training=[json.loads(line) for line in training_raw.splitlines()]
    rows,source=_cloud_source(root,"uk_renewable_development_projects")
    if (source.get("sha256") != EXPECTED_SOURCE_SHA
            or pilot["renewables"]["release_snapshots"][-1]["historical_sha256"]
                != EXPECTED_SOURCE_SHA):
        raise ValueError("NEXT_PUBLISHER_ASOF_OR_SOURCE_DRIFT_HOLD")
    states,quality=_validate_status_rows(
        rows,published=LATEST_PUBLISHED,id_key="project_ref",
        stage_key="development_status",update_key="record_last_updated",
        technology_key="technology")
    score_bytes,details=_build_scores(states,training,CUTOFF)
    model_bytes=(json.dumps(details["model_research_parameters"],
                            sort_keys=True,indent=2)+"\n").encode()
    score_digest=_sha(score_bytes)
    model_digest=_sha(model_bytes)
    score_name="repd_"+CUTOFF+"_scores_"+score_digest+".jsonl"
    model_name="repd_"+CUTOFF+"_model_"+model_digest+".json"
    freeze_dir=root/FREEZE_DIR
    objects_created=0
    for filename,raw,digest,limit in (
        (score_name,score_bytes,score_digest,MAX_SCORE_BYTES),
        (model_name,model_bytes,model_digest,MAX_MODEL_BYTES),
    ):
        object_path=freeze_dir/filename
        objects_created+=int(_immutable_create(object_path,raw))
        _verified_private_file(object_path,digest,limit)
    manifest={
        "schema":SCHEMA,"status":"FROZEN_PROSPECTIVE_RESEARCH_COHORT",
        "frozen_at":current.isoformat(timespec="seconds"),
        "publisher_asof_date":CUTOFF,
        "not_retroactively_frozen_at_publisher_date":True,
        "future_outcome":"NEXT_OFFICIAL_DESNZ_REPD_EDITION_AFTER_2026_11_13",
        "future_publisher_outcomes_observed":False,
        "original_data_brokerage_owner":"run_data_brokerage_source_mining",
        "original_source_sha256":EXPECTED_SOURCE_SHA,
        "original_source_rows":len(states),
        "original_private_label_ledger_sha256":ledger["object_sha256"],
        "original_label_count":len(training),
        "historical_stage_change_labels":details["model_research_parameters"]["training_event_count"],
        "scored_research_projects":details["score_rows"],
        "top_n_predeclared":TOP_N,
        "top_n_project_hashes_sha256":details["top_n_public_hashed_project_keys_sha256"],
        "model_specification_sha256":details["model_specification_sha256"],
        "score_object_filename":score_name,
        "score_object_sha256":score_digest,
        "model_object_filename":model_name,
        "model_object_sha256":model_digest,
        "score_min":details["score_min"],
        "score_max":details["score_max"],
        "training_production_authorized":False,
        "customer_delivery_authorized":False,
        "tenant_exposure_authorized":False,
        "revenue_forecasting_authorized":False,
        "production_forecasts_produced":0,
        "prospective_outcome_comparison_eligible_when_new_publisher_edition_verified":True,
        "historical_model_selection_was_not_blind_or_preregistered":True,
        "publisher_stage_change_only_not_customer_demand":True,
        "no_new_timer":True,
        "no_external_network_or_gpu":True,
        "status_change_requires_explicit_independent_evidence":True,
    }
    # Commit marker created LAST, only after both objects verify.
    if not _immutable_create(
            receipt,(json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode()):
        # Concurrent original-owner creation would be verified, not overwritten.
        return verify_frozen_cohort(root)
    status=verify_frozen_cohort(root)
    status["new_objects_written"]=objects_created+1
    return status
