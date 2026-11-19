"""Authenticated-empty registry classification preserves independent sources.

The adjudicator must not use unrelated research 'hold_reason' as verified
Forecast Revenue quarantine. The original guarded promoter is unchanged.
"""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime,timezone
from pathlib import Path
from copy import deepcopy
import json

import pytest

from empire_os.runtime_control_adjudication import AdjudicatedControl
from empire_os.predictive_registry_observation_guard import (
    revoke_legacy_forecast_claims, authenticated_empty_registry,
)
from scripts import adjudicate_runtime_control_evidence as owner


def adjudicated(control="quarantine", *, verified=True, sources=None):
    return AdjudicatedControl(
        lane="predictive_revenue",control=control,
        status="VERIFIED_RUNTIME" if verified else "UNVERIFIED",
        confidence=.99 if verified else 0.,
        artifact_paths=tuple(sources if sources is not None else [
            "runtime/predictive_cloud/brokerage_fundraising_source_latest.json"]),
        matched_keys=("hold_reason",) if verified else (),
        active_units=("empire-predictive-cloud-materializer.timer",),
        reason="recent_structured_runtime_artifact_with_exact_control_signature",
    )


def test_authenticated_zero_never_accepts_other_owner_quarantine_as_forecast():
    old=adjudicated()
    new=owner.restrict_empty_registry_claim(
        old,lane="predictive_revenue",control="quarantine",authenticated_zero=True)
    assert old.status=="VERIFIED_RUNTIME" and old.confidence==.99
    assert new.status=="SOURCE_EVIDENCE_ONLY" and new.confidence==0.
    assert new.matched_keys==()
    assert new.artifact_paths==old.artifact_paths
    assert new.active_units==old.active_units
    assert "NOT_FORECAST_VERIFICATION" in new.reason


def test_positive_forecast_case_and_other_owner_lanes_are_untouched():
    old=adjudicated()
    assert owner.restrict_empty_registry_claim(
        old,lane="predictive_revenue",control="quarantine",authenticated_zero=False)==old
    assert owner.restrict_empty_registry_claim(
        old,lane="opportunities",control="quarantine",authenticated_zero=True)==old
    assert owner.restrict_empty_registry_claim(
        old,lane="predictive_revenue",control="action_authority",authenticated_zero=True)==old


def test_no_evidence_means_unverified_not_fake_verified():
    old=adjudicated(verified=False,sources=[])
    new=owner.restrict_empty_registry_claim(
        old,lane="predictive_revenue",control="quarantine",authenticated_zero=True)
    assert new.status=="UNVERIFIED" and new.confidence==0 and new.artifact_paths==()


def test_source_only_is_not_downgraded_by_guard_or_promoted_to_forecast():
    original_controls={}
    for key in (
        "canonical_identity","conflict_detection","duplicate_detection",
        "entity_classification","input_quality","output_quality",
        "quarantine","outcome_linkage",
    ):
        original_controls[key]={"status":"UNVERIFIED","artifact_paths":[]}
    old=adjudicated()
    narrowed=owner.restrict_empty_registry_claim(
        old,lane="predictive_revenue",control="quarantine",authenticated_zero=True)
    original_controls["quarantine"].update(narrowed.as_dict())
    previous=deepcopy(original_controls)
    assert revoke_legacy_forecast_claims(original_controls)==[]
    assert original_controls==previous
    assert original_controls["quarantine"]["status"]!="VERIFIED_RUNTIME"


def test_real_brokerage_source_artifact_is_not_written_or_removed(tmp_path,monkeypatch):
    evidence=tmp_path/"runtime/predictive_cloud/brokerage_fundraising_source_latest.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(json.dumps({
        "schema_version":"test.private.research",
        "status":"VERIFIED_RESEARCH_ONLY","generated_at":"2026-11-19T11:00:00+00:00",
        "fundraising_hold_reason":"RIGHTS_REVIEW_REQUIRED",
    }))
    initial=evidence.read_bytes()
    candidates=tmp_path/"candidates.json"
    candidates.write_text(json.dumps({"lanes":[{
        "lane":"predictive_revenue",
        "units":[{"unit":"empire-predictive-cloud-materializer.timer",
                  "active_state":"active"}],
        "control_candidates":{"quarantine":{
            "artifact_paths":["runtime/predictive_cloud/brokerage_fundraising_source_latest.json"],
            "unit_names":[],
        }},
    }]}))
    results=[]
    monkeypatch.setattr(owner,"ROOT",tmp_path)
    monkeypatch.setattr(owner,"INPUT",candidates)
    monkeypatch.setattr(owner,"current_authenticated_empty_registry",lambda _:True)
    monkeypatch.setattr(owner,"atomic_write",lambda _path,payload:results.append(payload))
    monkeypatch.setattr(owner,"adjudicate_control",
        lambda root,lane,control,artifact_paths,active_units:
            AdjudicatedControl(
                lane=lane,control=control,
                status="VERIFIED_RUNTIME" if control=="quarantine" else "UNVERIFIED",
                confidence=.99 if control=="quarantine" else 0.,
                artifact_paths=tuple(artifact_paths),
                matched_keys=("hold_reason",) if control=="quarantine" else (),
                active_units=tuple(active_units),reason="test original source owner"))
    owner.main()
    assert len(results)==1
    row=results[0]["lanes"][0]
    assert "quarantine" not in row["verified_controls"]
    assert row["controls"]["quarantine"]["status"]=="SOURCE_EVIDENCE_ONLY"
    assert list(row["controls"]["quarantine"]["artifact_paths"])==[
        "runtime/predictive_cloud/brokerage_fundraising_source_latest.json"]
    assert list(row["controls"]["quarantine"]["matched_keys"])==[]
    assert evidence.read_bytes()==initial
