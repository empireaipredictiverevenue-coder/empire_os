"""Read-only Awin publisher relationship API; NEVER publishes links or revenue."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Callable
from urllib import request, parse

PUBLISHER_ID = "3136281"
PROGRAMMES = {"122556": "OVO Solar & Heating", "73922": "Glow Green"}
TOKEN_PATH = Path("/srv/empire_os/runtime/secrets/awin-publisher-api-token")
SNAPSHOT_PATH = Path("/srv/empire_os/runtime/buyer_network_intelligence/awin_publisher_api_membership_latest.json")
SCHEMA = "empire.awin.publisher_programme_membership.v1"
BASE = "https://api.awin.com"
STATUS_CODES = {
    "joined": "JOINED",
    "pending": "PENDING",
    "suspended": "SUSPENDED",
    "rejected": "REJECTED",
    "notjoined": "NOT_JOINED",
}


class AwinAPIHold(ValueError):
    pass


def _private_token(path: Path) -> str:
    if (path.is_symlink() or not path.is_file()
            or stat.S_IMODE(path.stat().st_mode) != 0o600
            or not 24 <= path.stat().st_size <= 2048):
        raise AwinAPIHold("AWIN_API_TOKEN_MISSING_OR_UNSAFE")
    try:
        token = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError) as exc:
        raise AwinAPIHold("AWIN_API_TOKEN_UNREADABLE") from exc
    if not re.fullmatch(r"[A-Za-z0-9._~-]{24,2048}", token):
        raise AwinAPIHold("AWIN_API_TOKEN_FORMAT_INVALID")
    return token


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AwinAPIHold("AWIN_API_REDIRECT_BLOCKED")


def _transport(url: str, token: str) -> dict:
    """Exactly one HTTPS request; never serialize bearer credentials."""
    if not url.startswith(BASE + "/publishers/" + PUBLISHER_ID + "/programmedetails?"):
        raise AwinAPIHold("AWIN_API_URL_NOT_ALLOWED")
    opener = request.build_opener(_NoRedirect())
    req = request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "User-Agent": "EmpireAI-Awin-Publisher-ReadOnly/1",
    }, method="GET")
    try:
        with opener.open(req, timeout=9) as response:
            if response.status != 200:
                raise AwinAPIHold("AWIN_API_NON_200")
            mime = response.headers.get_content_type()
            if mime != "application/json":
                raise AwinAPIHold("AWIN_API_CONTENT_TYPE_INVALID")
            raw = response.read(131073)
            if not 2 <= len(raw) <= 131072:
                raise AwinAPIHold("AWIN_API_PAYLOAD_BOUNDS")
    except AwinAPIHold:
        raise
    except Exception as exc:
        raise AwinAPIHold("AWIN_API_AUTH_OR_NETWORK_UNAVAILABLE") from exc
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        raise AwinAPIHold("AWIN_API_PAYLOAD_INVALID") from None
    if not isinstance(data, dict):
        raise AwinAPIHold("AWIN_API_NONOBJECT_DETAILS")
    return data


def _normalise(details: dict, advertiser_id: str) -> dict:
    if not isinstance(details, dict) or advertiser_id not in PROGRAMMES:
        raise AwinAPIHold("AWIN_API_PROGRAMME_UNKNOWN")
    info = details.get("programmeInfo")
    if not isinstance(info, dict):
        raise AwinAPIHold("AWIN_API_PROGRAMME_INFO_MISSING")
    ident = info.get("id")
    if type(ident) not in (int, str) or str(ident) != advertiser_id:
        raise AwinAPIHold("AWIN_API_PROGRAMME_ID_MISMATCH")
    state = info.get("membershipStatus")
    if not isinstance(state, str) or state.strip().casefold() not in STATUS_CODES:
        raise AwinAPIHold("AWIN_API_MEMBERSHIP_STATUS_UNSUPPORTED")
    status = STATUS_CODES[state.strip().casefold()]
    return {
        "advertiser_id": advertiser_id,
        "advertiser": PROGRAMMES[advertiser_id],
        "membership_status": status,
        "membership_verified_by_authenticated_awin_api": True,
        "awaiting_advertiser_decision": status == "PENDING",
        "publisher_authorised_to_use_tracking_link": False,
        "commission_earned_verified": False,
        "settled_payout_verified": False,
        "action": (
            "REVIEW_JOINED_PROGRAMME_TERMS_AND_TRACKING_AUTHORISATION"
            if status == "JOINED" else
            "REVIEW_REJECTION" if status == "REJECTED" else
            "REVIEW_SUSPENSION" if status == "SUSPENDED" else
            "AWAIT_DECISION" if status == "PENDING" else
            "REVIEW_UNJOINED_PROGRAMME"
        ),
    }


def review(*, token_path: Path = TOKEN_PATH, output: Path = SNAPSHOT_PATH,
           now: datetime | None = None, transport: Callable = _transport,
           write: bool = False) -> dict:
    """No side effects except an optional private membership snapshot."""
    held = {
        "status": "HELD_AWIN_API_TOKEN_NOT_READY_OR_PROVIDER_UNAVAILABLE",
        "publisher_id": PUBLISHER_ID, "api_live_verified": False,
        "requests_made": 0, "snapshot_written": False,
        "execution_authority": "NONE", "outbound_sent": False,
        "database_writes": False, "tracking_links_generated": False,
        "revenue_verified": False,
    }
    requests_made = 0
    try:
        current = now or datetime.now(timezone.utc)
        if not isinstance(current, datetime) or current.utcoffset() is None:
            raise AwinAPIHold("AWIN_API_TIME_INVALID")
        token = _private_token(token_path)
        programmes = []
        for advertiser_id in PROGRAMMES:
            params = parse.urlencode({"advertiserId": advertiser_id,
                                      "relationship": "any"})
            url = BASE + "/publishers/" + PUBLISHER_ID + "/programmedetails?" + params
            requests_made += 1
            data = transport(url, token)
            programmes.append(_normalise(data, advertiser_id))
        result = {
            "schema_version": SCHEMA,
            "status": "AWIN_API_MEMBERSHIP_REVIEW_VERIFIED",
            "observed_at": current.astimezone(timezone.utc).isoformat(),
            "publisher_id": PUBLISHER_ID,
            "source": "AWIN_AUTHENTICATED_PUBLISHER_API_PROGRAMMEDETAILS",
            "api_live_verified": True, "programmes": programmes,
            "requests_made": requests_made,
            "any_joined": any(x["membership_status"] == "JOINED" for x in programmes),
            "advertiser_terms_reviewed": False,
            "tracking_links_generated": False,
            "affiliate_publication_authorized": False,
            "commission_earned_verified": False,
            "commission_paid_verified": False,
            "execution_authority": "NONE",
            "outbound_sent": False, "database_writes": False,
        }
        if write:
            if (output.is_symlink() or output.parent.is_symlink()
                    or not output.parent.is_dir()
                    or (output.exists() and (not output.is_file() or
                         stat.S_IMODE(output.stat().st_mode) != 0o600))):
                raise AwinAPIHold("AWIN_API_SNAPSHOT_PATH_UNSAFE")
            fd,temp = tempfile.mkstemp(dir=output.parent,prefix=".awin_api_")
            try:
                with os.fdopen(fd,"w",encoding="utf-8") as stream:
                    os.fchmod(stream.fileno(),0o600)
                    json.dump(result,stream,sort_keys=True,indent=2)
                    stream.write("\n")
                    stream.flush(); os.fsync(stream.fileno())
                os.replace(temp,output)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
        return {**result,"snapshot_written":write}
    except (AwinAPIHold, OSError, TypeError, ValueError):
        return {**held,"requests_made":requests_made}
