"""Read-only Awin publisher relationship API; NEVER publishes links or revenue."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
from hashlib import sha256
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Callable
from urllib import request, parse

PUBLISHER_ID = "3136281"
PROGRAMMES = {
    "122556": "OVO Solar & Heating",
    "73922": "Glow Green",
    "118321": "Project Solar",
    "51797": "EcoFlow UK",
}
LEGACY_PROGRAMME_IDS = frozenset(("122556", "73922"))
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



MAX_STATUS_TRANSITIONS = 80
VALID_STATUSES = frozenset(STATUS_CODES.values())


def _read_previous_membership(path: Path, now: datetime) -> tuple[dict[str, str] | None, list[dict]]:
    """Treat previous private snapshot as untrusted; refuse ambiguous history."""
    if not path.exists() and not path.is_symlink():
        return None, []
    if (path.is_symlink() or not path.is_file()
            or stat.S_IMODE(path.stat().st_mode) != 0o600
            or not 200 <= path.stat().st_size <= 64000):
        raise AwinAPIHold("AWIN_API_PREVIOUS_SNAPSHOT_UNSAFE")
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise AwinAPIHold("AWIN_API_PREVIOUS_SNAPSHOT_UNREADABLE") from exc
    if (not isinstance(old, dict)
            or old.get("schema_version") != SCHEMA
            or old.get("status") != "AWIN_API_MEMBERSHIP_REVIEW_VERIFIED"
            or old.get("publisher_id") != PUBLISHER_ID
            or old.get("api_live_verified") is not True
            or old.get("affiliate_publication_authorized") is not False
            or old.get("tracking_links_generated") is not False
            or old.get("commission_earned_verified") is not False
            or old.get("commission_paid_verified") is not False
            or old.get("outbound_sent") is not False
            or old.get("database_writes") is not False):
        raise AwinAPIHold("AWIN_API_PREVIOUS_AUTHORITY_INVALID")
    at = old.get("observed_at")
    try:
        date = datetime.fromisoformat(at) if isinstance(at, str) else None
    except ValueError:
        date = None
    if (date is None or date.utcoffset() is None
            or date.astimezone(timezone.utc) > now.astimezone(timezone.utc) + timedelta(seconds=90)):
        raise AwinAPIHold("AWIN_API_PREVIOUS_TIMESTAMP_INVALID")
    rows = old.get("programmes")
    if not isinstance(rows, list) or len(rows) not in (len(LEGACY_PROGRAMME_IDS), len(PROGRAMMES)):
        raise AwinAPIHold("AWIN_API_PREVIOUS_PROGRAMMES_INVALID")
    statuses: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise AwinAPIHold("AWIN_API_PREVIOUS_ROW_INVALID")
        ident = row.get("advertiser_id")
        state = row.get("membership_status")
        if (ident not in PROGRAMMES or ident in statuses
                or not isinstance(state, str) or state not in VALID_STATUSES
                or row.get("membership_verified_by_authenticated_awin_api") is not True
                or row.get("publisher_authorised_to_use_tracking_link") is not False):
            raise AwinAPIHold("AWIN_API_PREVIOUS_MEMBERSHIP_INVALID")
        statuses[ident] = state
    if set(statuses) not in (LEGACY_PROGRAMME_IDS, frozenset(PROGRAMMES)):
        raise AwinAPIHold("AWIN_API_PREVIOUS_IDS_INVALID")
    transitions = old.get("status_transitions", [])
    if not isinstance(transitions, list) or len(transitions) > MAX_STATUS_TRANSITIONS:
        raise AwinAPIHold("AWIN_API_PREVIOUS_HISTORY_INVALID")
    observed_ids: set[str] = set()
    for event in transitions:
        if not isinstance(event, dict):
            raise AwinAPIHold("AWIN_API_PREVIOUS_EVENT_INVALID")
        event_id=event.get("event_id")
        if (not isinstance(event_id, str)
                or not re.fullmatch(r"[a-f0-9]{24}", event_id)
                or event_id in observed_ids
                or event.get("advertiser_id") not in PROGRAMMES
                or event.get("from_status") not in VALID_STATUSES
                or event.get("to_status") not in VALID_STATUSES
                or event["from_status"] == event["to_status"]
                or event.get("review_required") is not True
                or event.get("review_status") != "REVIEW_NOT_YET_ADMITTED"):
            raise AwinAPIHold("AWIN_API_PREVIOUS_EVENT_UNVERIFIED")
        observed_ids.add(event_id)
    return statuses, transitions


def _transition_events(previous: dict[str, str] | None, old_events: list[dict],
                       programmes: list[dict], at: datetime) -> tuple[list[dict], list[dict]]:
    """First authenticated snapshot is a baseline, not an invented change."""
    all_events = list(old_events)
    new_events: list[dict] = []
    if previous is None:
        return all_events, new_events
    for row in programmes:
        ident = row["advertiser_id"]
        before = previous.get(ident)
        # First observed state of an authorised newly tracked programme
        # is a baseline, not a fabricated status-change event.
        if before is None:
            continue
        after = row["membership_status"]
        if before == after:
            continue
        digest = sha256(
            f"{PUBLISHER_ID}|{ident}|{before}|{after}|{at.astimezone(timezone.utc).isoformat()}".encode("utf-8")
        ).hexdigest()[:24]
        new_events.append({
            "event_id": digest,
            "advertiser_id": ident,
            "from_status": before,
            "to_status": after,
            "detected_at": at.astimezone(timezone.utc).isoformat(),
            "required_action": row["action"],
            "review_required": True,
            "review_status": "REVIEW_NOT_YET_ADMITTED",
            "affiliate_publication_authorized": False,
            "commission_verified": False,
        })
    if len(all_events) + len(new_events) > MAX_STATUS_TRANSITIONS:
        raise AwinAPIHold("AWIN_API_STATUS_HISTORY_CAPACITY_REVIEW_REQUIRED")
    all_events.extend(new_events)
    return all_events, new_events


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
        previous, historic_events = _read_previous_membership(output, current)
        programmes = []
        for advertiser_id in PROGRAMMES:
            params = parse.urlencode({"advertiserId": advertiser_id,
                                      "relationship": "any"})
            url = BASE + "/publishers/" + PUBLISHER_ID + "/programmedetails?" + params
            requests_made += 1
            data = transport(url, token)
            programmes.append(_normalise(data, advertiser_id))
        transitions, new_transitions = _transition_events(
            previous, historic_events, programmes, current)
        result = {
            "schema_version": SCHEMA,
            "status": "AWIN_API_MEMBERSHIP_REVIEW_VERIFIED",
            "observed_at": current.astimezone(timezone.utc).isoformat(),
            "publisher_id": PUBLISHER_ID,
            "source": "AWIN_AUTHENTICATED_PUBLISHER_API_PROGRAMMEDETAILS",
            "api_live_verified": True, "programmes": programmes,
            "requests_made": requests_made,
            "status_transitions": transitions,
            "new_status_transition_count": len(new_transitions),
            "historical_status_transition_count": len(transitions),
            "transition_review_required": bool(new_transitions),
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
