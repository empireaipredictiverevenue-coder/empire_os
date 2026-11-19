"""Research-only prospective evaluation of the November 2026 DESNZ freeze.

Owned by the original Data Brokerage service/timer. Does not fetch or publish.
Only the original verified official Q4 2026 publisher CSV + current private
Cloud/source provenance may unlock comparison with the unmodified frozen
November ranking. No customer demand, production inference or training.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from math import log
from pathlib import Path
from urllib.parse import urlparse
import json
import re

from empire_os.data_brokerage_enterprise_feed import STATE, SCHEMA as SOURCE_SCHEMA
from empire_os.predictive_cloud_brokerage_research import (
    read_internal_brokerage_rows, _read_receipt,
)
from empire_os.predictive_cloud_temporal_research_pilot import (
    _cloud_source, _validate_status_rows,
)
from empire_os.predictive_cloud_prospective_freeze import (
    CUTOFF, FREEZE_DIR, RECEIPT, TOP_N, MAX_SCORE_BYTES, MAX_MODEL_BYTES,
    _verified_private_file, _immutable_create, verify_frozen_cohort,
)
from empire_os.predictive_cloud_temporal_science_eval import _auc_tie_aware

SCHEMA = "empire.predictive_cloud.prospective_publisher_stage_evaluation.v1"
EVIDENCE = FREEZE_DIR / "repd_2026-11-13_q4_2026_evaluation.json"
DATASET = "uk_renewable_development_projects"
NEXT_RELEASE = "REPD_Publication_Q4_2026.csv"
RELEASE_PATTERN = re.compile(r"(?i)^/media/[a-z0-9]+/REPD_publication_Q4_2026[.]csv$")
MIN_COHORT_COVERAGE = 0.97
MIN_TOP500_COVERAGE = 0.98
MIN_PUBLISHER_ROWS, MAX_PUBLISHER_ROWS = 10000, 20000
MAX_RELEASE_BYTES = 12_000_000


def _publisher_url_verified(url: str) -> bool:
    if not isinstance(url, str):
        return False
    parts = urlparse(url)
    return (parts.scheme == "https"
            and parts.netloc == "assets.publishing.service.gov.uk"
            and not parts.query and not parts.fragment
            and RELEASE_PATTERN.fullmatch(parts.path) is not None)


def _release_gate(source: dict, frozen: dict, now: datetime) -> str:
    """Never accept a source simply because its bytes changed."""
    if (frozen.get("frozen_at") != "2026-11-18T18:59:43+00:00"
            or frozen.get("future_publisher_outcomes_observed") is not False):
        raise ValueError("ORIGINAL_FROZEN_COHORT_IDENTITY_INVALID")
    if (source.get("publisher") != "DESNZ"
            or source.get("quality_pass") is not True
            or source.get("customer_delivery_authorized") is not False
            or source.get("source_status") not in ("VERIFIED_UNCHANGED", "VERIFIED_CHANGED")):
        raise ValueError("NEW_PUBLISHER_SOURCE_QUALITY_OR_AUTHORITY_HOLD")
    orig = frozen["original_source_sha256"]
    new = source.get("source_snapshot_sha256")
    if not isinstance(new, str) or not re.fullmatch(r"[0-9a-f]{64}", new):
        raise ValueError("NEW_PUBLISHER_SNAPSHOT_DIGEST_MISSING")
    current_url = urlparse(source.get("source_url") or "")
    is_q3_url = (
        current_url.scheme == "https"
        and current_url.netloc == "assets.publishing.service.gov.uk"
        and re.fullmatch(
            r"(?i)/media/[a-z0-9]+/REPD_publication_Q3_2026[.]csv",
            current_url.path,
        ) is not None
        and not current_url.query and not current_url.fragment
    )
    if new == orig:
        if not is_q3_url:
            raise ValueError("SOURCE_BYTES_MATCH_FROZEN_BUT_PUBLISHER_EDITION_DIFFERS")
        return "AWAITING_NEW_OFFICIAL_REPD_RELEASE"
    if is_q3_url:
        # Correct CP1252 parsing fixes text corruption but is NOT a new quarter.
        meta = source.get("publisher_publication_metadata") or {}
        if (meta.get("publisher_original_raw_sha256")
                == "48e76c49f33a1090e78108d1ea9bfe689b35963ea3be1bb4f6516d038a5ff862"
                and meta.get("raw_publisher_encoding") == "cp1252"
                and meta.get("publisher_original_source_url")
                    == source.get("source_url")):
            return "AWAITING_NEW_OFFICIAL_REPD_RELEASE"
        raise ValueError("REVISED_Q3_PUBLISHER_SOURCE_NOT_A_FUTURE_EDITION")
    if not _publisher_url_verified(source.get("source_url", "")):
        raise ValueError("NEW_PUBLISHER_EDITION_URL_NOT_Q4_2026_HOLD")
    try:
        checked = datetime.fromisoformat(source["last_checked_at"])
        succeeded = datetime.fromisoformat(source["last_success_at"])
        frozen_at = datetime.fromisoformat(frozen["frozen_at"])
        if any(t.utcoffset() is None for t in (checked,succeeded,frozen_at)):
            raise ValueError("TIMELINE_MUST_BE_TIMEZONE_AWARE")
        checked=checked.astimezone(timezone.utc)
        succeeded=succeeded.astimezone(timezone.utc)
        frozen_at=frozen_at.astimezone(timezone.utc)
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("SOURCE_PUBLICATION_TIMELINE_UNVERIFIED") from exc
    if (checked.utcoffset() is None or succeeded.utcoffset() is None
            or checked < frozen_at or succeeded < frozen_at
            or checked < datetime(2027,1,1,tzinfo=timezone.utc)
            or succeeded < datetime(2027,1,1,tzinfo=timezone.utc)
            or checked < succeeded
            or succeeded > now or checked > now
            or source.get("sample_not_full_population") is not False
            or type(source.get("row_count")) is not int
            or not MIN_PUBLISHER_ROWS <= source["row_count"] <= MAX_PUBLISHER_ROWS):
        raise ValueError("NEXT_PUBLISHER_RELEASE_CHRONOLOGY_OR_COVERAGE_HOLD")
    return "OFFICIAL_NEW_Q4_EDITION_VERIFIED_BY_ORIGINAL_SOURCE"


def _verify_official_q4_raw_source(repo: Path, source: dict,
                                    rows: list[dict]) -> dict:
    """Raw official-byte SHA + full parser/canonical-CVS-to-Cloud reconciliation."""
    from empire_os.data_brokerage_enterprise_feed import (
        _parse_repd_raw, _csv_bytes,
    )
    meta=source.get("publisher_publication_metadata") or {}
    rawsha=meta.get("publisher_original_raw_sha256")
    official_name=urlparse(source.get("source_url") or "").path.rsplit("/",1)[-1]
    if (not _publisher_url_verified(source.get("source_url"))
            or not re.fullmatch(
                r"(?i)REPD_publication_Q4_2026[.]csv",official_name
            )):
        raise ValueError("Q4_RAW_PUBLISHER_ASSET_URL_NOT_VERIFIED")
    expected_path=(
        "runtime/predictive_cloud/brokerage_research_private/"
        "forecast_pilot/source_archives/"
        "source_"+official_name.removesuffix(".csv")
        +"_"+str(rawsha)+".csv"
    )
    if (not isinstance(rawsha,str)
            or not re.fullmatch(r"[0-9a-f]{64}",rawsha)
            or meta.get("publisher_original_raw_archive_relative")!=expected_path
            or meta.get("publisher_original_source_url")!=source["source_url"]
            or meta.get("publisher_raw_redistribution_authorized") is not False
            or meta.get("publisher_source_content_addressed") is not True
            or meta.get("raw_publisher_encoding") not in ("cp1252", "utf-8-sig")
            or type(meta.get("publisher_original_raw_bytes")) is not int
            or not 1<=meta["publisher_original_raw_bytes"]<=9_000_000):
        raise ValueError("Q4_OFFICIAL_RAW_PUBLISHER_ARCHIVE_METADATA_HOLD")
    path=repo/expected_path
    if path.parent.is_symlink() or path.parent.stat().st_mode & 0o077:
        raise ValueError("Q4_OFFICIAL_RAW_PUBLISHER_ARCHIVE_DIRECTORY_HOLD")
    raw=_verified_private_file(path,rawsha,9_000_000)
    if len(raw)!=meta["publisher_original_raw_bytes"]:
        raise ValueError("Q4_OFFICIAL_RAW_PUBLISHER_SIZE_DRIFT")
    if (not rows or len({x["observed_at"] for x in rows})!=1):
        raise ValueError("Q4_CLOUD_SOURCE_MIXED_OBSERVATION_TIMESTAMPS")
    rebuilt,raw_quality=_parse_repd_raw(raw,rows[0]["observed_at"])
    if (raw_quality["raw_publisher_row_count"]!=meta.get("raw_publisher_row_count")
            or raw_quality["exact_duplicate_public_ref_rows"]
                !=meta.get("exact_duplicate_public_ref_rows")
            or raw_quality["raw_publisher_encoding"]!=meta["raw_publisher_encoding"]
            or rebuilt!=rows):
        raise ValueError("Q4_RAW_PUBLISHER_ROWS_AND_CLOUD_SOURCE_DIVERGE")
    digest=sha256(_csv_bytes(DATASET,rebuilt)).hexdigest()
    if digest!=source["source_snapshot_sha256"]:
        raise ValueError("Q4_RECONSTRUCTED_NORMALISED_SOURCE_SHA_DRIFT")
    return {
        "original_official_publisher_csv_sha256":rawsha,
        "original_official_publisher_csv_bytes":len(raw),
        "original_official_publisher_rows":raw_quality["raw_publisher_row_count"],
        "original_publisher_exact_duplicate_ids":
            raw_quality["exact_duplicate_public_ref_rows"],
        "official_byte_to_normalized_cloud_fields_reconciled":True,
        "raw_source_redistribution_authorized":False,
    }


def _average_precision_with_ties(scored: list[tuple[float, bool, str]]) -> float | None:
    """Deterministic threshold-group AP: tied projects share one threshold."""
    pos = sum(int(y) for _, y, _ in scored)
    if not pos:
        return None
    ordered = sorted(scored,key=lambda t:-t[0])
    got,seen,area,i=0,0,0.,0
    while i < len(ordered):
        j=i+1
        while j<len(ordered) and ordered[j][0]==ordered[i][0]:
            j+=1
        ntrue=sum(int(x[1]) for x in ordered[i:j])
        got+=ntrue
        seen+=j-i
        area+=(ntrue/pos)*(got/seen)
        i=j
    return round(area,6)


def compare_fixed_cohort(frozen_scores: list[dict],
                         later: dict[str,str],
                         *, expected_total: int | None = None,
                         training_only_constant_rate: float | None = None) -> dict:
    """Pure independent evaluation: match frozen scores only, no re-ranking."""
    total = len(frozen_scores)
    if not total or expected_total is not None and total != expected_total:
        raise ValueError("FROZEN_SCORE_COHORT_LENGTH_CHANGED")
    keys=[r["public_project_key_sha256"] for r in frozen_scores]
    if len(set(keys)) != total:
        raise ValueError("DUPLICATE_FROZEN_PUBLISHER_PROJECT_KEYS")
    eligible=[]
    missing=[]
    for index,row in enumerate(frozen_scores):
        ident=row["public_project_key_sha256"]
        if ident not in later:
            missing.append(ident)
            continue
        stage=later[ident]
        changed=stage != row["published_development_stage_at_asof"]
        score=row["stage_change_research_score"]
        if type(score) is not float or not 0 < score < 1:
            raise ValueError("FROZEN_SCORE_OUTSIDE_RESEARCH_BOUNDS")
        eligible.append((score,changed,ident,index))
    unknown_top = sum(x in set(keys[:TOP_N]) for x in missing)
    matched_top = min(TOP_N,total)-unknown_top
    coverage=len(eligible)/total
    if (coverage < MIN_COHORT_COVERAGE
            or matched_top/min(TOP_N,total) < MIN_TOP500_COVERAGE):
        raise ValueError("NEXT_EDITION_LABEL_COVERAGE_INSUFFICIENT")
    if len(later) < MIN_PUBLISHER_ROWS and total > 1000:
        raise ValueError("NEXT_EDITION_PUBLISHER_INVENTORY_TOO_SMALL")
    scored=[(s,y,k) for s,y,k,_ in eligible]
    pos=sum(y for _,y,_ in scored)
    if pos == 0 or pos == len(scored):
        raise ValueError("NO_BALANCED_PUBLISHER_STAGE_OUTCOMES_FOR_METRICS")
    # Preserve original top-500 membership. Missing projects are unknown, not
    # negative and never replaced by rank 501 or beyond.
    original_top=[(s,y,k) for s,y,k,rank in eligible if rank < min(TOP_N,total)]
    top_pos=sum(y for _,y,_ in original_top)
    base=pos/len(eligible)
    precision=top_pos/len(original_top)
    brier=sum((s-int(y))**2 for s,y,_ in scored)/len(scored)
    baseline_brier=sum((base-int(y))**2 for _,y,_ in scored)/len(scored)
    if training_only_constant_rate is not None:
        if type(training_only_constant_rate) is not float or not 0 < training_only_constant_rate < 1:
            raise ValueError("ORIGINAL_FROZEN_TRAINING_ONLY_BASELINE_RATE_INVALID")
        train_brier=sum((training_only_constant_rate-int(y))**2
                        for _,y,_ in scored)/len(scored)
        skill=(train_brier-brier)/train_brier if train_brier else None
    else:
        train_brier=None
        skill=None
    log_loss=-sum(int(y)*log(s)+(1-int(y))*log(1-s)
                  for s,y,_ in scored)/len(scored)
    # Fixed score-range bins, not dynamically recalibrated on future labels.
    bins=[]
    for i in range(10):
        part=[(s,y) for s,y,_ in scored
              if (i/10 <= s < (i+1)/10 if i<9 else i/10 <= s <= 1)]
        bins.append({
            "score_interval":[i/10,(i+1)/10],
            "count":len(part),
            "observed_change_fraction":round(sum(y for _,y in part)/len(part),6)
                 if part else None,
            "mean_frozen_score":round(sum(s for s,_ in part)/len(part),6)
                 if part else None,
        })
    return {
        "frozen_cohort_rows":total,
        "matched_publisher_project_rows":len(eligible),
        "missing_unlabelled_frozen_project_rows":len(missing),
        "new_only_publisher_rows_excluded":len(set(later)-set(keys)),
        "matched_cohort_coverage_fraction":round(coverage,6),
        "changed_published_development_stages":pos,
        "unchanged_published_development_stages":len(eligible)-pos,
        "observed_change_fraction":round(base,6),
        "original_fixed_top_n":min(TOP_N,total),
        "original_top_n_matched":len(original_top),
        "original_top_n_unknown_unlabelled":unknown_top,
        "original_top_n_stage_changes":top_pos,
        "fixed_top_n_precision_on_known_outcomes":round(precision,6),
        "fixed_top_n_recall_on_known_outcomes":round(top_pos/pos,6),
        "lift_vs_matched_base_rate":round(precision/base,6),
        "roc_auc":_auc_tie_aware(scored),
        "average_precision_tie_grouped":_average_precision_with_ties(scored),
        "brier_score_frozen_uncalibrated_research_scores":round(brier,6),
        "retrospective_matched_prevalence_brier_reference":round(baseline_brier,6),
        "frozen_training_only_constant_rate":training_only_constant_rate,
        "frozen_training_only_constant_brier":round(train_brier,6) if train_brier is not None else None,
        "brier_skill_against_frozen_training_only_constant":round(skill,6) if skill is not None else None,
        "research_score_log_loss":round(log_loss,6),
        "fixed_score_band_calibration":bins,
        "no_renormalization_of_missing_top_500":True,
        "missing_next_edition_projects_not_counted_as_negatives":True,
        "published_stage_changes_are_not_customer_demand_or_sales":True,
        "production_prediction_validation_authorized":False,
    }


def check_due(root: str | Path, *, now:datetime | None = None) -> dict:
    """Original owner only; no result is created until a verified Q4 appears."""
    repo=Path(root).resolve()
    if repo != Path("/srv/empire_os"):
        return {"status":"NONCANONICAL_RESEARCH_EVALUATION_HELD",
                "publication_outcome_rows_admitted":0}
    instant=now or datetime.now(timezone.utc)
    if not isinstance(instant,datetime) or instant.utcoffset() is None:
        raise ValueError("RESEARCH_EVALUATION_TIMESTAMP_TZ_REQUIRED")
    instant=instant.astimezone(timezone.utc)
    original=verify_frozen_cohort(repo)
    frozen=json.loads((repo/RECEIPT).read_text())
    outcome_path=repo/EVIDENCE
    if outcome_path.is_symlink():
        raise ValueError("UNSAFE_PROSPECTIVE_OUTCOME_RECEIPT_SYMLINK")
    if outcome_path.is_file():
        out=_read_receipt(outcome_path,SCHEMA)
        source_sha=out.get("source_snapshot_sha256")
        content_sha=out.get("outcome_object_sha256")
        if (out.get("status")!="VERIFIED_PUBLISHER_STAGE_RESEARCH_PROSPECTIVE_OUTCOMES"
                or out.get("frozen_score_sha256")!=original["score_object_sha256"]
                or not isinstance(content_sha,str)
                or not re.fullmatch(r"[0-9a-f]{64}",content_sha)
                or not isinstance(source_sha,str)
                or not re.fullmatch(r"[0-9a-f]{64}",source_sha)
                or out.get("outcome_object_filename")!="repd_2026-11-13_q4_outcomes_"+content_sha+".json"
                or out.get("customer_delivery_authorized") is not False
                or out.get("production_model_training_authorized") is not False):
            raise ValueError("EXISTING_PROSPECTIVE_OUTCOME_EVIDENCE_HELD")
        outcome_raw=_verified_private_file(
            repo/FREEZE_DIR/out["outcome_object_filename"],content_sha,65000)
        observed=json.loads(outcome_raw)
        if (observed.get("schema")!=SCHEMA
                or observed.get("frozen_score_sha256")!=original["score_object_sha256"]
                or observed.get("normalized_brokerage_csv_sha256")!=source_sha
                or observed.get("production_forecasts_produced")!=0
                or observed.get("customer_delivery_authorized") is not False):
            raise ValueError("PROSPECTIVE_OUTCOME_OBJECT_AUTHORITY_HOLD")
        return {"status":"VERIFIED_UNCHANGED_PUBLISHER_STAGE_OUTCOME_EVIDENCE",
                "cohort_rows":original["research_scored_projects"],
                "evaluation_writes":0,"production_forecasts_produced":0}
    state=_read_receipt(repo/STATE,SOURCE_SCHEMA)
    source=(state.get("datasets") or {}).get(DATASET)
    if not isinstance(source,dict):
        raise ValueError("NEW_REPD_OFFICIAL_SOURCE_RECEIPT_MISSING")
    allowed=_release_gate(source,frozen,instant)
    if allowed=="AWAITING_NEW_OFFICIAL_REPD_RELEASE":
        return {"status":allowed,
                "cohort_rows":original["research_scored_projects"],
                "future_official_outcome_rows":0,
                "evaluation_writes":0,
                "production_forecasts_produced":0,
                "customer_delivery_authorized":False}
    # Existing Cloud has already validated original source snapshot and digest.
    view=read_internal_brokerage_rows(
        repo,DATASET,limit=1,now=instant,
        system_research_context="EMPIRE_INTERNAL_RESEARCH_OBSERVE")
    if view["dataset_sha256"] != source["source_snapshot_sha256"]:
        raise ValueError("NEXT_EDITION_SOURCE_CLOUD_DIGEST_DRIFT")
    rows,_=_cloud_source(repo,DATASET)
    if len(rows) != source["row_count"]:
        raise ValueError("NEXT_EDITION_SOURCE_ROWS_CHANGED")
    raw_source_evidence=_verify_official_q4_raw_source(repo,source,rows)
    publisher_states,publisher_quality=_validate_status_rows(
        rows, published=datetime.fromisoformat(
            source["last_success_at"]).date(),
        id_key="project_ref",stage_key="development_status",
        update_key="record_last_updated",technology_key="technology")
    outcome={
        sha256(("REPD:PROJECT:V1:"+ref).encode()).hexdigest():item["status"]
        for ref,item in publisher_states.items()
    }
    if len(outcome)!=len(rows):
        raise ValueError("DUPLICATE_PUBLICATION_PROJECT_ID")
    frozen_data=json.loads((repo/RECEIPT).read_text())
    freeze_bytes=_verified_private_file(
        repo/FREEZE_DIR/frozen_data["score_object_filename"],
        frozen_data["score_object_sha256"],MAX_SCORE_BYTES)
    fixed=[json.loads(line) for line in freeze_bytes.splitlines()]
    model_bytes=_verified_private_file(
        repo/FREEZE_DIR/frozen_data["model_object_filename"],
        frozen_data["model_object_sha256"],MAX_MODEL_BYTES)
    model=json.loads(model_bytes)
    if model.get("model_authority")!="RESEARCH_OBSERVE_ONLY":
        raise ValueError("FROZEN_RESEARCH_BASELINE_MODEL_AUTHORITY_HOLD")
    metrics=compare_fixed_cohort(
        fixed,outcome,expected_total=14967,
        training_only_constant_rate=model["global_smoothed_rate"])
    result={
        "schema":SCHEMA,
        "status":"VERIFIED_PUBLISHER_STAGE_RESEARCH_PROSPECTIVE_OUTCOMES",
        "evaluated_at":instant.isoformat(timespec="seconds"),
        "publisher_release":"Q4_2026",
        "publisher_official_asset_url":source["source_url"],
        "publisher_first_verified_at":source["last_success_at"],
        "normalized_brokerage_csv_sha256":source["source_snapshot_sha256"],
        "raw_official_publisher_binary_sha256_independently_preserved":True,
        "original_brokerage_source_receipt_status":source["source_status"],
        "original_brokerage_cloud_source_count":len(rows),
        "future_publisher_record_quality":publisher_quality,
        "official_raw_publisher_source_evidence":raw_source_evidence,
        "frozen_at":original["frozen_at"],
        "frozen_source_publisher_asof":original["publisher_asof_date"],
        "frozen_score_sha256":original["score_object_sha256"],
        "frozen_model_sha256":original["model_object_sha256"],
        "fixed_cohort_evaluation":metrics,
        "frozen_project_ranking_was_not_changed":True,
        "future_outcomes_only_from_official_source":True,
        "next_source_publication_exact_day_not_independently_verified":True,
        "research_only":True,
        "production_model_training_authorized":False,
        "customer_delivery_authorized":False,
        "tenant_exposure_authorized":False,
        "outbound_sent":False,
        "production_forecasts_produced":0,
        "model_accuracy_approved_for_customer_products":False,
    }
    # Preserve full content as a SHA-addressed research object. Create the
    # small commit receipt LAST, with fixed source and object digests.
    raw=(json.dumps(result,sort_keys=True,indent=2)+"\n").encode()
    digest=sha256(raw).hexdigest()
    object_name="repd_2026-11-13_q4_outcomes_"+digest+".json"
    object_path=repo/FREEZE_DIR/object_name
    _immutable_create(object_path,raw)
    _verified_private_file(object_path,digest,65000)
    manifest={
        "schema":SCHEMA,
        "status":result["status"],
        "recorded_at":instant.isoformat(timespec="seconds"),
        "frozen_score_sha256":original["score_object_sha256"],
        "source_snapshot_sha256":source["source_snapshot_sha256"],
        "outcome_object_filename":object_name,
        "outcome_object_sha256":digest,
        "customer_delivery_authorized":False,
        "production_model_training_authorized":False,
        "production_forecasts_produced":0,
    }
    commit=(json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode()
    if not _immutable_create(outcome_path,commit):
        raise ValueError("PROSPECTIVE_PUBLICATION_RESULT_ALREADY_CREATED")
    return {
        "status":result["status"],"cohort_rows":14967,
        "matched_outcomes":metrics["matched_publisher_project_rows"],
        "evaluation_writes":1,"production_forecasts_produced":0,
        "customer_delivery_authorized":False,
    }
