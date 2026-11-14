"""MiniMind shadow evaluator backed by EmpireOS's existing ICP classifier.

No model inference, training, network calls, customer data exports, or promotion.
Human-reviewed labels and candidate predictions are optional external inputs;
they are NOT inferred from the baseline's own weak labels.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from urllib.parse import urlsplit, urlunsplit

from empire_os.icp_intent_relevance import classify_icp_intent

HISTORY_SCHEMA = "empire.community_intent_history.v1"
SCHEMA = "empire.minimind_intent_shadow.v1"
ALLOWED_CLASSES = frozenset((
    "SELLER_PITCH",
    "EXPLICIT_REQUEST_UNVERIFIED",
    "CONTENT_OR_ADVICE",
    "OPERATOR_PROBLEM_SELF_REPORTED",
    "UNATTRIBUTED_DISCUSSION",
    "NON_COMMERCIAL_HIRING_OR_CAREER",
))
DOMAINS = {
    "reddit": ("reddit.com", "www.reddit.com", "old.reddit.com"),
    "linkedin": ("linkedin.com", "www.linkedin.com"),
}
MAX_ROWS = 2000


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def build_manifest(history: Mapping[str, object]) -> dict:
    """Hash public research items; export no names, URLs, titles or post text."""
    if not isinstance(history, Mapping) or history.get("schema_version") != HISTORY_SCHEMA:
        raise ValueError("invalid canonical community-intent history")
    observations = history.get("observations")
    if not isinstance(observations, list) or len(observations) > MAX_ROWS:
        raise ValueError("unbounded or invalid observations")
    entries = {}
    for observation in observations:
        if not isinstance(observation, Mapping):
            raise ValueError("malformed observation")
        source, url = observation.get("source"), observation.get("url")
        if source not in DOMAINS or not isinstance(url, str):
            continue
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in DOMAINS[source]:
            continue
        if parsed.username or parsed.password or parsed.fragment:
            continue
        title, text = observation.get("title"), observation.get("text")
        if not isinstance(title, str) or not isinstance(text, str):
            continue
        if not title.strip() and not text.strip():
            continue
        if len(title) > 5000 or len(text) > 50000:
            raise ValueError("oversized observation")
        ref = _digest(source + "\0" + url)
        input_digest = _digest(title + "\0" + text)
        if ref in entries:
            if entries[ref]["input_digest"] != input_digest:
                # A changed post must not inherit an older human label.
                raise ValueError("ambiguous changed observation for one source")
            continue
        baseline = classify_icp_intent(observation)
        entries[ref] = {
            "sample_ref": ref,
            "input_digest": input_digest,
            "source_class": source,
            "baseline_intent_class": baseline["intent_class"],
            "label_source": "DETERMINISTIC_WEAK_BASELINE_NOT_GOLD",
            "review_required": True,
            "buyer_identity_verified": False,
            "commercial_intent_verified": False,
            "outbound_authorized": False,
        }
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "samples": sorted(entries.values(), key=lambda x: x["sample_ref"]),
        "sample_count": len(entries),
        "raw_post_content_exported": False,
        "synthetic_labels_as_truth": False,
        "model_training_authorized": False,
        "outbound_authorized": False,
    }


def _index_rows(rows: object, *, kind: str, expected: Mapping[str, dict]) -> dict:
    if rows is None:
        return {}
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("invalid " + kind + " rows")
    indexed = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("invalid " + kind + " row")
        ref = row.get("sample_ref")
        if not isinstance(ref, str) or ref not in expected or ref in indexed:
            raise ValueError("unknown or duplicated " + kind + " identity")
        if row.get("input_digest") != expected[ref]["input_digest"]:
            raise ValueError("stale or mismatched " + kind + " text digest")
        label = row.get("label")
        if not isinstance(label, str) or label not in ALLOWED_CLASSES:
            raise ValueError("invalid " + kind + " label")
        if kind == "adjudication":
            if (row.get("human_reviewed") is not True
                    or row.get("synthetic") is not False
                    or row.get("usage_scope") != "EVALUATION_ONLY"
                    or not isinstance(row.get("review_ref"), str)
                    or not row["review_ref"].strip()):
                raise ValueError("unreviewed or unauthorized adjudication")
        else:
            if (row.get("model_family") != "minimind"
                    or not isinstance(row.get("model_version"), str)
                    or not row["model_version"].strip()
                    or row.get("shadow_only") is not True):
                raise ValueError("unproven MiniMind candidate prediction")
        indexed[ref] = row
    return indexed


def evaluate_manifest(
    manifest: Mapping[str, object], *, adjudications: object = None,
    model_predictions: object = None, min_samples: int = 30,
) -> dict:
    """No model improvement claims from the baseline's own weak labels."""
    if type(min_samples) is not int or min_samples < 20:
        raise ValueError("minimum adjudication cohort is 20")
    if (not isinstance(manifest, Mapping)
            or manifest.get("schema_version") != SCHEMA
            or manifest.get("mode") != "OBSERVE"
            or manifest.get("execution_authority") != "none"
            or manifest.get("raw_post_content_exported") is not False
            or manifest.get("model_training_authorized") is not False):
        raise ValueError("unsafe shadow manifest")
    rows = manifest.get("samples")
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("invalid samples")
    lookup = {}
    for row in rows:
        if (not isinstance(row, Mapping)
                or row.get("baseline_intent_class") not in ALLOWED_CLASSES
                or not isinstance(row.get("sample_ref"), str)
                or row["sample_ref"] in lookup
                or not isinstance(row.get("input_digest"), str)):
            raise ValueError("invalid or duplicated baseline sample")
        lookup[row["sample_ref"]] = dict(row)
    if manifest.get("sample_count") != len(lookup):
        raise ValueError("manifest count mismatch")
    gold = _index_rows(adjudications, kind="adjudication", expected=lookup)
    candidates = _index_rows(model_predictions, kind="prediction", expected=lookup)
    paired = [ref for ref in gold if ref in candidates]
    enough = len(paired) >= min_samples and len(gold) >= min_samples
    # Every independently reviewed item must be predicted to prevent cherry-picking.
    complete = enough and len(paired) == len(gold)
    baseline_accuracy = candidate_accuracy = beats = None
    if complete:
        baseline_accuracy = round(
            sum(lookup[ref]["baseline_intent_class"] == row["label"] for ref, row in gold.items())
            / len(gold), 6
        )
        candidate_accuracy = round(
            sum(candidates[ref]["label"] == row["label"] for ref, row in gold.items())
            / len(gold), 6
        )
        beats = candidate_accuracy > baseline_accuracy
    blockers = []
    if len(gold) < min_samples:
        blockers.append("independent_human_adjudications_insufficient")
    if not candidates:
        blockers.append("minimind_model_predictions_absent")
    elif len(paired) != len(gold):
        blockers.append("holdout_prediction_coverage_incomplete")
    if not complete and not blockers:
        blockers.append("cohort_below_minimum")
    return {
        "schema_version": SCHEMA + ".evaluation",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "sample_count": len(lookup),
        "reviewer_attested_label_count": len(gold),
        "candidate_prediction_count": len(candidates),
        "matched_evaluation_count": len(paired),
        "evaluation_ready": complete,
        "blockers": blockers,
        "baseline_accuracy": baseline_accuracy,
        "candidate_accuracy": candidate_accuracy,
        "candidate_beats_baseline": beats,
        "statistical_significance_established": False,
        "model_promotion_authorized": False,
        "model_training_authorized": False,
        "live_model_inference_performed": False,
        "commercial_activation_authorized": False,
        "outbound_authorized": False,
    }


def build_review_queue(history: Mapping[str, object], manifest: Mapping[str, object]) -> dict:
    """Internal source-linked review queue; not an export or a training dataset.

    Links permit a reviewer to inspect the original public post. No raw post
    text, authors, inferred gold labels, or identity claims are stored here.
    """
    if not isinstance(manifest, Mapping) or manifest.get("schema_version") != SCHEMA:
        raise ValueError("invalid MiniMind review manifest")
    if not isinstance(history, Mapping) or history.get("schema_version") != HISTORY_SCHEMA:
        raise ValueError("invalid community intent source")
    expected = {row["sample_ref"]: row for row in manifest["samples"]}
    queue = {}
    for observation in history.get("observations", []):
        if not isinstance(observation, Mapping):
            raise ValueError("malformed review observation")
        source, url = observation.get("source"), observation.get("url")
        if source not in DOMAINS or not isinstance(url, str):
            continue
        parts = urlsplit(url)
        if (parts.scheme != "https" or parts.hostname not in DOMAINS[source]
                or parts.username or parts.password or parts.fragment):
            continue
        ref = _digest(source + "\0" + url)
        item = expected.get(ref)
        if item is None:
            continue
        if ref in queue:
            continue
        # Keep the link for human access only; never add it to model samples.
        clean_url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        kind = item["baseline_intent_class"]
        priority = ("HIGH" if kind == "EXPLICIT_REQUEST_UNVERIFIED"
                    else "MEDIUM" if kind == "OPERATOR_PROBLEM_SELF_REPORTED"
                    else "LOW")
        queue[ref] = {
            "sample_ref": ref, "input_digest": item["input_digest"],
            "public_review_url": clean_url, "source_class": source,
            "review_priority": priority, "review_status": "UNREVIEWED",
            "proposed_weak_label": kind, "independent_gold_label": None,
            "requires_authorized_human_review": True,
            "verified_buyer_intent": False, "outbound_authorized": False,
        }
    ordered = sorted(queue.values(), key=lambda x: (
        {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[x["review_priority"]],
        x["sample_ref"],
    ))
    return {
        "schema_version": "empire.minimind_intent_review_queue.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "review_queue_count": len(ordered), "review_items": ordered,
        "contains_public_source_links": True, "contains_raw_post_text": False,
        "training_dataset": False, "independent_gold_labels_collected": 0,
        "model_promotion_authorized": False, "outbound_authorized": False,
    }


def merge_review_archive(previous: Mapping[str, object] | None, latest: Mapping[str, object], *,
                         max_samples: int = MAX_ROWS) -> dict:
    """Keep provenance-only review history beyond the 48-hour source window.

    An updated public post replaces its previous digest and explicitly
    requires fresh independent review; previously adjudicated labels must
    never be silently transferred between content versions.
    """
    if type(max_samples) is not int or not 1 <= max_samples <= MAX_ROWS:
        raise ValueError("invalid review archive capacity")
    if (not isinstance(latest, Mapping)
        or latest.get("schema_version") != "empire.minimind_intent_review_queue.v1"
        or latest.get("mode") != "OBSERVE"
        or latest.get("execution_authority") != "none"
        or latest.get("outbound_authorized") is not False
        or latest.get("training_dataset") is not False):
        raise ValueError("unsafe MiniMind review queue")

    history = []
    if previous is not None:
        if (not isinstance(previous, Mapping)
            or previous.get("schema_version") != "empire.minimind_review_archive.v1"
            or previous.get("mode") != "OBSERVE"
            or previous.get("execution_authority") != "none"
            or previous.get("outbound_authorized") is not False
            or previous.get("model_promotion_authorized") is not False):
            raise ValueError("unsafe MiniMind archive")
        history = previous.get("review_items")
        if not isinstance(history, list) or len(history) > max_samples:
            raise ValueError("invalid existing archive length")
    current = latest.get("review_items")
    if not isinstance(current, list) or len(current) > max_samples:
        raise ValueError("invalid current review queue")

    def verify(row):
        if not isinstance(row, Mapping):
            raise ValueError("invalid review item")
        if (not isinstance(row.get("sample_ref"), str)
            or len(row["sample_ref"]) != 64
            or any(ch not in "0123456789abcdef" for ch in row["sample_ref"])
            or not isinstance(row.get("input_digest"), str)
            or len(row["input_digest"]) != 64
            or any(ch not in "0123456789abcdef" for ch in row["input_digest"])
            or row.get("source_class") not in DOMAINS
            or row.get("review_status") != "UNREVIEWED"
            or row.get("independent_gold_label") is not None
            or row.get("requires_authorized_human_review") is not True
            or row.get("verified_buyer_intent") is not False
            or row.get("outbound_authorized") is not False
            or row.get("review_priority") not in ("HIGH", "MEDIUM", "LOW")
            or row.get("proposed_weak_label") not in ALLOWED_CLASSES):
            raise ValueError("untrusted review archive item")
        url = row.get("public_review_url")
        if not isinstance(url, str):
            raise ValueError("invalid public review URL")
        parts = urlsplit(url)
        if (parts.scheme != "https" or parts.hostname not in DOMAINS[row["source_class"]]
            or parts.username or parts.password or parts.fragment or parts.query):
            raise ValueError("invalid public review host")
        return dict(row)

    combined = {}
    for row in history:
        item = verify(row)
        ref = item["sample_ref"]
        if ref in combined:
            raise ValueError("duplicate archived item")
        combined[ref] = item
    seen_new = set()
    new_count = changed = baseline_drift = 0
    for row in current:
        item = verify(row)
        ref = item["sample_ref"]
        if ref in seen_new:
            raise ValueError("duplicate current review item")
        seen_new.add(ref)
        old = combined.get(ref)
        if old is None:
            new_count += 1
        elif old["input_digest"] != item["input_digest"]:
            changed += 1
        elif old["proposed_weak_label"] != item["proposed_weak_label"]:
            # Baseline predictions are frozen at first observation. Rewriting
            # them after the classifier changes would falsify comparisons.
            baseline_drift += 1
            item["proposed_weak_label"] = old["proposed_weak_label"]
        # Never carry a previous claimed gold label or review state forward.
        combined[ref] = item
    # Retain current observations and higher-priority archived evidence.
    # Low-priority older-window entries are evicted first at the hard cap.
    priorities = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    prior_refs = sorted((r for r in combined if r not in seen_new),
                        key=lambda r: (priorities[combined[r]["review_priority"]], r))
    limit_prior = max_samples - len(seen_new)
    evicted = max(0, len(prior_refs) - limit_prior)
    retained = prior_refs[:limit_prior]
    merged = [combined[r] for r in sorted(seen_new)] + [combined[r] for r in retained]
    ordered = sorted(merged, key=lambda x: (
        {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[x["review_priority"]],
        x["sample_ref"],
    ))
    return {
        "schema_version": "empire.minimind_review_archive.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "review_items": ordered, "archive_count": len(ordered),
        "current_window_count": len(seen_new),
        "new_items_this_cycle": new_count,
        "changed_content_requires_new_review": changed,
        "baseline_label_drift_frozen": baseline_drift,
        "evicted_due_to_capacity": evicted,
        "independent_gold_label_count": 0,
        "raw_post_content_exported": False, "training_dataset": False,
        "model_promotion_authorized": False, "outbound_authorized": False,
    }


def manifest_from_review_archive(archive: Mapping[str, object]) -> dict:
    """Frozen, non-identifying baseline labels across successive source windows.

    The archive is a held research cohort, NOT permission to train or to infer
    commercial outcomes. Independent reviewed labels must still be supplied.
    """
    if (not isinstance(archive, Mapping)
        or archive.get("schema_version") != "empire.minimind_review_archive.v1"
        or archive.get("mode") != "OBSERVE"
        or archive.get("execution_authority") != "none"
        or archive.get("training_dataset") is not False
        or archive.get("outbound_authorized") is not False
        or archive.get("model_promotion_authorized") is not False):
        raise ValueError("unsafe archived evaluation cohort")
    items = archive.get("review_items")
    if not isinstance(items, list) or archive.get("archive_count") != len(items):
        raise ValueError("invalid archive cohort length")
    samples=[]
    seen=set()
    for item in items:
        if (not isinstance(item, Mapping)
            or not isinstance(item.get("sample_ref"), str)
            or item["sample_ref"] in seen
            or not isinstance(item.get("input_digest"), str)
            or item.get("proposed_weak_label") not in ALLOWED_CLASSES
            or item.get("review_status") != "UNREVIEWED"
            or item.get("independent_gold_label") is not None
            or item.get("outbound_authorized") is not False):
            raise ValueError("invalid archived sample")
        seen.add(item["sample_ref"])
        samples.append({
            "sample_ref":item["sample_ref"],
            "input_digest":item["input_digest"],
            "source_class":item["source_class"],
            "baseline_intent_class":item["proposed_weak_label"],
            "label_source":"DETERMINISTIC_WEAK_BASELINE_NOT_GOLD",
            "review_required":True,
            "buyer_identity_verified":False,
            "commercial_intent_verified":False,
            "outbound_authorized":False,
        })
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE","execution_authority":"none",
        "samples":sorted(samples,key=lambda x:x["sample_ref"]),
        "sample_count":len(samples),"raw_post_content_exported":False,
        "synthetic_labels_as_truth":False,"model_training_authorized":False,
        "outbound_authorized":False,
    }


def partition_review_attestations(reviewed: dict | None, manifest: dict) -> tuple[list[dict], int]:
    """Keep locally attested outcomes; quarantine old content versions.

    Never treat an old fingerprint, unknown sample or unreviewed claim as gold.
    Strict failures for malformed envelopes and duplicate reviewer attestations.
    """
    if reviewed is None:
        return [], 0
    if (not isinstance(reviewed, dict)
        or reviewed.get("schema_version") != "empire.minimind_manual_adjudications.v1"):
        raise ValueError("invalid adjudication provenance envelope")
    rows = reviewed.get("adjudications")
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("invalid bounded adjudication rows")
    known = {row["sample_ref"]: row["input_digest"] for row in manifest["samples"]}
    valid, stale, seen = [], 0, set()
    for row in rows:
        if (not isinstance(row, dict)
            or not isinstance(row.get("sample_ref"), str)
            or not isinstance(row.get("input_digest"), str)
            or row.get("label") not in ALLOWED_CLASSES
            or row.get("human_reviewed") is not True
            or row.get("synthetic") is not False
            or row.get("usage_scope") != "EVALUATION_ONLY"
            or not isinstance(row.get("review_ref"), str)
            or not row["review_ref"].strip()
            or row.get("commercial_intent_verified") is True
            or row.get("outbound_authorized") is True):
            raise ValueError("untrusted local reviewer attestation")
        ref = row["sample_ref"]
        if ref in seen:
            raise ValueError("duplicate local reviewer attestation")
        seen.add(ref)
        if known.get(ref) != row["input_digest"]:
            stale += 1
            continue
        valid.append(row)
    return valid, stale
