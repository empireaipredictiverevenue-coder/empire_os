#!/usr/bin/env python3
"""One authorised Brave API search through existing Search Fabric.

Invoke from a root-managed, unprivileged systemd transient service whose
EnvironmentFile=/etc/empire_os.env. NEVER put the key on the command line.
Outputs source hostnames and provider status only; no raw results or secrets.
No Scout, CRM, campaigns, contact, outreach or paid bulk jobs are started.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import tempfile
from urllib.parse import urlparse

QUERY = "roofing contractors Tampa Florida"
_REDACTABLE = re.compile(r"(?:[A-Za-z0-9_-]{16,})")
def main() -> int:
    key = os.environ.get("BRAVE_API_KEY", "").strip()
    if not key or key == "YOUR_ACTUAL_BRAVE_KEY" or len(key) < 12:
        print(json.dumps({"provider": "brave", "state": "KEY_NOT_AVAILABLE_IN_SERVICE_ENVIRONMENT",
                          "provider_requests": 0, "verified_buyers": 0}))
        return 2

    os.environ["EMPIRE_SEARCH_KEYED_ATTEMPTS"] = "1"
    os.environ["EMPIRE_SEARCH_KEYED_TIMEOUT_SECONDS"] = "10"
    # Prevent unwanted proxy routing or persistence in production search cache.
    os.environ.pop("SEARCH_PROXIES", None)

    with tempfile.TemporaryDirectory(prefix="empire_brave_single_query_") as temp:
        os.environ["EMPIRE_SEARCH_CACHE"] = temp
        from empire_os.search_fabric.search import search
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            response = search(QUERY, num=3, engine="brave", use_cache=False)
        found = response.get("organic", [])
        hosts = []
        for row in found[:3]:
            url = row.get("link")
            if isinstance(url, str):
                host = urlparse(url).hostname
                if host and host not in hosts:
                    hosts.append(host.lower())
        diagnostics = stderr.getvalue().lower()
        http_status = None
        for code in ("401", "403", "429", "422", "503", "202"):
            if "brave http " + code in diagnostics:
                http_status = int(code)
                break
        if hosts:
            state = "BRAVE_SEARCH_RETURNED_SOURCE_RESULTS"
        elif http_status in (401, 403, 422):
            state = "BRAVE_KEY_OR_ACCOUNT_AUTHENTICATION_REJECTED"
        elif http_status == 429:
            state = "BRAVE_QUOTA_OR_RATE_LIMIT"
        elif "brave rejected: no relevant results" in diagnostics:
            state = "BRAVE_RESPONSE_REJECTED_BY_RELEVANCE_GATE"
        else:
            state = "BRAVE_NO_USABLE_RESULTS_PROVIDER_STATUS_UNVERIFIED"
        # Result URLs are represented as public domain names only.
        print(json.dumps({
            "provider": "brave",
            "state": state,
            "provider_query_count_max": 1,
            "fresh_public_domains": hosts,
            "result_count": len(found),
            "http_failure_code_if_detected": http_status,
            "api_key_readable_from_service_environment": True,
            "api_key_value_logged": False,
            "buyer_scout_or_crm_modified": False,
            "messages_sent": 0,
            "verified_buyers": 0,
        }, sort_keys=True))
    return 0 if hosts else 3


if __name__ == "__main__":
    raise SystemExit(main())
