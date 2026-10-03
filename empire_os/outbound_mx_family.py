"""Recipient MX family classification for destination-specific pacing.

This module classifies already-observed MX hostnames. DNS observation is separate so
classification remains deterministic and testable.
"""
from __future__ import annotations

from typing import Iterable


def classify_mx_family(mx_hosts: Iterable[str]) -> dict[str, object]:
    hosts = sorted({
        str(host or "").strip().lower().rstrip(".")
        for host in mx_hosts
        if str(host or "").strip()
    })

    families: set[str] = set()
    for host in hosts:
        if (
            host.endswith(".google.com")
            or "googlemail.com" in host
            or "aspmx.l.google.com" in host
        ):
            families.add("GOOGLE")
        elif (
            host.endswith(".outlook.com")
            or "protection.outlook.com" in host
            or host.endswith(".hotmail.com")
        ):
            families.add("MICROSOFT")
        elif host.endswith(".yahoodns.net") or host.endswith(".yahoo.com"):
            families.add("YAHOO")
        elif host.endswith(".icloud.com") or host.endswith(".me.com"):
            families.add("APPLE")
        else:
            families.add("OTHER")

    if not hosts:
        family = "UNKNOWN"
    elif len(families) == 1:
        family = next(iter(families))
    else:
        family = "MIXED"

    return {
        "family": family,
        "families": sorted(families),
        "mx_hosts": hosts,
        "classification_basis": "observed_mx_hostname",
    }
