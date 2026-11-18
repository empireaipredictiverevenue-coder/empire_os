"""Research-only chronological baseline evaluation for original Predictive Cloud.

Pure Python, no model registration/training, private predictions, customer UI,
weights persistence, tenant access or external calls. Historical labels are
publisher stage changes, NOT leads, actual construction, buyer demand or sales.

Fit a small pre-specified stage/technology smoothing estimator only on rows
whose publisher label was already available at holdout as-of publication.
Compare to training-only constant base-rate, never tune on the holdout.
"""
from __future__ import annotations

from collections import Counter
from math import log
from typing import Any


def _require_asof_separation(training: list[dict], test: list[dict]) -> None:
    if not training or not test:
        raise ValueError("EMPTY_RESEARCH_TRAIN_OR_TEST_FOLD")
    asof = {x["features_available_after_publisher_edition"] for x in test}
    if len(asof) != 1:
        raise ValueError("MIXED_RESEARCH_TEST_ASOF")
    cutoff = next(iter(asof))
    if any(x.get("label_is_publisher_change_not_business_outcome") is not True
           or x.get("training_admission_allowed") is not False
           for x in training + test):
        raise ValueError("UNTRUSTED_RESEARCH_OUTCOME_LABEL_AUTHORITY")
    if any(x["label_available_after_publisher_edition"] > cutoff
           or x["features_available_after_publisher_edition"]
                >= x["label_available_after_publisher_edition"]
           for x in training):
        raise ValueError("FUTURE_OUTCOME_LEAKAGE_IN_RESEARCH_TRAINING_FOLD")
    if any(x["label_available_after_publisher_edition"] <= cutoff
           or x["features_available_after_publisher_edition"] != cutoff
           for x in test):
        raise ValueError("HOLDOUT_TEMPORAL_ORDER_INVALID")


def _fit(training: list[dict]) -> tuple[float, dict, dict]:
    positives = sum(x["published_stage_changed"] is True for x in training)
    base = (positives + 1) / (len(training) + 2)
    stage_counts: Counter[str] = Counter()
    stage_positive: Counter[str] = Counter()
    mix_counts: Counter[tuple[str,str]] = Counter()
    mix_positive: Counter[tuple[str,str]] = Counter()
    for row in training:
        stage = row["development_stage_at_asof"]
        mix = (stage, row["technology_at_asof"])
        stage_counts[stage] += 1
        mix_counts[mix] += 1
        if row["published_stage_changed"]:
            stage_positive[stage] += 1
            mix_positive[mix] += 1
    # Pre-specified shrinkage; neither constants nor categories use test labels.
    stage_rate = {
        stage: (stage_positive[stage] + 50 * base) / (count + 50)
        for stage, count in stage_counts.items()
    }
    mixed_rate = {
        mix: (mix_positive[mix] + 100 * stage_rate[mix[0]]) / (count + 100)
        for mix, count in mix_counts.items()
    }
    return base, stage_rate, mixed_rate


def _auc_tie_aware(scored: list[tuple[float,bool,str]]) -> float | None:
    positive = sum(int(y) for _, y, _ in scored)
    negative = len(scored) - positive
    if positive == 0 or negative == 0:
        return None
    sorted_rows = sorted(scored, key=lambda t:t[0])
    lower_negatives = 0
    credit = 0.0
    idx = 0
    while idx < len(sorted_rows):
        end = idx + 1
        while end < len(sorted_rows) and sorted_rows[end][0] == sorted_rows[idx][0]:
            end += 1
        group_pos = sum(x[1] for x in sorted_rows[idx:end])
        group_neg = end-idx-group_pos
        credit += group_pos*(lower_negatives+0.5*group_neg)
        lower_negatives += group_neg
        idx = end
    return round(credit/(positive*negative),6)


def _metrics(training: list[dict], holdout: list[dict]) -> dict:
    _require_asof_separation(training,holdout)
    base, stage_rate, mixed_rate = _fit(training)
    scored = []
    for row in holdout:
        key = (row["development_stage_at_asof"],row["technology_at_asof"])
        p = mixed_rate.get(key,stage_rate.get(key[0],base))
        if not 0 < p < 1:
            raise ValueError("INVALID_RESEARCH_SMOOTHED_RATE")
        scored.append((p,bool(row["published_stage_changed"]),
                       row["source_project_key_sha256"]))
    total=len(scored)
    changed=sum(y for _,y,_ in scored)
    global_brier = sum((base-int(y))**2 for _,y,_ in scored)/total
    experimental_brier = sum((p-int(y))**2 for p,y,_ in scored)/total
    brier_skill=(global_brier-experimental_brier)/global_brier if global_brier else 0.
    log_loss = -sum(y*log(p)+(1-y)*log(1-p) for p,y,_ in scored)/total
    # Fixed review capacity of 500 cases is specified BEFORE seeing heldout labels.
    k=min(500,total)
    rank=sorted(scored,key=lambda t:(-t[0],t[2]))
    top_true=sum(y for _,y,_ in rank[:k])
    prior_holdout=changed/total
    precision=top_true/k
    # Equal-frequency deciles summarise calibration; are descriptive not
    # independently calibrated probabilities.
    ordered=sorted(scored,key=lambda t:(t[0],t[2]))
    bins=[]
    for idx in range(10):
        chunk=ordered[idx*total//10:(idx+1)*total//10]
        if not chunk:continue
        bins.append({
            "count":len(chunk),
            "mean_experimental_score":round(sum(p for p,_,_ in chunk)/len(chunk),6),
            "observed_stage_change_share":round(sum(y for _,y,_ in chunk)/len(chunk),6),
        })
    return {
        "training_rows":len(training),
        "training_event_rows":sum(x["published_stage_changed"] is True for x in training),
        "training_only_global_rate":round(base,6),
        "test_asof_date":holdout[0]["features_available_after_publisher_edition"],
        "test_outcome_release_date":holdout[0]["label_available_after_publisher_edition"],
        "test_rows":total,
        "test_stage_changed":changed,
        "test_observed_change_share":round(prior_holdout,6),
        "experimental_stage_technology_brier":round(experimental_brier,6),
        "training_prevalence_constant_baseline_brier":round(global_brier,6),
        "brier_skill_vs_training_prevalence_constant":round(brier_skill,6),
        "experimental_research_roc_auc":_auc_tie_aware(scored),
        "experimental_research_log_loss":round(log_loss,6),
        "top_n_predefined":k,
        "experiment_top_n_true_changes":top_true,
        "experiment_precision_at_n":round(precision,6),
        "experiment_recall_at_n":round(top_true/changed,6) if changed else None,
        "holdout_unranked_prevalence":round(prior_holdout,6),
        "top_n_lift_vs_holdout_prevalence":round(precision/prior_holdout,6) if prior_holdout else None,
        "calibration_deciles":bins,
        "majority_no_change_recall":0.0 if changed else None,
        "majority_no_change_apparent_accuracy":round(1-prior_holdout,6),
        "no_frozen_prospective_predictions":True,
        "not_customer_sales_or_conversions":True,
        "research_only_no_production_weight_registration":True,
        "not_an_independently_replicated_forecasting_result":True,
    }


def research_walkforward(frames: list[list[dict]]) -> dict:
    """Chronological folds: Jan→May trains May→Aug, then both train Aug→Nov."""
    if len(frames) != 3 or any(len(row)<100 for row in frames):
        raise ValueError("THREE_REAL_QUARTERLY_WINDOWS_REQUIRED")
    if not (frames[0][0]["label_available_after_publisher_edition"]
            ==frames[1][0]["features_available_after_publisher_edition"]
            and frames[1][0]["label_available_after_publisher_edition"]
            ==frames[2][0]["features_available_after_publisher_edition"]):
        raise ValueError("NONCONTIGUOUS_PUBLISHER_RELEASE_WINDOWS")
    first=_metrics(frames[0],frames[1])
    final=_metrics(frames[0]+frames[1],frames[2])
    return {
        "status":"RETROSPECTIVE_RESEARCH_ONLY_CHRONOLOGICAL_HOLDOUT",
        "estimator":"PRE_SPECIFIED_STAGE_TECH_HIERARCHICAL_RATE_SHRINKAGE_50_100",
        "experimental_score_only":True,
        "training_data_after_holdout_asof_admitted":False,
        "selection_tuning_on_test_forbidden":True,
        "first_exploratory_validation":first,
        "latest_out_of_time_holdout":final,
        "future_independent_quarterly_holdout_required":True,
        "independently_validated_production_model":False,
        "production_model_weights_created":False,
        "production_training_samples_admitted":0,
        "customer_revenue_outcomes_included":0,
        "model_deployment_authorized":False,
    }
