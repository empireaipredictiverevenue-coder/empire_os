"""Temporal research pilot owned by EmpireOS original Data Brokerage.

Read-only historical stage comparison + negative-control baseline.
NOT a production predictor, training pipeline, model release, tenant endpoint,
market purchase-intent score, storm event forecaster, or customer forecast.

Evidence uses official DESNZ Jan/Jul archived editions and the original
authenticated Cloud research snapshot of the Oct 2026 edition. Each historical
file is pinned to the observed original SHA and independently checked against
its declared publication cut-off. FEMA's latest 1000-row sample is descriptive
ONLY (latest-N selection makes unbiased temporal backtesting impossible).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import csv
import io
import json
import os
from pathlib import Path
import re
from statistics import median
from typing import Any

from empire_os.data_brokerage_enterprise_feed import (
    HEADERS, SOURCES, SCHEMA as SOURCE_SCHEMA, STATE as SOURCE_RECEIPT,
)
from empire_os.predictive_cloud_brokerage_research import (
    INDEX_PATH, SCHEMA as CLOUD_SCHEMA, _atomic_secure, _read_receipt,
    _read_source_bytes, _decode_csv,
)
from empire_os.predictive_cloud_brokerage_feature_adapter import (
    build_internal_brokerage_features,
)

SCHEMA = "empire.predictive_cloud.temporal_research_pilot.v1"
RELATIVE = Path("runtime/predictive_cloud/brokerage_research_private/forecast_pilot")
OUTPUT = RELATIVE / "research_pilot_latest.json"
HISTORICAL = (
    ("2026-02-09", "2026-02-09_REPD_Q4_2025_archived_official.csv",
     "fdb6aec50647a4de88f63d33679b93cb2147417eddc43f3f31cbf12792a38aae",
     13995, "2026-04-10", "REPD_Publication_Q4_2025.csv"),
    ("2026-05-06", "2026-05-06_REPD_Q1_2026_archived_official.csv",
     "3aa6752bfdc6b5275f8be0585ad8bd00a8646bd522d686cfb57d95cc9d8688a3",
     14316, "2026-06-04", "REPD_publication_Q1_2026.csv"),
    ("2026-08-03", "2026-08-03_REPD_Q2_2026_archived_official.csv",
     "84c1b5f958a934d8b4b86ec88f50bdcf43830ded7ff2efc27bffca0c98695035",
     14657, "2026-10-08", "REPD_Publication_Q2_2026.csv"),
)
LATEST_PUBLISHED = date(2026, 11, 13)
MIN_ROWS = 10_000
MAX_ROWS = 20_000
MAX_BYTES = 6_500_000
STAGE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
STATUS_MAX = 100


def _pubday(value: str) -> date:
    try:
        out = date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("INVALID_DECLARED_PUBLICATION_DATE") from exc
    return out


def _validate_status_rows(
    rows: list[dict[str, str]], *,
    published: date,
    id_key: str,
    stage_key: str,
    update_key: str,
    technology_key: str,
) -> tuple[dict[str, dict[str, str]], dict]:
    if not MIN_ROWS <= len(rows) <= MAX_ROWS:
        raise ValueError("OUT_OF_SCOPE_REPD_PUBLISHER_ROW_COUNT")
    seen = {}
    invalid_updates = 0
    future_updated = 0
    for r in rows:
        ident = (r.get(id_key) or "").strip()
        stage = (r.get(stage_key) or "").strip()
        tech = (r.get(technology_key) or "").strip()
        if (not STAGE_ID_PATTERN.fullmatch(ident) or ident in seen
                or not 0 < len(stage) <= STATUS_MAX
                or not 0 < len(tech) <= 120):
            raise ValueError("INVALID_DUPLICATED_OR_MISSING_PROJECT_STATE")
        stamp = (r.get(update_key) or "").strip()
        if stamp not in ("", "Not set"):
            try:
                date_of_change = datetime.strptime(stamp, "%d/%m/%Y").date()
                if date_of_change > published:
                    future_updated += 1
            except ValueError:
                invalid_updates += 1
        else:
            invalid_updates += 1
        seen[ident] = {"status": stage, "technology": tech}
    if future_updated:
        raise ValueError("FUTURE_UPDATED_PROJECT_IN_HISTORICAL_EDITION")
    return seen, {
        "project_records": len(seen),
        "unknown_or_invalid_last_update_dates": invalid_updates,
        "publisher_last_updated_is_not_transition_time": True,
    }


def _archive(root: Path, edition: tuple) -> tuple[dict, dict]:
    published_text, filename, pinned, expected_rows, captured, edition_filename = edition
    published = _pubday(published_text)
    if _pubday(captured) < published:
        raise ValueError("ARCHIVE_CAPTURE_BEFORE_REPORTED_PUBLICATION")
    file = root / RELATIVE / "source_archives" / filename
    if (file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_BYTES):
        raise ValueError("HISTORICAL_OFFICIAL_EDITION_UNAVAILABLE_OR_OVERSIZE")
    content = _read_source_bytes(file, pinned)
    if content.startswith(b"\xef\xbb\xbf"):
        content = content[3:]
    try:
        parser = csv.DictReader(io.StringIO(content.decode("cp1252"), newline=""))
        required = {
            "Ref ID", "Development Status", "Technology Type",
            "Record Last Updated (dd/mm/yyyy)",
        }
        if not required.issubset(set(parser.fieldnames or [])):
            raise ValueError("REPD_HISTORIC_PUBLISHER_SCHEMA_CHANGED")
        rows = list(parser)
    except UnicodeError as exc:
        raise ValueError("REPD_HISTORIC_PUBLISHER_ENCODING_ERROR") from exc
    if len(rows) != expected_rows:
        raise ValueError("HISTORICAL_EDITION_ROW_COUNT_CHANGED")
    state, quality = _validate_status_rows(
        rows, published=published, id_key="Ref ID",
        stage_key="Development Status",
        update_key="Record Last Updated (dd/mm/yyyy)",
        technology_key="Technology Type",
    )
    return state, {
        "published_at": published_text,
        "archived_original_filename": edition_filename,
        "archive_capture_date": captured,
        "historical_sha256": pinned,
        "source_rows": len(rows),
        "quality": quality,
        "historical_official_publisher_asset": True,
        "privacy_review_required_before_external_use": True,
    }


def _cloud_source(root: Path, dataset_id: str) -> tuple[list[dict],dict]:
    index = _read_receipt(root / INDEX_PATH, CLOUD_SCHEMA)
    if (index.get("status") != "VERIFIED_BROKERAGE_RESEARCH_INPUTS_INTERNAL"
            or index.get("source_redistribution_authorized") is not False
            or index.get("tenant_exposure_authorized") is not False
            or index.get("production_training_samples_admitted") != 0):
        raise ValueError("CLOUD_INDEX_OR_AUTHORITY_INVALID")
    matching = [x for x in index.get("dataset_records", [])
                if isinstance(x, dict) and x.get("dataset_id") == dataset_id]
    if len(matching) != 1:
        raise ValueError("CLOUD_SOURCE_NOT_UNIQUE")
    row = matching[0]
    if (row.get("kind") != "original_source"
            or row.get("source_id") != dataset_id
            or row.get("tenant_exposure_allowed") is not False
            or row.get("commercial_feature_admission") != "RESEARCH_ONLY"):
        raise ValueError("CLOUD_SOURCE_SCOPE_INVALID")
    source_receipts = _read_receipt(root / SOURCE_RECEIPT, SOURCE_SCHEMA)
    upstream = (source_receipts.get("datasets") or {}).get(dataset_id)
    if (source_receipts.get("source_redistribution_approved") is not False
            or not isinstance(upstream, dict)
            or upstream.get("quality_pass") is not True
            or upstream.get("source_status") not in ("VERIFIED_UNCHANGED", "VERIFIED_CHANGED")
            or upstream.get("source_snapshot_sha256") != row["sha256"]
            or upstream.get("customer_delivery_authorized") is not False):
        raise ValueError("UPSTREAM_SOURCE_OR_CLOUD_VERSION_NOT_VERIFIED")
    file = (root / INDEX_PATH.parent / "objects"
            / (dataset_id + "_" + row["sha256"] + ".csv"))
    raw = _read_source_bytes(file, row["sha256"])
    records = _decode_csv(raw, HEADERS[dataset_id], row["rows"])
    return records, row


def _window(previous: dict, subsequent: dict, a: date, b: date) -> dict:
    if a >= b or (b-a).days < 30:
        raise ValueError("INVALID_RESEARCH_HOLDOUT_WINDOW")
    old_ids = set(previous)
    new_ids = set(subsequent)
    shared = sorted(old_ids & new_ids)
    if not shared:
        raise ValueError("NO_LINKABLE_RELEASE_PROJECTS")
    pairs = Counter()
    by_status: dict[str, list[int]] = defaultdict(lambda:[0,0])
    by_technology: dict[str, list[int]] = defaultdict(lambda:[0,0])
    for key in shared:
        old = previous[key]
        new = subsequent[key]
        changed = int(old["status"] != new["status"])
        by_status[old["status"]][0] += 1
        by_status[old["status"]][1] += changed
        by_technology[old["technology"]][0] += 1
        by_technology[old["technology"]][1] += changed
        if changed:
            pairs[(old["status"],new["status"])] += 1
    changed_count=sum(pairs.values())
    initial = len(shared)
    def groups(values):
        return [
            {"group": k, "eligible_projects": v[0],
             "published_stage_changes": v[1],
             "observed_change_fraction": round(v[1]/v[0],6),
             "not_a_future_prediction_probability": True}
            for k,v in sorted(values.items())
            if v[0]>=30
        ]
    return {
        "previous_edition_published_at": a.isoformat(),
        "subsequent_edition_published_at": b.isoformat(),
        "days_between_publications": (b-a).days,
        "matched_projects": initial,
        "new_project_refs": len(new_ids-old_ids),
        "no_longer_in_publisher_edition": len(old_ids-new_ids),
        "published_stage_changes": changed_count,
        "unchanged": initial-changed_count,
        "observed_change_fraction": round(changed_count/initial,6),
        "persistence_rule_accuracy": round((initial-changed_count)/initial,6),
        "persistence_rule_changed_stage_recall": 0.0 if changed_count else None,
        "persistence_rule_balanced_accuracy": 0.5 if changed_count else None,
        "single_window_does_not_establish_future_accuracy": True,
        "top_status_changes": [
            {"from_published_stage":x[0], "to_published_stage":x[1], "count":n}
            for x,n in pairs.most_common(15)
        ],
        "stage_conditioned_descriptive_rates": groups(by_status),
        "technology_conditioned_descriptive_rates": groups(by_technology),
        "not_comparable_to_different_duration_windows_without_duration_adjustment": True,
        "labels_are_changes_in_published_stage_not_proof_of_real_work": True,
        "missing_next_release_records_are_unlabelled_not_negative_examples": True,
    }


def _storm_descriptive(rows: list[dict], published_at: date) -> dict:
    """FEMA latest-N *sample*, not an as-of historical sampling frame."""
    if not (500<=len(rows)<=2000):
        raise ValueError("FEMA_CURRENT_SAMPLE_COUNT_UNEXPECTED")
    declarations = {}
    invalid_date = 0
    for r in rows:
        key = (r["declaration_id"] or "").strip()
        if not key:
            invalid_date+=1
            continue
        try:
            begin = date.fromisoformat(r["incident_begin_date"][:10])
            declared = date.fromisoformat(r["declaration_date"][:10])
            if declared>published_at or begin>declared:
                invalid_date+=1
                continue
        except ValueError:
            invalid_date+=1
            continue
        delay=(declared-begin).days
        if not 0<=delay<=365:
            invalid_date+=1
            continue
        existing = declarations.get(key)
        if existing is not None and existing != delay:
            invalid_date+=1
            continue
        declarations[key]=delay
    values=sorted(declarations.values())
    if not values:
        raise ValueError("NO_VALID_PUBLISHED_FEMA_DECLARATIONS")
    return {
        "sample_rows":len(rows),
        "unique_declaration_ids_observed":len(values),
        "declaration_lag_days_median_observed":median(values),
        "declaration_lag_days_p90_observed":values[(len(values)*9-1)//10],
        "invalid_or_conflicting_sample_rows":invalid_date,
        "source_selection":"LATEST_1000_RECORDS_ONLY_NOT_COMPLETE_HISTORY",
        "predictive_backtest_admitted":False,
        "county_event_count_unbiased":False,
        "future_insurance_claims_inferred":False,
        "temporal_outcome_coverage_complete":False,
    }


def _label_rows(previous: dict, subsequent: dict,
                a: date, b: date) -> list[dict]:
    """Only published states; previous edition features and later edition label.

    No project name, address, operator, developer, phone, email, spend,
    claimant data or customer identity. Dropped IDs stay explicitly unlabelled.
    """
    if not a < b or (b-a).days < 30:
        raise ValueError("INVALID_PUBLISHER_STAGE_LABEL_WINDOW")
    result = []
    for ident in sorted(set(previous) & set(subsequent)):
        first=previous[ident]
        last=subsequent[ident]
        result.append({
            "source_project_key_sha256":
                sha256(("REPD:PROJECT:V1:"+ident).encode()).hexdigest(),
            "features_available_after_publisher_edition":a.isoformat(),
            "label_available_after_publisher_edition":b.isoformat(),
            "days_between_publications":(b-a).days,
            "development_stage_at_asof":first["status"],
            "technology_at_asof":first["technology"],
            "later_published_development_stage":last["status"],
            "published_stage_changed":first["status"] != last["status"],
            "label_is_publisher_change_not_business_outcome":True,
            "training_admission_allowed":False,
        })
    return result


def _private_label_object(root: Path, result: dict) -> dict:
    """Content-addressed 0600 private publisher label ledger, never model-fed."""
    snapshots=[]
    for edition in HISTORICAL:
        snapshots.append(_archive(root,edition)[0])
    current,source=_cloud_source(root,"uk_renewable_development_projects")
    current_state,quality=_validate_status_rows(
        current,published=LATEST_PUBLISHED,id_key="project_ref",
        stage_key="development_status", update_key="record_last_updated",
        technology_key="technology",
    )
    recorded=result["renewables"]["release_snapshots"]
    if (source["sha256"] != recorded[-1]["historical_sha256"]
            or len(current_state) != recorded[-1]["source_rows"]):
        raise ValueError("LABEL_LEDGER_CURRENT_SOURCE_DRIFT")
    dated = [(snapshots[i], _pubday(HISTORICAL[i][0]))
             for i in range(len(HISTORICAL))]
    dated.append((current_state, LATEST_PUBLISHED))
    frames = [
        _label_rows(dated[i][0], dated[i + 1][0],
                    dated[i][1], dated[i + 1][1])
        for i in range(len(dated) - 1)
    ]
    if [len(r) for r in frames] != [r["matched_projects"] for r in result["renewables"]["windows"]]:
        raise ValueError("LABEL_LEDGER_COHORT_RECONCILIATION_HOLD")
    payload=("".join(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n"
                     for frame in frames for row in frame)).encode("utf-8")
    if len(payload)>30_000_000:
        raise ValueError("BOUND_EXCEEDED_FOR_PRIVATE_PUBLISHER_LABELS")
    digest=sha256(payload).hexdigest()
    path=root/RELATIVE/"label_objects"/("repd_published_stage_"+digest+".jsonl")
    wrote=0
    if path.exists():
        if (path.is_symlink() or path.stat().st_mode & 0o077
                or sha256(path.read_bytes()).hexdigest()!=digest):
            raise ValueError("EXISTING_TEMPORAL_LABEL_OBJECT_NOT_TRUSTED")
    else:
        _atomic_secure(path,payload)
        wrote=1
    return {
        "private_object_rel":str(path.relative_to(root)),
        "object_sha256":digest,
        "label_rows":sum(len(x) for x in frames),
        "window_label_counts":[len(x) for x in frames],
        "new_private_label_objects_written":wrote,
        "feature_asof_and_label_availability_separate":True,
        "publisher_project_keys_only_hashed":True,
        "customer_labels_available":0,
        "training_admitted":False,
        "not_public_or_licensed_for_delivery":True,
    }


def research_pilot(root: str | Path, *,now: datetime|None=None) -> dict[str,Any]:
    repo=Path(root).resolve()
    if repo!=Path("/srv/empire_os"):
        return {"status":"NONCANONICAL_RESEARCH_PILOT_HELD",
                "production_model_training_authorized":False}
    stamp=now or datetime.now(timezone.utc)
    if stamp.utcoffset() is None or stamp.date() < LATEST_PUBLISHED:
        raise ValueError("FORECAST_PILOT_TIME_CUTOFF_INVALID")
    # Uses existing Fabric verification for ALL nine Cloud inputs.
    verified=build_internal_brokerage_features(repo,now=stamp)
    if (verified["dataset_count"]!=9
            or verified["production_model_input_admitted"] is not False):
        raise ValueError("ORIGINAL_CLOUD_FABRIC_INVENTORY_NOT_VERIFIED")
    snapshots=[]
    editions=[]
    for version in HISTORICAL:
        snapshots.append(_archive(repo,version))
        editions.append(_pubday(version[0]))
    current,cloud = _cloud_source(repo,"uk_renewable_development_projects")
    if cloud.get("publisher") != "DESNZ":
        raise ValueError("CURRENT_REPD_SOURCE_PUBLISHER_CHANGED")
    states, quality = _validate_status_rows(
        current,published=LATEST_PUBLISHED,
        id_key="project_ref",stage_key="development_status",
        update_key="record_last_updated",technology_key="technology",
    )
    timeline = [(snapshots[i][0], editions[i])
                for i in range(len(snapshots))]
    timeline.append((states, LATEST_PUBLISHED))
    windows = [_window(timeline[i][0], timeline[i + 1][0],
                       timeline[i][1], timeline[i + 1][1])
               for i in range(len(timeline) - 1)]
    from empire_os.predictive_cloud_temporal_science_eval import research_walkforward
    research_folds = [_label_rows(timeline[i][0], timeline[i + 1][0],
                                  timeline[i][1], timeline[i + 1][1])
                      for i in range(len(timeline) - 1)]
    if [len(fold) for fold in research_folds] != [w["matched_projects"] for w in windows]:
        raise ValueError("RESEARCH_SCIENCE_FOLD_SOURCE_RECONCILIATION_HOLD")
    research_backtest = research_walkforward(research_folds)
    fema, fema_source = _cloud_source(repo,"us_disaster_declaration_activity")
    storm=_storm_descriptive(fema,stamp.date())
    return {
        "schema":SCHEMA,"status":"RESEARCH_ONLY_POINT_IN_TIME_STAGE_CHANGE_PILOT",
        "source_of_truth":"ORIGINAL_DATA_BROKERAGE_AND_VERIFIED_PREDICTIVE_CLOUD_INPUTS",
        "observed_at":stamp.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "renewables":{
            "target":"NEXT_PUBLISHER_EDITION_REPD_PROJECT_STAGE_CHANGE",
            "target_definition":"Change of DESNZ published stage for a project Ref ID present in both editions.",
            "release_snapshots":[item[1] for item in snapshots]+[
                {"published_at":LATEST_PUBLISHED.isoformat(),
                 "source_rows":len(states),
                 "historical_sha256":cloud["sha256"],
                 "publisher":"DESNZ",
                 "archived_official_filename":"REPD_Publication_Q3_2026.csv",
                 "quality":quality}],
            "windows":windows,
            "research_only_chronological_backtest":research_backtest,
            "separate_observation_windows":len(windows),
            "equal_horizon_windows":len({x["days_between_publications"] for x in windows})==1,
            "out_of_time_2026_october_holdout_windows":1,
            "feature_as_of_alignment":"PUBLISHER_EDITION_DATES_ONLY",
            "minimum_comparable_training_windows_required":3,
            "additional_equal_horizon_train_windows_verified":0,
            "historical_roughly_quarterly_train_windows_verified":2,
            "out_of_time_research_holdout_windows_verified":1,
            "independent_customer_outcomes_verified":0,
            "model_trained":False,
            "calibrated_probability_available":False,
            "backtest_accuracy_approved_for_products":False,
            "next_quarter_forecast_produced":False,
            "commercial_demand_inference_authorized":False,
        },
        "storms":storm,
        "quality_gates":{
            "distinct_official_historical_editions":4,
            "jan_and_july_archive_hashes_pinned":True,
            "jan_april_july_archive_hashes_pinned":True,
            "future_updated_archived_records_rejected":True,
            "historic_edition_redirect_to_current_excluded":True,
            "publication_as_of_proven_from_release_metadata":True,
            "genuine_independent_future_buyer_or_claim_outcomes":0,
            "training_eligibility":"HOLD_INSUFFICIENT_INDEPENDENT_ROLLING_EVALUATIONS_FOR_PRODUCTION",
            "research_backtest_eligibility":"ALLOW_READ_ONLY_CHRONOLOGICAL_EVALUATION",
            "fema_forecasting_eligibility":"HOLD_LATEST_1000_SELECTION_BIAS",
            "production_forecast_or_model_admission":"DENIED",
            "tenant_scope":"INTERNAL_SYSTEM_RESEARCH_ONLY",
            "historical_revision_caveat":"Publisher release revisions can differ from actual real-world event times.",
        },
        "execution_authority":"none",
        "new_timer_created":False,
        "network_calls":0,
        "outbound_sent":False,
        "customer_data_processed":False,
        "customer_downloads_authorized":False,
        "tenant_exposure_authorized":False,
        "production_model_training_authorized":False,
        "new_predictions_produced":0,
        "verified_revenue":None,
    }


def refresh_research_pilot(root: str | Path, *,now:datetime|None=None) -> dict:
    result=research_pilot(root,now=now)
    if result["status"]=="NONCANONICAL_RESEARCH_PILOT_HELD":
        return result
    root=Path(root).resolve()
    labels=_private_label_object(root,result)
    result["private_temporal_label_ledger"]={
        k:v for k,v in labels.items()
        if k!="new_private_label_objects_written"
    }
    file=root/OUTPUT
    content=json.dumps(result,sort_keys=True,indent=2)+"\n"
    # Idempotence excludes the generated time, which is not a source update.
    if file.exists() and not file.is_symlink():
        prior=_read_receipt(file,SCHEMA)
        if (prior.get("renewables")==result["renewables"]
                and prior.get("storms")==result["storms"]
                and prior.get("quality_gates")==result["quality_gates"]
                and prior.get("private_temporal_label_ledger")
                    == result["private_temporal_label_ledger"]
                and prior.get("production_model_training_authorized") is False):
            return {"status":"VERIFIED_UNCHANGED_TEMPORAL_RESEARCH_PILOT",
                    "retrospective_windows":len(result["renewables"]["windows"]),
                    "forecast_predictions_produced":0,
                    "private_label_rows":labels["label_rows"],
                    "private_label_objects_written":labels["new_private_label_objects_written"],
                    "dataset_writes":0,"production_model_training_authorized":False}
    _atomic_secure(file,content.encode())
    return {"status":result["status"],
            "retrospective_windows":len(result["renewables"]["windows"]),
            "forecast_predictions_produced":0,"dataset_writes":1,
            "private_label_rows":labels["label_rows"],
            "private_label_objects_written":labels["new_private_label_objects_written"],
            "production_model_training_authorized":False}
