"""Root-attested REVIEW -> DONE finalisation for the native department queue.

This module is dormant unless explicitly invoked with a feature flag. Receipts
must be issued by a separately privileged verifier and stored in the fixed
root-controlled receipt directory. Agent-written JSON is NEVER a credential.
Neither this module nor a passing receipt can deploy, send, settle or merge.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

from empire_os.factory_hybrid_review_v1 import assess_held_review, REVIEWED

SCHEMA = "empire.factory_hybrid_review_receipt.v1"
TRUST_ROOT = Path("/etc/empire_os/factory_review_receipts")
WORK_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40,64}\Z")


class FinalisationDenied(ValueError):
    pass


@dataclass(frozen=True)
class FinalisationDecision:
    allowed: bool
    reason: str
    work_id: str
    evidence_refs: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "empire.factory_hybrid_finalisation.v1",
            "allowed": self.allowed,
            "reason": self.reason,
            "work_id": self.work_id,
            "evidence_refs": list(self.evidence_refs),
            "production_deploy": False,
            "production_merge": False,
            "external_send": False,
            "payment_action": False,
            "revenue_recognition": False,
            "execution_authority": "none",
        }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _reject(work_id: str, reason: str) -> FinalisationDecision:
    return FinalisationDecision(False, reason, work_id)


def assess_finalisation(
    *, work_record: Mapping[str, Any], record_bytes: bytes,
    receipt: Mapping[str, Any],
) -> FinalisationDecision:
    """Pure semantic validation; caller MUST authenticate receipt provenance."""
    item = _mapping(work_record)
    proof = _mapping(receipt)
    work_id = _text(item.get("id"))
    if not WORK_ID.fullmatch(work_id):
        return _reject(work_id, "invalid_work_id")
    if _text(item.get("status")) != "REVIEW":
        return _reject(work_id, "not_in_review")
    if item.get("lease_id") is not None or item.get("worker_id") is not None:
        return _reject(work_id, "review_still_leased")
    # A decision-identity work item needs the native execution-binding contract;
    # this separate reviewer is not authorised to bypass that contract.
    if item.get("decision_identity") is not None:
        return _reject(work_id, "native_decision_identity_binding_required")
    if proof.get("schema_version") != SCHEMA:
        return _reject(work_id, "receipt_schema_mismatch")
    if proof.get("work_id") != work_id:
        return _reject(work_id, "receipt_wrong_work")
    digest = hashlib.sha256(record_bytes).hexdigest()
    if proof.get("review_record_sha256") != digest:
        return _reject(work_id, "receipt_stale_or_modified_work")
    if proof.get("issuer") != "empire_root_review_governor":
        return _reject(work_id, "issuer_not_governor")
    if proof.get("decision") != "APPROVED_WITH_RUNTIME_PROOF":
        return _reject(work_id, "not_approved")
    # An agent cannot upgrade its own result to execution authority.
    if any(proof.get(k) is not False for k in (
        "production_deploy", "production_merge", "external_send",
        "payment_action", "revenue_recognition",
    )) or proof.get("execution_authority") != "none":
        return _reject(work_id, "receipt_claims_operational_authority")

    quality_request = _mapping(proof.get("quality_request"))
    assessment = assess_held_review(
        work_item=item,
        quality_request=quality_request,
        self_review=_mapping(proof.get("self_review")),
        independent_review=_mapping(proof.get("independent_review")),
        promptfoo_result=_mapping(proof.get("promptfoo_result")),
        council_result=_mapping(proof.get("council_result")),
    )
    if assessment.status != REVIEWED:
        return _reject(work_id, "review_gate_" + assessment.status.lower() + ":" + assessment.reason)

    runtime = _mapping(proof.get("runtime_proof"))
    if (runtime.get("status") != "PASS"
            or runtime.get("work_id") != work_id
            or runtime.get("proposal_branch") != assessment.proposal_branch
            or runtime.get("production_verified") is not True
            or runtime.get("read_only_probe") is not True
            or runtime.get("environment") != "production"
            or runtime.get("tests_passed") is not True
            or runtime.get("simulated") is not False
            or runtime.get("shadow_only") is not False):
        return _reject(work_id, "trusted_production_runtime_proof_missing")
    builder_id = _text(quality_request.get("builder_id"))
    verifier = _text(runtime.get("verifier_id"))
    independent = _text(_mapping(proof.get("independent_review")).get("reviewer_id"))
    if not verifier or verifier in {builder_id, independent}:
        return _reject(work_id, "runtime_verifier_not_independent")
    commit = _text(runtime.get("production_commit"))
    candidate_commit = _text(proof.get("candidate_commit"))
    if (not COMMIT.fullmatch(commit) or commit != candidate_commit):
        return _reject(work_id, "production_revision_unbound")
    runtime_ref = _text(runtime.get("evidence_ref"))
    if not runtime_ref:
        return _reject(work_id, "runtime_evidence_ref_missing")
    verified_at = _text(runtime.get("verified_at"))
    try:
        parsed = datetime.fromisoformat(verified_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone missing")
        delta = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
        if not 0 <= delta <= 86400:
            raise ValueError("stale or future")
    except ValueError:
        return _reject(work_id, "runtime_proof_stale_or_invalid")
    # No founder-gated operation can be auto-finalised; the quality gate has
    # already rejected founder_gate_required=True.
    refs = tuple(dict.fromkeys((*assessment.evidence_refs, runtime_ref)))
    if not refs:
        return _reject(work_id, "no_verification_evidence")
    return FinalisationDecision(True, "independent_review_and_production_runtime_verified", work_id, refs)


def load_root_attested_receipt(work_id: str) -> dict[str, Any]:
    """Require a fixed root-owned, non-group-writable file AND directory.

    No user-selected path, symlinks, group-write or world-write permissions.
    Ownership is an OS trust boundary; only root-governed attesters can issue.
    """
    if not WORK_ID.fullmatch(work_id):
        raise FinalisationDenied("invalid_work_id")
    path = TRUST_ROOT / (work_id + ".json")
    for directory in (TRUST_ROOT.parent, TRUST_ROOT):
        if directory.is_symlink() or not directory.is_dir():
            raise FinalisationDenied("receipt_directory_missing_or_symlink")
        stat = directory.stat()
        if stat.st_uid != 0 or stat.st_mode & 0o022:
            raise FinalisationDenied("receipt_directory_not_root_protected")
    if path.is_symlink() or not path.is_file():
        raise FinalisationDenied("receipt_missing_or_symlink")
    stat = path.stat()
    if stat.st_uid != 0 or stat.st_mode & 0o022:
        raise FinalisationDenied("receipt_not_root_protected")
    # Avoid oversized or arbitrary content. Root-only writers guarantee that
    # an unprivileged builder cannot replace this receipt concurrently.
    if stat.st_size > 256_000:
        raise FinalisationDenied("receipt_too_large")
    try:
        with path.open("rb") as stream:
            loaded = json.load(stream)
    except (OSError, UnicodeError, ValueError) as exc:
        raise FinalisationDenied("receipt_unreadable") from exc
    if not isinstance(loaded, dict):
        raise FinalisationDenied("receipt_invalid_shape")
    return loaded


def finalize_review_locked(queue: Any, work_id: str) -> Any:
    """Explicit root-governed REVIEW->DONE; NEVER called by normal workers.

    The queue lock is held across locating, assessing and moving the record.
    Avoid calling queue.complete(), whose lease contract only permits RUNNING.
    """
    if os.environ.get("EMPIRE_HYBRID_FACTORY_FINALISE_V1") != "1":
        raise FinalisationDenied("finalisation_not_enabled")
    if os.geteuid() != 0:
        raise FinalisationDenied("privileged_governor_required")
    if not WORK_ID.fullmatch(work_id):
        raise FinalisationDenied("invalid_work_id")
    receipt = load_root_attested_receipt(work_id)
    with queue._locked():
        current = queue.review / f"{queue._safe(work_id)}.json"
        destination = queue.done / current.name
        if current.is_symlink() or not current.is_file():
            raise FinalisationDenied("review_record_missing")
        if destination.exists() or destination.is_symlink():
            raise FinalisationDenied("conflicting_done_record")
        # Fail closed if the ID appears in any other lane.
        for lane in (queue.ready, queue.running, queue.blocked, queue.failed):
            if (lane / current.name).exists():
                raise FinalisationDenied("duplicate_work_identity")
        original = current.read_bytes()
        try:
            record = json.loads(original)
        except (UnicodeError, ValueError) as exc:
            raise FinalisationDenied("review_record_unreadable") from exc
        if not isinstance(record, dict) or record.get("id") != work_id:
            raise FinalisationDenied("review_record_identity_mismatch")
        decision = assess_finalisation(work_record=record, record_bytes=original, receipt=receipt)
        if not decision.allowed:
            raise FinalisationDenied(decision.reason)
        item = queue._load(current)
        # This status means verified completion of department work with live
        # runtime evidence, NOT permission to deploy or make commercial changes.
        from empire_os.department_work_queue import DepartmentWorkStatus
        item.status = DepartmentWorkStatus.DONE
        new_result = deepcopy(record.get("result") or {})
        new_result["factory_finalisation"] = decision.as_dict()
        new_result["factory_finalisation"]["receipt_ref"] = str(TRUST_ROOT / (work_id + ".json"))
        new_result["status"] = "COMPLETED"
        new_result["production_deploy"] = False
        new_result["production_merge"] = False
        new_result["external_send"] = False
        new_result["payment_action"] = False
        new_result["revenue_recognition"] = False
        new_result["execution_authority"] = "none"
        item.result = new_result
        item.result_evidence_refs = decision.evidence_refs
        item.error = None
        item.updated_at = datetime.now(timezone.utc).isoformat()
        # Equivalent to native _finish atomic rename semantics.
        queue._write(current, item)
        current.replace(destination)
        return item
