"""Open-source deliverability evidence adapters.

These adapters consume machine output from externally-run open-source observers.
They do not invoke binaries, mutate DNS, or grant those tools decision authority.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def normalize_checkdmarc_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(payload)
    spf = dict(row.get("spf") or {})
    dmarc = dict(row.get("dmarc") or {})
    mx = row.get("mx") or {}
    mta_sts = dict(row.get("mta_sts") or row.get("mta-sts") or {})
    tlsrpt = dict(row.get("smtp_tls_reporting") or row.get("tlsrpt") or {})

    def _warnings(value: Any) -> list[str]:
        if isinstance(value, Mapping):
            raw = value.get("warnings") or []
            if isinstance(raw, list):
                return [str(item) for item in raw]
        return []

    def _valid(value: Mapping[str, Any]) -> bool | None:
        if not value:
            return None
        if value.get("valid") is not None:
            return value.get("valid") is True
        if value.get("error"):
            return False
        record = value.get("record")
        return bool(record) if record is not None else None

    mx_rows = []
    if isinstance(mx, Mapping):
        hosts = mx.get("hosts") or []
        if isinstance(hosts, list):
            mx_rows = [dict(item) for item in hosts if isinstance(item, Mapping)]
    elif isinstance(mx, list):
        mx_rows = [dict(item) for item in mx if isinstance(item, Mapping)]

    starttls_values = [
        host.get("starttls")
        for host in mx_rows
        if host.get("starttls") is not None
    ]
    starttls_ready = (
        all(value is True for value in starttls_values)
        if starttls_values
        else None
    )

    warnings = (
        _warnings(spf)
        + _warnings(dmarc)
        + _warnings(mta_sts)
        + _warnings(tlsrpt)
    )

    return {
        "source": "checkdmarc",
        "domain": str(row.get("domain") or ""),
        "spf_valid": _valid(spf),
        "dmarc_valid": _valid(dmarc),
        "mta_sts_valid": _valid(mta_sts),
        "tlsrpt_valid": _valid(tlsrpt),
        "mx_starttls_ready": starttls_ready,
        "warnings": warnings,
        "warning_count": len(warnings),
        "raw": row,
        "mutation_authorized": False,
    }


def summarize_parsedmarc_aggregate(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Summarize one parsed aggregate report without trusting vendor naming."""

    row = dict(payload)
    records = row.get("records") or []
    if not isinstance(records, list):
        records = []

    messages = 0
    spf_aligned = 0
    dkim_aligned = 0
    fully_aligned = 0
    failed = 0

    for raw in records:
        if not isinstance(raw, Mapping):
            continue
        record = dict(raw)
        count = max(0, int(record.get("count") or 0))
        messages += count

        alignment = dict(record.get("alignment") or {})
        spf_pass = alignment.get("spf") is True
        dkim_pass = alignment.get("dkim") is True
        dmarc_pass = alignment.get("dmarc")

        if spf_pass:
            spf_aligned += count
        if dkim_pass:
            dkim_aligned += count

        if dmarc_pass is True or (dmarc_pass is None and (spf_pass or dkim_pass)):
            fully_aligned += count
        else:
            failed += count

    def rate(value: int) -> float:
        return value / messages if messages else 0.0

    return {
        "source": "parsedmarc",
        "domain": str(
            row.get("domain")
            or dict(row.get("report_metadata") or {}).get("domain")
            or dict(row.get("policy_published") or {}).get("domain")
            or ""
        ),
        "messages": messages,
        "spf_aligned": spf_aligned,
        "dkim_aligned": dkim_aligned,
        "dmarc_passed": fully_aligned,
        "dmarc_failed": failed,
        "spf_alignment_rate": rate(spf_aligned),
        "dkim_alignment_rate": rate(dkim_aligned),
        "dmarc_pass_rate": rate(fully_aligned),
        "raw": row,
        "mutation_authorized": False,
    }


def normalize_dnscontrol_preview(
    corrections: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Normalize a wrapper-produced DNSControl preview; never execute push."""

    rows: list[dict[str, str]] = []
    destructive = 0

    for raw in corrections:
        row = dict(raw)
        action = str(row.get("action") or "").strip().upper()
        record_type = str(row.get("record_type") or "").strip().upper()
        name = str(row.get("name") or "").strip()
        if action not in {"ADD", "CHANGE", "DELETE"}:
            raise ValueError("unsupported_dnscontrol_preview_action")
        if not name:
            raise ValueError("dnscontrol_preview_name_required")
        if action == "DELETE":
            destructive += 1
        rows.append({
            "action": action,
            "record_type": record_type,
            "name": name,
        })

    changed = bool(rows)
    if destructive:
        posture = "APPROVAL_REQUIRED"
    elif changed:
        posture = "DRIFT"
    else:
        posture = "STABLE"

    return {
        "source": "dnscontrol_preview",
        "posture": posture,
        "corrections": rows,
        "correction_count": len(rows),
        "delete_count": destructive,
        "dns_push_authorized": False,
        "mutation_authorized": False,
    }
